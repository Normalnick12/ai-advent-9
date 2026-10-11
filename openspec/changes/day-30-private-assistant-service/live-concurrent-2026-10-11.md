# Day 30 — logging correction и одна concurrent live-пара, 2026-10-11

Совместный review предыдущего диалога подтверждён пользователем: первый ход
technical PASS / semantic PARTIAL, уточнение technical PASS / semantic FAIL.
Передача истории подтверждена, качественное использование её моделью — нет.
Prompts, RAG, schema, модель и лимиты ради улучшения результатов не изменялись.
Исторический Day 29 NO SUITABLE PROFILE CONFIRMED сохранён.

## Исправление logging и offline gate

Причина HTTPX INFO в первом live: стандартный `uvicorn.Config.configure_logging`
вызывает `dictConfig` с `disable_existing_loggers=False`, который повторно включает
ранее отключённый logger `httpx`. Кроме того, `logger.disabled` не наследуется
дочерними логгерами. Простое отключение родителя недостаточно.

Минимальная правка ограничена `server.py`: HTTPX/HTTPCore получают NullHandler и
`propagate=False`; `uvicorn.access` отключён; `uvicorn.run(log_config=None)` сохраняет
политику launcher вместо повторной настройки. `laa.http` и безопасный lifecycle
сервера продолжают работать. Изменений core/runtime/CLI нет.

Новый regression запускает launcher и настоящую конфигурацию Uvicorn в изолированном
subprocess, выполняет HTTPX MockTransport request с canary URL/query/header и
имитирует descendant debug/error/exception records. Проверяет отсутствие canaries
и HTTPX INFO, а также наличие safe completion/HTTP-style метрик.
Первый вариант теста выявил дополнительный путь `uvicorn.access` → lastResort после
очистки handlers; итоговая политика закрывает его. Изменения не выходили за logging.

Перед live: **66 passed**, 2.94 s, **OpenSpec strict validation PASS**.
Единственный warning — ранее известный deprecated Starlette TestClient/httpx backend.
Проверен синтаксис launcher, regression и локальных наблюдателей. Real generation
во время offline-проверок не выполнялась.

## Повторный preflight

- Ollama local-only подтверждена текущим startup log (`cloud disabled=true`) и
  listener `127.0.0.1:11434`; порт 8030 до запуска свободен.
- Установленный `qwen2.5-coder:7b-instruct-q4_K_M`, digest
  `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`;
  remote metadata отсутствует.
- До запуска нет резидентных моделей, runner-процесса и клиентских соединений к
  Ollama. GPU снимки после краткого всплеска фоновой нагрузки: 12%, 2%, 1%,
  VRAM 734/702/702 MiB. Существенной устойчивой сторонней нагрузки не наблюдалось.
- Разрешённые synthetic Workspace/Knowledge и свежий индекс совпадают с fixtures
  предыдущего этапа. Новых embeddings **0**, rebuild **0**, warm-up **0**.
- Фактические `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_QUEUE=512` не менялись.
  Операторская рекомендация queue=2 не применялась скрыто; приложение по-прежнему
  допускает максимум два chat и не имеет собственной очереди.
- HTTP запущен штатным launcher с временным content-free observer только на
  `127.0.0.1:8030`. Health/readiness 200 до chat. Bearer получен из прежнего
  DPAPI-файла вне Git; два независимых HTTPX клиента использовали разрешённый token.

## Единственная пара

Два клиента с собственными TCP-соединениями одновременно запущены общим стартовым
барьером, по одному различному synthetic question, без history. Client A — ветка
пустой корзины; B — ветка отклонённого платежа. Содержание вопросов/ответов в
технических записях не сохранялось. Полный успешный synthetic ответ просмотрен
в stdout клиента для предварительного review; сервер его не журналировал.

| Метрика | A | B |
|---|---:|---:|
| request_id | f5672442717c4fe4aae653ce3ed238b7 | 3149e64a3a414934a39f4deb65a800f1 |
| Старт, client-relative seconds | 0.063719 | 0.063552 |
| Завершение, client-relative seconds | 13.280069 | 37.733516 |
| HTTP wall | 13.216342 s | 37.669953 s |
| HTTP status | 200 | 502 invalid_model_response |
| Ollama done / reason | true / stop | true / length |
| Mechanical validation | passed | failed |
| Prompt / output tokens | 1285 / 874 | 1280 / 2048 |
| Provider total | 13.158113 s | 37.611701 s |
| Provider load | 2.633269 s | 2.632695 s |
| Provider prompt evaluation | 0.313397 s | 0.176730 s |
| Provider generation evaluation | 10.201424 s | 24.234816 s |

Provider times сохранены наблюдателем после исходного transport; raw model output
не сохранялся и не обходил HTTP validation. Номер observer turn определялся при
upstream submission и не равен порядку HTTP admission: A дошёл до upstream первым.

На offset=0.275704 s status подтвердил **active=2, max_active=2**, оба клиента ещё
ожидали. Затем `/healthz` вернул **200 за 1.15 ms**, оба клиента оставались pending.
HTTP-интервалы перекрываются примерно на **13.216 s**. Два разных request_id,
две записи admission и две completion сохранены. Третьего chat, retry или повышения
лимитов не было. B достиг фиксированного num_predict=2048; валидатор корректно
не выдал оборванный ответ за успех. После 502 серия остановлена.

## Очередь, ресурсы и logging

Две upstream submission были разделены примерно 1.03 ms. Текущий Ollama runner
сообщил `n_seq_max=1`; вместе с parallel=1 это соответствует последовательной
обработке. Прямой метрики глубины/времени очереди нет: **queue wait unavailable**.
Разность durations не объявляется измерением queue wait. Фактический параллельный
GPU inference не подтверждён и не является условием проверки HTTP concurrency.

Во время выполнения снимок GPU: 5879 MiB VRAM / 95% utilization; после —
5898 MiB / 8%. Это system-wide snapshots, не peak или доказательство parallelism.

Фактический server log нового запуска не содержит `HTTP Request:` и проверяемых
markers URL/query/header/token/source; безопасные `operation_admitted`,
`operation_finished`, `http_finished` и shutdown сохранены. Ollama log подтвердил
ровно **2 новых завершённых chat**, **0 embed**. Общий Day 30 budget на данный момент:
**4 chat calls** (первый диалог 2 + эта пара 2) и **1 embedding batch**.

Конечный status: active=0, max_active=2, recovery_required=false. Неизвестного
завершения нет: B вернул terminal done/length. Cached ready=false после ошибки /
истечения cache не выдаётся за новую проверку readiness. HTTP штатно остановлен;
Ollama не останавливалась/перенастраивалась. Hashes корпуса/индекса до/после совпали.

## Verdict и дальнейший gate

- Logging fix: **PASS** offline и по фактическому live stdout.
- HTTP concurrency / health responsiveness: **PASS**.
- Клиент A: **technical PASS**, предварительно **semantic PARTIAL**. Ответ правильно
  связывает пустую корзину с ранним return до оплаты, но одно application ошибочно
  обосновывает правило approved-payment поведением empty-cart; наблюдение о непустой
  корзине также слишком обобщает последующую очистку.
- Клиент B: **technical FAIL** (`length`); **semantic NOT EVALUATED**, завершённого
  валидного ответа клиент не получил.
- Критерий двух успешно завершённых валидных ответов пары: **FAIL**. Обработка 502
  работает корректно, но это не замена успешной live-паре.

Task 6.3 остаётся открытой. Task 6.4 завершена: зафиксированы отдельные verdicts,
метрики и stop-on-error. OpenSpec **28/33**; новая генерация/повтор возможны только
после отдельного решения пользователя. Tailscale, второй физический клиент через
интернет, Mac, commit/push/archive и видео не выполнялись.
