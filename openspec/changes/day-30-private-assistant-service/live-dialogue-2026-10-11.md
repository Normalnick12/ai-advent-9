# Day 30 — первый локальный live-диалог, 2026-10-11

Scope: отдельно разрешённый Windows preflight, одно построение synthetic index,
не более двух последовательных реальных HTTP chat calls. Повторов, warm-up,
конкурентной пары, Tailscale, внешних listener/route, изменения Ollama config,
скачивания моделей, commit/push/archive и видео не было. Production runtime не менялся.
Полные синтетические ответы показаны пользователю в чате; этот файл содержит только
технические сведения и review, без transcript, вопросов, токенов и содержимого корпуса.

## Preflight и корпус

- Windows, Ollama **0.40.2**, RTX 4070 SUPER 12 GB, RAM около 32 GB.
- Startup log текущего процесса: `Ollama cloud disabled: true`,
  `OLLAMA_NO_CLOUD=true`, `OLLAMA_HOST=http://127.0.0.1:11434`.
- Фактический listener Ollama: только `127.0.0.1:11434`; порт 8030 до запуска свободен.
- Coder: `qwen2.5-coder:7b-instruct-q4_K_M`, установлен локально, remote metadata отсутствует.
  Digest: `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
- Embedding: `qwen3-embedding:0.6b`, установлен локально, remote metadata отсутствует.
  Digest: `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`.
- Перед работой `/api/ps` пуст, runner process отсутствует, соединений клиентов к
  Ollama нет, GPU utilization 0%. Последние прежние chat в server log имели 200
  несколько часов назад. Совокупность снимков не показала незавершённых операций;
  один только `/api/ps` не считался доказательством отсутствия работы.
- Фактические настройки: parallel=1, queue=512, max_loaded_models=0 (как записано
  в startup log). Они не изменялись. Рекомендованный для будущей конкурентной
  демонстрации queue=2 не применялся скрыто.

Создан отдельный игнорируемый `.local/day30/` с копиями ровно двух проверенных
учебных fixtures: `day-27-local-architecture-assistant/tests/fixtures/CheckoutCoordinator.kt`
в Workspace и `day-28-local-architecture-rag/fixtures/knowledge/checkout.md` в Knowledge.
Корпоративные/пользовательские файлы не читались для индексации. Allowlist:
`checkout-demo` → `CheckoutCoordinator.kt`. Kotlin: 26 строк. Knowledge: **1 документ,
4 chunks**, явная include policy только `checkout.md`.

Индекса раньше не было. Выполнено **одно построение**, **1 POST /api/embed** с четырьмя
входами, **0 chat calls** на этом шаге. Проверка freshness после записи PASS.
Embedding wall time 2.356243 s; provider total 2.258342 s, load 2.131938 s,
prompt_eval_count 188. После embedding `/api/ps` снова пуст; отдельной загрузки
или warm-up не выполнялось.

Конфигурация и secrets исключены из Git. JSON хранит только имя env-переменной;
Bearer token генерировался в памяти и сохранён локально в DPAPI-encrypted файле.
Значение токена не печаталось и не передавалось в arguments/URL.

## HTTP и два последовательных хода

Штатный `server.main` запущен в отдельной управляемой терминальной сессии, один
worker, listener **127.0.0.1:8030**. Временный локальный observer делегирует
исходным функциям runtime без изменения prompt/schema/limits/transport; сравнивает
подготовленный payload в памяти и сохраняет только booleans/counts/timings.
Собственный generation budget observer и клиент ограничены двумя вызовами.

До диалога: `/healthz` 200, авторизованный `/readyz` 200, `/v1/status` 200
(`ready=true`, active=0, recovery=false). Без токена status и chat вернули 401.
Generation count после этих проверок **0**; `/api/ps` оставался пустым.

| Метрика | Ход 1 | Ход 2 |
|---|---:|---:|
| HTTP | 200 | 200 |
| request_id | 69b8b277aeb047028aa7deb0c10cecf0 | 11ec53279ffa4bdba0fe74f60522c35a |
| HTTP wall, s | 13.045816 | 10.900903 |
| Runtime retrieval, s | 0.001095 | 0.001382 |
| Runtime generation phase, s | 12.982596 | 10.867091 |
| Ollama total, s | 12.978349 | 10.864168 |
| Ollama load, s | 2.305593 | 0.006629 |
| Ollama prompt eval, s | 0.274323 | 0.336892 |
| Ollama generation eval, s | 10.389298 | 10.464993 |
| Prompt / output tokens | 1279 / 943 | 2231 / 946 |
| History pairs / compact bytes | 0 / 2 | 1 / 3852 |
| Полный Ollama request, bytes | 7219 | 11423 |
| Selected / omitted chunks | 4 / 0 | 4 / 0 |
| done / reason | true / stop | true / stop |
| Mechanical validation | passed | passed |
| API semantic_status | not_evaluated | not_evaluated |

Provider durations переведены из наносекунд. Runtime generation phase включает
ожидание ответа и загрузку; это не чистое время декодирования. Второй запрос
использовал резидентную модель; cold OS cache не утверждается для первого.

На втором ходе непосредственно перед единственным `generate` подтверждены:
`history_matches_client=true`, `query_matches_current_last_user_filename=true`,
`last_user_in_query=true`, `kotlin_matches_current=true`,
`documents_match_current_retrieval=true`. Клиент передал полный первый вопрос и
полный отрендеренный ответ в одной паре, без trimming и server session.
Assistant history не включалась в retrieval query. Validation применена к текущим
строкам/найденным chunks. Это подтверждает передачу контекста, но не доказывает,
что модель содержательно использовала его или что те же chunks не нашлись бы по filename.

Проверка файлов Workspace/Knowledge/index до и после диалога: hashes совпали.
Observer очищал thread-local контекст по окончании каждого вызова, клиент очистил
RAM history при выходе. Сохранённые записи проверены на отсутствие содержимого
диалога и токена; серверного transcript/session storage нет.

## Ресурсы и остановка

| Snapshot | VRAM used MiB | GPU utilization | RAM available MiB |
|---|---:|---:|---:|
| До диалога | 739 | 0% | 18886 |
| Во время диалога | 5846 | 79% | 17943 |
| После диалога | 5844 | 0% | 18025 |

Это system-wide snapshots, не peak и не process RSS. RAM total 32607 MiB.
Per-process VRAM под WDDM недоступна. После завершения `/api/ps` показал Coder
с context_length=8192, size=size_vram=5133943438 bytes.

Финальный status: active=0, max_active=1, recovery_required=false. Cached ready
стал false из-за истечения пятисекундного readiness cache; повторного ready probe
в этом снимке не было. Это не наблюдение ошибки Ollama. После двух terminal ответов
HTTP остановлен Ctrl+C; shutdown сообщил active=0/recovery=false. Ollama не
останавливалась и не перенастраивалась, принудительная выгрузка модели не выполнялась.

## Verdict и замечания

- **Технический диалог PASS**: ровно 2 chat generations, 2 HTTP 200, done/stop и
  mechanical validation, подтверждённая клиентская history и текущие источники.
- **Предварительный смысловой review: ход 1 PARTIAL, ход 2 FAIL.** Первый ответ
  содержит подходящее описание координации и ограничения гарантий, но наблюдения
  в основном перепечатывают код, а документация цитируется по-английски. Номера
  строк проходят bounds check, однако первая ссылка включает строки package/blank
  и не точно соответствует цитируемой декларации — это не semantic verification.
  Второй ответ почти полностью повторяет первый (переставлены applications) и
  не даёт прямого контекстного объяснения связи перехода с проверкой approved.
  Подходящее правило присутствует в цитате, но уточнение содержательно не отработано.
- **Диагностика требует отдельного review:** несмотря на `logger.disabled` в launcher,
  в stdout остались HTTPX INFO method/локальный URL/status. Тел, Authorization,
  вопросов и ответов в этих строках нет, но обещание полного подавления HTTPX logs
  фактический запуск не подтвердил. Runtime во время live не исправлялся.

Coder остаётся техническим кандидатом; Day 29 **NO SUITABLE PROFILE CONFIRMED**
не изменён. Это один диалог, не оценка устойчивости модели. Конкурентная live-пара,
Tailscale/второе устройство и Mac остаются **NOT TESTED / PENDING**.

OpenSpec: 6.1 и 6.2 выполнены, **27/33**. Для 6.4 сохранены метрики этой части;
полная локальная сводка остаётся открытой до отдельно разрешённой конкурентной пары.

Итоговая OpenSpec strict validation **PASS**. Порт 8030 после shutdown не слушается;
Ollama продолжает слушать только loopback 11434. Новая часть Ollama log содержит
ровно 2 завершённых `/api/chat` и 1 `/api/embed`; проверяемое содержимое диалога,
Kotlin/Markdown и Authorization в ней не обнаружено. SHA-256 сверка 885 существующих
файлов выявила изменения только Day 30 README и tasks; добавлен этот отчёт.
Runtime, исторические Days 27–29 и Weeks 1–5 не изменены.
