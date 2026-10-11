# Day 30 — дополнительная локальная конкурентная пара, 2026-10-11

## Read-only review предыдущей пары

Исходный вопрос B установлен по локальному сценарию предыдущего запуска.
Текст вопроса и ответов не переносится в технические метрики: это был вопрос
о поведении CheckoutCoordinator при отклонённом платеже. History пустая.
Сохранённые метрики: запрос Ollama 7232 bytes, prompt_eval_count=1280,
eval_count=2048, done=true, done_reason=length, HTTP 502 invalid_model_response.
Offline-пересборка только входа неизменным packer подтвердила 7232 bytes, 4 chunks
из checkout.md, num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m.
Это проверка текущего неизменённого кода, а не повторная генерация.

В grounded.parse проверка done/stop предшествует JSON/schema/citation validation.
Установленная причина 502 — достижение лимита выхода (ровно 2048, не превышение).
Последующие проверки содержания не выполнялись; нельзя исключить другие дефекты
непроверенного ответа. Raw output B не сохранён. Повторы либо просто длинное
содержание неизвестны и не восстанавливаются предположениями.

Два допуска, два upstream completion, отдельные request_id, health под нагрузкой
и terminal cleanup подтверждены предыдущими метриками. Признаков ошибки HTTP
admission/передачи или несоответствия validation контракту не найдено. HTTP-блокера
для отдельно разрешённой пары не установлено. Предыдущий FAIL не изменяется:
[исходное evidence](live-concurrent-2026-10-11.md).

## Перспективное разрешение и бюджет — до нового live

Исходный бюджет: 6 chat generations, использованы 4 (первый диалог 2, первая
конкурентная пара 2). Пользователь явно увеличил общий потолок до 8:

- 2 — первоначальный диалог;
- 2 — первая конкурентная пара;
- 2 — одна дополнительная локальная пара с более узкими синтетическими вопросами;
- 2 — резерв remote-демонстрации, требующей отдельного разрешения.

Новая пара — отдельная проверка, не воспроизведение исходного теста. Вопрос A
проверяет ранний возврат EmptyCart до PaymentGateway; B — корзину и навигацию
при отклонении платежа. Используются дословные вопросы текущего разрешения.
Настройки, model digest, prompt/schema/RAG/validation/limits не меняются.
Никаких retries, warm-up, дополнительных поколений для перегрузки либо remote.
При новом техническом отказе локальные конкурентные эксперименты прекращаются.

## Preflight и условия запуска

До генерации: Ollama 0.40.2, cloud disabled=true, единственный listener
127.0.0.1:11434, parallel=1, штатный max_queue=512. Настройки не менялись.
Coder digest: `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
Нет резидентных моделей, runner-процесса или активных клиентских соединений;
последняя предыдущая пара имела два terminal completion. Это совокупность
наблюдений об отсутствии outstanding inference, не гарантия одного `/api/ps`.
GPU до запуска: 693/694/694 MiB, 4/4/10%. Порт 8030 свободен.

Workspace и единственный Markdown совпадают с прежними synthetic fixtures,
Knowledge index fresh. Bearer и allowlist остались в ignored `.local/day30`;
секрет получен из прежнего DPAPI-файла. HTTP запущен только на 127.0.0.1:8030;
health/readiness перед парой — 200. Индексации/embeddings/warm-up — 0.

Production code не менялся. Отдельный временный observer делегировал исходным
operation/transport, проверял соответствие дословного вопроса клиенту и фиксировал
только client label, bytes/counts/options/times/done/validation и digest synthetic
result. Локальный guard разрешал максимум 2 вызова этой пары и учитывал уже
использованные 4. Наблюдатель не подменял model output или validation.

## Единственная дополнительная пара

Два независимых HTTPX клиента, отдельные TCP-соединения, общий стартовый барьер,
Bearer auth, по одному POST /v1/chat с history=[]; повторных отправок нет.
В обоих фактических upstream payload подтверждены num_ctx=8192, num_predict=2048,
temperature=0, seed=28, четыре текущих фрагмента checkout.md и выбранный Kotlin.
История, schema, prompt и retrieval не модифицировались ради результата.

| Метрика | A: EmptyCart | B: declined payment |
|---|---:|---:|
| request_id | 5f16b2009032444abc6c1601fbb6b638 | 0bd217243cef4e559de3e1f8a3664ef5 |
| Старт, client-relative seconds | 0.051203 | 0.051058 |
| Завершение, client-relative seconds | 12.127997 | 22.952247 |
| HTTP wall | 12.076784 s | 22.901179 s |
| HTTP status | 200 | 200 |
| Ollama request bytes | 7268 | 7248 |
| Ollama done / reason | true / stop | true / stop |
| Mechanical validation | passed | passed |
| Prompt / output tokens | 1291 / 828 | 1289 / 904 |
| Provider total | 12.021707 s | 22.847306 s |
| Provider load | 2.300706 s | 2.300775 s |
| Provider prompt evaluation | 0.294466 s | 0.172097 s |
| Provider generation evaluation | 9.414437 s | 10.613458 s |
| Application generation wall | 12.026672 s | 22.850313 s |
| Retrieval wall | 0.002342 s | 0.002383 s |
| Selected / omitted chunks | 4 / 0 | 4 / 0 |

Два `operation_admitted`, наблюдаемые active=2/max_active=2 на offset=0.263438 s,
оба client futures ещё выполнялись. Health при двух занятых слотах: HTTP 200,
1.179 ms. Интервалы HTTP перекрываются, request_id различны. Observer привязал
фактический question к своему client label; SHA-256 канонического synthetic result
каждой operation совпал с result, полученным соответствующим HTTP-клиентом.
Перестановки/смешения результатов в этой паре не обнаружено.

Ollama log содержит ровно два завершённых POST /api/chat 200, новых /api/embed нет.
parallel=1 и runner n_seq_max=1 наблюдаемы. Точная глубина/длительность очереди
недоступна; разность таймингов не объявляется измеренным queue wait. Перекрытие HTTP
не является доказательством параллельного inference. Provider load для двух calls
не трактуется как две независимые холодные загрузки модели.

GPU снимок во время пары: 5782 MiB / 95%, после: 5796 MiB / 1%.
Это отдельные снимки, не непрерывный мониторинг или гарантированный пик.

После завершения active=0, max_active=2, recovery_required=false.
В /v1/status ready=false из-за истечения 5-секундного readiness cache;
это не новый отказ probe (readiness до пары была 200).
HTTP штатно остановлен: service_stopped active=0 recovery=False, listener8030
отсутствует. Ollama не перезапускалась и остаётся loopback; модель может оставаться
резидентной до окончания прежнего keep_alive=5m.

## Privacy и evidence

Локальные metadata-only файлы находятся в ignored `.local/day30/concurrent-narrow/`:
preflight/readiness, client-metrics.jsonl, observations.jsonl, server-metadata.log,
server-budget.json и postflight/final-status. Нет transcript/raw output файлов.
Полные synthetic ответы просмотрены только в stdout клиента для смыслового review.
Штатный service log содержит safe request_id/route/status/times/admission/recovery
и lifecycle. Проверка не обнаружила HTTPX INFO, токен, вопрос, Kotlin или Markdown
в service log. Corpus/index hashes до/после пары совпадают.

## Verdict, сравнение и границы выводов

Technical PASS обоих клиентов и дополнительной пары: два допуска, перекрытие,
health, раздельность, done/stop и механическая validation. Задача 6.3 закрыта
по этому отдельно разрешённому сценарию. Первая пара остаётся HTTP concurrency
PASS / два успешных ответа FAIL: A 200, B 502/length. Её evidence не переписано.
Новые вопросы и входы отличаются; это не доказательство исправления старого
вопроса B, устойчивости любых запросов или устранения риска length=2048.

Предварительный semantic review:

- A **FAIL**: ранний EmptyCart распознан, но затем ответ неверно отрицает вызов
  PaymentGateway в продолжении метода и неверно утверждает, что успешные шаги
  не выполняются. Координация ошибочно смешана с отсутствием участия в оплате.
- B **PARTIAL**: правильно описаны PaymentDeclined, отсутствие очистки корзины
  и перехода на чек. При этом разделение ответственности неточно передано как
  отсутствие участия координатора в обработке, хотя он вызывает collaborator.

API semantic_status остаётся not_evaluated; это отдельный предварительный review,
а не изменение механического валидатора. Coder 7B по-прежнему технический кандидат;
Day 29 **NO SUITABLE PROFILE CONFIRMED** неизменён. Два клиента одного Windows-ПК
не заменяют две физические машины или remote-демонстрацию.

Фактически использовано **6 из нового потолка 8** generations: 2+2+2.
Оставшиеся 2 зарезервированы для отдельно разрешаемой remote-пары. Новых embeddings
0; прежняя единственная индексация учитывается отдельно и не повторялась.
Локальные эксперименты завершены после этой пары; Tailscale/remote/video и
commit/push/archive не выполнялись. OpenSpec после закрытия 6.3: **29/33**,
оставшиеся 7.1–7.4 относятся к отдельному remote/final этапу.

## Финальные проверки

- OpenSpec strict validation **PASS**; task count **29/33**.
- Python syntax локального test harness, ссылки изменённых Markdown и единственная
  ссылка Day 30 в корневом README — **PASS**; git diff --check без ошибок.
- Из 888 исходных non-ignored файлов изменены только Day 30 README, текущие
  design/tasks; добавлено это evidence. Остальные 885 hashes неизменны, удалений нет.
  Production runtime, prompts/schema/RAG, fixtures, прошлые live reports и Days 27–29
  не менялись. Временный harness и локальные метрики остаются ignored.
- Focused offline tests в этом этапе повторно не запускались: production code и
  их входы не изменились. Прежний logging gate **66 passed** остаётся историческим
  результатом предыдущего этапа, не выдаётся за новый прогон.
