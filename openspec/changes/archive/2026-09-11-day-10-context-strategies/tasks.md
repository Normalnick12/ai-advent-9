Финальный статус: 66/66 tasks completed. Section 12 закрыт по explicit user live/video/restart/reset confirmation; exact observations и ограничения coverage — в [validation](validation.md#final-v3-controlled-live-acceptance-user-confirmed). Historical v1/v2 evidence отделено от final v3 comparison.

## 1. Fixed contracts and shared Agent seams

- [x] 1.1 Зафиксировать Day 10 config/scenario/schema versions, N=6 и response/extraction/evaluation settings по design; проверить config tests и отсутствие пользовательских model/settings fields.
- [x] 1.2 Добавить optional Structured Output format в общий payload builder без изменения default text payload; проверить existing Day 06–09 exact-payload/call-count tests и exact new schema payload.
- [x] 1.3 Добавить concrete Day 10 preparation/commit path через один SimpleAgent с reuse generate/validation; проверить ordinary Send вызывает общий generation primitive, освобождает guard при failure/cancellation и не создаёт отдельные Agent implementations.

## 2. Isolated durable runs and recovery metadata

- [x] 2.1 Реализовать новый config-versioned Day 10 SQLite schema/store и scoped immutable run identity; проверить create/load/delete/reopen, startup path isolation, wrong strategy/config и отсутствие migration старых files.
- [x] 2.2 Реализовать atomic pair + scenario step + revision и strict exact raw ordering; проверить rollback/failed COMMIT, Unicode/LF preservation, incomplete pair/corrupt schema rejection и RAM update только после durable success.
- [x] 2.3 Реализовать run GET с confirmed steps/revision/latest replies/actual state и отдельный owned raw-message read; проверить no provider calls, stale revision и восстановление lost-HTTP committed Send без replay.
- [x] 2.4 Добавить Day 10 error envelopes и strict request validation для run/message/target/version; проверить 404 wrong namespace, distinct busy/revision/config errors, 422 extra history/facts/settings и безопасный storage error.

## 3. Sliding Window

- [x] 3.1 Реализовать SlidingWindowContextPolicy с фиксированными 6 confirmed messages и current user сверх N; проверить empty/<N/=N/>N и exact roles/order на fake provider.
- [x] 3.2 Отделить full raw audit от assembled provider input и Day 10 preflight; проверить out-of-window messages отсутствуют во всех generation/count payloads, no fallback и maintenance=0 после restart.

## 4. Structured Facts lifecycle

- [x] 4.1 Реализовать typed FactState `(scope,key)` с kind/value/set-or-cleared/provenance; проверить add/replace/clear/no-op, A/B coexistence, duplicates, strict scalar types и active count без tombstones.
- [x] 4.2 Реализовать fixed gpt-4o-mini strict Structured Output extractor; проверить exact previous-facts + current-user input, отсутствие assistant/full raw/evaluation outputs и SDK/application retries.
- [x] 4.3 Реализовать patch validation по current raw assertions/evidence без hidden expected table; проверить unsupported value/scope/conflicting operations reject, empty patch допускается и пропущенные facts не достраиваются backend.
- [x] 4.4 Реализовать candidate facts + raw tail 6 + current user assembly ниже system/developer priority; проверить exact payload, clear/correction precedence, отсутствие evidence transcript и values в fixed instructions.
- [x] 4.5 Реализовать ONE transaction для raw pair/resulting FactState/step/revision; проверить extraction failure -> no response, response failure -> no facts/pair, storage rollback/reopen и отсутствие transaction во время provider await.
- [x] 4.6 Добавить read-only facts endpoint и восстановление exact state; проверить restart/provenance/config mismatch, отсутствие mutation/LLM при inspector reads и extraction usage receipt при later failure.

## 5. Branch topology and guard

- [x] 5.1 Реализовать root, checkpoint после confirmed Turn 6 и атомарное создание ровно A/B; проверить pair boundary, единственную копию prefix, repeated checkpoint behavior и durable reopen.
- [x] 5.2 Реализовать prefix+local resolver с explicit immutable target и local pair commit; проверить exact A/B payloads, source IDs, no leakage и отсутствие mutable history swap.
- [x] 5.3 Запретить root continuation после checkpoint, third/nested/arbitrary-parent/merge/rebase operations; проверить rejection до provider/storage mutation.
- [x] 5.4 Реализовать bounded run guard: mutation exclusion и два independent named evaluation slots одной snapshot revision; проверить concurrent Send/reset/checkpoint races, same-variant busy, finally cleanup/cancellation и независимость других runs.
- [x] 5.5 Реализовать whole-run reset с cascade evaluation outputs/facts/prefix/branches; проверить reset после restart, unloaded run delete, idempotent absence и no provider calls.

## 6. Exact controlled scenario and deterministic verifiers

- [x] 6.1 Добавить canonical meeting-rooms-v1 catalog из восьми exact spec fixtures, titles и compact descriptors; проверить UTF-8/LF bytes без trailing LF, full-text Send и отсутствие hidden expected answers в catalog/provider inputs.
- [x] 6.2 Реализовать durable scenario applicability/order/target validation: 1–6 root, checkpoint, 7A/8B либо linear; проверить real pairs, edited/free-form/wrong-order/noncanonical history без synthetic substitution и корректный 8/8 progress.
- [x] 6.3 Реализовать final schema из 11 nullable typed fields и strict duplicate-key decoder; проверить whitespace/key order, 37 != 137, bool != integer, null != 0, exact strings/scopes и отсутствие answer-valued schema enums/defaults.
- [x] 6.4 Реализовать deterministic quality A/B N/11 с expected values только в verifier; проверить wrong-variant values, valid all-null 0/11, invalid/refused/incomplete -> unavailable и exclusion reminders из denominator.
- [x] 6.5 Реализовать retention reducer над actual assembled sources/serialized facts по closed grammar design; проверить corrections/clear/scopes, exact assistant restatements, conflicts, unknown grammar -> unavailable и отсутствие audit fallback.
- [x] 6.6 Реализовать independent branch source-ID invariant; проверить opposite-source intersection=empty, violation blocks provider и wrong model answer не объявляется storage leakage.

## 7. Side-effect-free final evaluation and outputs

- [x] 7.1 Реализовать immutable final snapshot identity для completed 8-turn run и two explicit A/B endpoints с фиксированными questions; проверить same base context Window/Facts, exact prefix/local Branching, no hidden answers и pre-provider readiness rejection.
- [x] 7.2 Реализовать independent/parallel A/B generation через общий SimpleAgent.generate без extractor/commit interface; проверить reverse completion order и concurrent calls дают те же input payloads, ни reply/question не попадает другому, no pair/facts/step/revision mutation.
- [x] 7.3 Реализовать per-variant status/quality/retention/isolation и partial failure handling; проверить A failure не отменяет B, same running variant busy, no automatic retry и no transaction during provider awaits.
- [x] 7.4 Сохранять last evaluation result/verdict отдельным output с snapshot/revision/attempt, не billing journal; проверить restore без provider, failed output COMMIT, matching-attempt reconciliation и отсутствие outputs в любом source builder/extractor.

## 8. Token accounting

- [x] 8.1 Подключить existing TokenCounter к exact Day 10 assembled payload включая final schema; проверить preflight source distinction, count failures/overflow без fallback и no count на reads/switch/dashboard.
- [x] 8.2 Реализовать operation receipts с response/extraction phases и actual TokenUsage; проверить failed attempts, extractor usage после failed response, not-attempted vs unknown и no new calls в старых namespaces.
- [x] 8.3 Реализовать runtime totals/dedup по attempt+phase, coverage и partial known total; проверить total/input/output/cached/reasoning без double count, repeated read не суммируется, explicit retry учитывается отдельно.
- [x] 8.4 Проверить полный offline controlled call budget: Window 10 response, Facts 10 response+8 extraction, Branching 10 response, checkpoint/switch 0; подтвердить evaluations не меняют conversation counts и total 38 не выдаётся за live observation.

## 9. Android repository and independent state

- [x] 9.1 Добавить Day 10 DTO/Repository и AppContainer wiring с отключёнными transport retries; проверить MockWebServer tests exact raw body, target/revision/version/attempt validation и no history/settings fields.
- [x] 9.2 Реализовать screen-level map трёх independent run states и versioned ID/strategy/branch preferences; проверить selector не создаёт/migrates runs и callback обновляет только originating run/branch.
- [x] 9.3 Реализовать durable progress/latest state restore и unknown Send reconciliation; проверить confirmed lost-response step не повторяется, absent step требует explicit action, busy/config/corrupt recovery и no automatic replacement/replay.
- [x] 9.4 Реализовать два independent evaluation states и runtime receipt totals; проверить возможность явно запустить B при running A, reverse completion, partial results, matching attempt restore и потерянный accounting -> incomplete.
- [x] 9.5 Реализовать objective management counters с separate common/optional/recovery actions; проверить Window/Facts=0 mandatory, checkpoint=0/1, actual branch switches и missing local observations != 0.

## 10. Scenario-first Compose UI

- [x] 10.1 Реализовать main selector/state/stepper/latest response/dashboard action без центрального transcript/composer; проверить UI fixtures preparation и Send раздельны, Next explicit, compact post-send card и exact original disclosure до/после Send.
- [x] 10.2 Реализовать Window band/card и Facts scoped rows/read-only inspector с cleared section; проверить counts, no expected-value substitution, last-context vs current labels и unavailable retention/token rendering.
- [x] 10.3 Реализовать explicit checkpoint и simple A/B topology/selector с prefix/local counts; проверить Turn 7 A/Turn 8 B, independent latest responses, no provider calls на switch и whole-run reset wording.
- [x] 10.4 Добавить main actions «Проверить ТЗ A/B» после 8/8 с question disclosure и independent progress; проверить evaluation не создаёт ninth step/bubbles и один click не запускает другую evaluation.
- [x] 10.5 Реализовать read-only dashboard из трёх compact cards с quality/retention/tokens/coverage/actions/isolation и короткими qualitative descriptions; проверить no calls при открытии, unknown != zero bar, отсутствие USD/debug clutter.
- [x] 10.6 Добавить Day 10 catalog/destination/Russian strings и main/dashboard/inspector Back; проверить девять cards 02–10, matching titles, backend-unavailable navigation и независимость старых labs.
- [x] 10.7 Выполнить targeted Day 10 UI checks: navigation/config recreation/process restore, small-screen и ordinary responsive layout, system bars/scroll/controls usability; подтвердить сохранение prepared text/scroll/results, отсутствие obvious overlap и duplicate provider operations. Landscape проверять только в уже покрывающем его обычном targeted UI flow либо при выявленном риске. Отдельный manual/dedicated large-font/font-scale smoke не является обязательным acceptance criterion; применять verification policy из design, не добавляя и не запуская дублирующих проверок.

## 11. Integration regression and documentation

- [x] 11.1 Выполнить полный backend pytest по component README; подтвердить Day 02–09 exact payloads/calls, Day 08 pricing/count/overflow, Day 09 rolling summary и новые storage/evaluation tests без regressions.
- [x] 11.2 Выполнить Android JVM tests и debug build через PowerShell 7 scripts/dev.ps1 unit/build последовательно; подтвердить successful results и отсутствие direct/concurrent Gradle launches.
- [x] 11.3 Выполнить итоговый полный UI regression через scripts/dev.ps1 ui для связанной navigation/UI области; подтвердить старые Day 02–09 и новые Day 10 flows без backend/OpenAI dependencies fake tests.
- [x] 11.4 Добавить краткий day-10-context-strategies/README.md по project template и component README для новых API/run commands; проверить Markdown links/structure и честное «live не проведён» до фактического acceptance.
- [x] 11.5 Сверить implementation с пятью capability deltas, non-goals и scoped diff; выполнить strict OpenSpec validation и проверки синтаксиса изменённых файлов без auto commit/push/archive.

- [x] 11.6 Перевести immutable Day 10 config identity backend и Android versioned preferences/restore на `day10-gpt4o-mini-n6-v2` и новый SQLite path; сохранить scenario/schema/model/N и generation settings кроме extraction instructions. Не переносить v1 IDs/results/receipts в v2 dashboard; create только при explicit Send.
- [x] 11.7 Заменить только extractor instructions exact текстом v2 из design: current assertions first, previous facts только operation reference, same-identity scope/key/value/evidence, full-line evidence и self-check. Не менять validator/schema/operations/atomicity, не достраивать omissions.
- [x] 11.8 Добавить deterministic preservation/isolation tests на временных v1/v2 stores и Android preferences: v1 bytes/runs сохраняются при v2 startup/read/reset/reopen, чужие IDs/config/results не открываются и не смешиваются, fallback/migration/automatic provider calls отсутствуют. Реальную v1 БД тестами не трогать.
- [x] 11.9 Добавить и выполнить targeted fake-provider tests exact v2 prompt/input и unchanged payload settings; явно проверить запрет previous-only offline_schedule при current style/email_reminders, borrowed evidence, прежние reasons/index/whole-patch rejection, no-op/clear и честный omission. Выполнить связанные Android Repository/ViewModel tests versioned restore/dashboard через scripts/dev.ps1; не повторять весь full/UI matrix без выявленного regression risk. Fake tests не доказывают live compliance.
- [x] 11.10 Обновить truthful implementation/validation и component/Day documentation: v1 failure и Window success исторические, v2 deterministic results только фактические, live v2 pending. Выполнить strict OpenSpec validation, syntax и Markdown/link checks; не запускать live/reset v1/commit/push/archive и не закрывать Section 12.

- [x] 11.11 Реализовать extraction schema facts-v2 без op: strict scope/key/kind/state/value/evidence, exact prompt v3 из design и current_user-only input. Previous FactState остаётся только у backend; raw/history/assistant/evaluation/expected answers исключены. Старый op output отклоняется, не конвертируется.
- [x] 11.12 Реализовать strict whole semantic patch validation и узкий deterministic reducer: set add/update/no-op, active clear, repeated clear no-op, never-existing clear reject. Сохранить exact source/type/value/evidence/duplicate checks, no-op provenance, отсутствие wrong-value repair/omission reconstruction, atomic candidate+pair/step/revision и usage при failure.
- [x] 11.13 Перевести config backend/Android preferences на day10-gpt4o-mini-n6-v3 и новый store path, сохранив v1/v2 databases/IDs/results/preferences без migration/delete/import/fallback. Не менять model/scenario/evaluation schema/N, Sliding/Branching/evaluation/metrics или UI layout; new runs только explicit Send.
- [x] 11.14 Добавить/адаптировать targeted deterministic backend tests schema/input/prompt, scoped B ADD независимо от A, different/same typed value, set after cleared, repeated/unknown clear, duplicates/wrong scope/key/type/value/evidence before transition, no partial commit и failures/restart. Проверить historical op rejection, v1/v2/v3 isolation и Android versioned state/metadata через scripts/dev.ps1 targeted JVM; подтвердить old shared-payload contracts. Fake tests не доказывают live semantic correctness; без UI/layout изменений не повторять full UI/large-font matrix.
- [x] 11.15 Обновить truthful validation/component/Day documentation: v1/v2 failed live evidence отдельно, фактические v3 deterministic results отдельно, v3 live pending. Выполнить strict OpenSpec validation, syntax и Markdown/link checks; не запускать provider/retries/manual acceptance/reset old runs/commit/push/archive и не закрывать Section 12.

## 12. Separate live acceptance and video evidence

- [x] 12.1 Только после implementation v3 и отдельного явного разрешения подготовить live окружение через scripts/dev.ps1 status/backend/emulator и отдельно проверить backend из эмулятора; зафиксировать готовность, не называя /health доказательством OpenAI.
- [x] 12.2 Провести новый controlled live experiment с чистыми Window v3, Facts v3 и Branching v3 runs с 8 явными Sends, checkpoint/routing где нужно и двумя explicit side-effect-free evaluations; записать actual outputs, quality/retention, known usage/coverage и actions без заранее заявленного победителя.
- [x] 12.3 Проверить live restart/restore facts/topology/evaluation outputs, независимость A/B и whole-run reset только v3 без replay; v1/v2 namespaces/runs не изменять; отдельно зафиксировать expected loss/incomplete runtime token coverage при process death.
- [x] 12.4 Подготовить/зафиксировать короткое видео финального v3 comparison по workflow design: selector, один raw disclosure, Window eviction, Facts correction/clear, checkpoint/A/B, explicit evaluations и dashboard; подтвердить каждый показанный Send настоящий.
- [x] 12.5 Обновить Day README и change validation evidence только проверенными live v3 наблюдениями или явным подтверждением пользователя; сохранить historical Window success и Facts v1/v2 failed observations отдельно, без смешивания с v3 dashboard; проверить разделение fake tests/actual model results и предел вывода одним controlled experiment.
