## 1. Context preparation seam and legacy behavior

- [x] 1.1 Ввести минимальные ContextPolicy/PreparedHistory и default FullHistoryContextPolicy в SimpleAgent, сохранив ownership busy/generation/validation/commit; проверить existing test_agent/test_agent_adapter и exact roles/text/order/config/call-count assertions Day 06–08.
- [x] 1.2 Выделить generation без session/store для normal и diagnostic calls, не меняя overflow probe; проверить normal outcome validation и test_token_lab probe tests, включая completed-as-overflow-error.
- [x] 1.3 Добавить Day 09 transient operation/phase result types без manager/global accounting и без расширения legacy HTTP contracts; проверить сериализацию unavailable/not_attempted/attempted phase outcomes и snapshot fields.

## 2. Isolated durable summary storage

- [x] 2.1 Добавить узкий ConversationSummaryStore и SQLite adapter на connection Day 09 с таблицей session_id/summary_text/covered_through_position/config_version; проверить schema/FK, отсутствие таблицы в Day 06–08 databases и сохранение existing raw schema.
- [x] 2.2 Реализовать atomic summary load/save с version/non-empty/pair-boundary/tail validation; проверить real-SQLite reopen, отсутствующую строку, invalid state/version и rollback text+boundary при ошибке commit без paid calls.
- [x] 2.3 Подключить cascade reset/delete и resource ownership без отдельного summary cache; проверить удаление unloaded session после reopen, rollback delete, busy delete, idempotent 204 и отсутствие восстановления удалённого ID.
- [x] 2.4 Подключить config-versioned Day 09 store/manager в lifespan и проверить попарно различные database paths; проверить cross-namespace GET/send/compare/delete и закрытие всех ресурсов при startup failure.

## 3. Rolling summarizer and normal lifecycle

- [x] 3.1 Добавить fixed Day 09 response/summarizer configs gpt-4o-mini и source-only prompt с budget 384; проверить exact payload settings, отсутствие reasoning/current/verifier hints, zero retries и validation completed/non-empty/refusal/incomplete.
- [x] 3.2 Реализовать общий no-write summary candidate builder и RollingSummaryContextPolicy с strict N=4; проверить M=0/2/4/6/8, inclusive pair boundaries, newly eligible slices и отсутствие вызова при актуальной summary.
- [x] 3.3 Добавить synthetic assistant wrapper и сборку summary+raw tail+current; проверить Unicode/whitespace/roles/order tail, identical FULL/COMPRESSED до compression и отсутствие synthetic message в SQLite.
- [x] 3.4 Связать successful summary persistence с normal generation в SimpleAgent; проверить summary failure/save failure → no response, а response/count/pair failure после summary commit → durable summary и неизменная confirmed raw history.
- [x] 3.5 Сохранять известные phase receipts до validation/persistence и возвращать их при handled Day 09 errors; проверить usage/cost после summary save и pair save failures, cancellation на обеих границах и finally busy release без изменения legacy errors.

## 4. Exact token and operation cost diagnostics

- [x] 4.1 Подключить provider TokenCounter для exact immutable FULL/COMPRESSED payloads и standalone summary block; проверить count/generation payload agreement, identical-payload dedup, malformed counts и non-additive size labeling.
- [x] 4.2 Рассчитать signed delta/percent, boundary/count/tail и actual-context limit checks; проверить negative/zero delta, full=0, FULL>window с пригодным COMPRESSED, compressed overflow, reserve warning и auxiliary size failure без блокировки normal response.
- [x] 4.3 Переиспользовать actual TokenUsage/pricing для каждой summary/response phase с monotonic latency и operation wall time; проверить missing/invalid cached usage, unknown model/tier, independent phase costs, not-attempted vs unknown и отсутствие backend cumulative accounting/runtime_id/journal.

## 5. Side-effect-free comparison and deterministic facts

- [x] 5.1 Реализовать comparison service над immutable raw/config/summary/question snapshot и local catch-up без write path; проверить storage до/после compare и reopen, отсутствие commit question/replies/summary, current exclusion и distinct durable/local summary metadata.
- [x] 5.2 После preparation запускать independent FULL/COMPRESSED count→limit→generation branches параллельно, сохраняя per-branch errors; проверить barrier-based concurrency, отсутствие branch-to-branch inputs, partial failure, catch-up failure с доступной FULL и zero retries.
- [x] 5.3 Ввести конечный Day 09 operation deadline 210s с отменой/ожиданием незавершённых дочерних calls и сохранением завершённой branch; проверить fake-clock/короткими test deadlines освобождение busy, known receipt retention и отсутствие orphan generations.
- [x] 5.4 Создать фиксированные видимые scenario drafts/recipe и question three-facts-v1 для ORBIT-7319/37/Мира с нейтральными acknowledgements и message length<=20000; проверить точные user templates/ordering, отсутствие answers в question и filler без случайного standalone target 37.
- [x] 5.5 Реализовать pre-paid applicability/tail-contamination validation и exact named-field verifier N/3 без LLM judge; проверить repeated early values в обеих tail roles, 137 vs 37, wrong/missing/duplicate/conflicting fields, changed fixture и отсутствие проверки summary как precondition успеха.

## 6. Day 09 API contract

- [x] 6.1 Добавить compression-lab create/get/summary/delete/messages endpoints с безопасными envelopes и операция-ориентированными diagnostics; проверить 201/200/204, 422 extra fields/invalid UUID/input, 404 namespace isolation, 409 busy и read-only restore без OpenAI key/count/repair.
- [x] 6.2 Добавить explicit compare endpoint question/scenario_id с per-branch results и committed=false; проверить no writes, safe scenario_not_applicable до paid calls, snapshot identity, partial metrics и отсутствие raw/instructions/secrets в response/logs.

## 7. Android repository and process-local state

- [x] 7.1 Добавить CompressionLab DTO/API/repository и отдельный HTTP client read=220s/call=240s с no retries, сохранив старые budgets; проверить repository tests для phase/branch/error parsing, exact outbound message/question без history/config и timeout isolation.
- [x] 7.2 Создать CompressionLabViewModel и отдельные config-scoped CurrentSessionStore/Activity key, исключив ID из backup по текущему подходу; проверить save-before-send, read-only restore, отсутствие create на opening/compare без ID и isolation Day 06–08.
- [x] 7.3 Реализовать VM observations/dedup/totals только текущего process, раздельно normal response/maintenance summary/compare preparation/branches и unknown coverage; проверить rotation/navigation retention, no double count, process cold-start empty observations и reset clear без backend runtime accounting.
- [x] 7.4 Реализовать busy/error/unknown send и compare recovery, durable summary metadata refresh и result snapshot freshness; проверить no replay, unknown compare read-only refresh, reset failure, отдельный question draft и сохранение known receipts после failed normal operation.

## 8. Android main, details and navigation

- [x] 8.1 Создать main Day 09 с reusable chat/composer, compact last-normal-context card и details action; проверить UI отсутствие больших diagnostics/summary bubbles, initial not-measured, actual tail vs fixed 4 и positive/negative/zero delta labels.
- [x] 8.2 Создать Details с раздельными context/phase costs/totals, раскрываемыми durable/local summary, explicit compare и factual results; проверить partial branch failure, unavailable score, stale snapshot label и vertical narrow / side-by-side wide rendering.
- [x] 8.3 Добавить видимые fixture draft actions без hidden import/send; проверить, что каждое нажатие только вставляет читаемый текст, отдельный Send выполняет реальный turn и contamination объясняется без ложного N/3.
- [x] 8.4 Подключить Day 09 к каталогу/AppRoot/MainActivity и nested CHAT/DETAILS route с общим VM; проверить toolbar/system Back Details→Chat→каталог, IME priority, scroll/rotation/state retention и отсутствие дополнительных requests при переходах.

## 9. Integration, live experiment and documentation

- [x] 9.1 Выполнить backend pytest для новых compression и existing agent/persistence/token-lab contracts, затем полный разумный backend regression; подтвердить Day 02–08 payload/model/call-count/atomicity/pricing/overflow invariants и отсутствие secrets в изменениях.
- [x] 9.2 Через PowerShell 7 scripts/dev.ps1 последовательно выполнить необходимые Android unit/build и targeted compression UI tests, затем связанный navigation/UI regression после wiring; сохранить реальные результаты и не запускать параллельный Gradle или лишние clean/retries.
- [x] 9.3 Подготовить краткий Day 09 README по трём разделам и обновить README backend/Android с отдельными API/store/timeouts/commands; проверить ссылки и прямо отметить live results как ещё не проверенные до фактического прогона, не дублировать длинный сценарий видео в Day README.
- [x] 9.4 Подготовить окружение через scripts/dev.ps1 status/backend/emulator, отдельно проверить backend с эмулятора и выполнить/получить подтверждение одного явного четырёх-turn + compare live scenario; зафиксировать actual FULL/COMPRESSED counts, N/3 или contamination, maintenance/compare overhead и generation count без обещания положительной net экономии.
- [x] 9.5 Проверить durable raw+summary restart/reset отдельно от runtime UI metrics (offline reopen tests и контролируемый read-only live restore после завершённого запроса); подтвердить отсутствие paid restore/replay и исчезновение Android observations после process death.
- [x] 9.6 Обновить README только фактически полученными/подтверждёнными итогами, выполнить syntax/structure и strict OpenSpec validation, просмотреть scoped git diff/status; не выполнять commit/push/archive без отдельного запроса завершения Day.

### Подтверждение live acceptance

9.4 закрыта по последнему явному подтверждению пользователя: normal context
3485→1907 (1578, 45.3%), summary=2 messages/raw tail=4; итоговый compare
FULL=2/3 и COMPRESSED=1/3 с переданными actual input/output/estimated cost.
Наличие отдельных maintenance summarization usage/cost подтверждено.
Их численные значения, compare-preparation overhead и общее число generation
calls не переданы и не выдумываются; полная net денежная экономия не заявляется.
В соответствии с последним запросом новые provider calls не нужны для закрытия
эксперимента; детали и пределы данных записаны в [validation.md](validation.md).

9.5 закрыта по ручному подтверждению пользователя: session restore/count=4,
отсутствие старых bubbles, очистка runtime measurements/compare results и
отсутствие paid replay. Durable summary после restart успешно прочитана;
reset успешен, старый диалог после reset не восстанавливается.
