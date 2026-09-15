## 1. Reusable Profile domain and persistence

- [x] 1.1 Добавить strict AgentProfile/format/constraints/binding models по design; проверить unit tests valid combinations, ru/en, bounds/name trim, extra/type rejection и совместимость двух explanation flags.
- [x] 1.2 Определить один layout-independent ProfileStore contract с immutable snapshots и create/read/list/edit/select; проверить contract tests на двух owners без MemoryStore/provider imports и без database paths в domain operations.
- [x] 1.3 Реализовать SQLite ProfileStore с atomic profile/binding writes и revisions; проверить create без activation, edit active/inactive, duplicate names, no-op и stale edit/select включая stale no-op.
- [x] 1.4 Добавить strict reopen/schema/reference validation; проверить сохранность profiles/active binding после restart, foreign-owner read/edit/select rejection и fault-injection rollback без silent repair.
- [x] 1.5 Развести reusable profile modules и harness dependencies; проверить состав imports и tests: domain не знает fixtures, result DTO, A/B slots, OpenAI SDK или расположение Memory DB.

## 2. Instructions and existing Memory extension point

- [x] 2.1 Реализовать pure ProfileInstructionsBuilder с фиксированными templates и нейтральной базой; проверить exact output для всех field variants, обоих explanation flags, False semantics и отсутствие конфликта concise base/detailed Profile.
- [x] 2.2 Проверить metadata-only rename/IDs/revisions и отсутствие arbitrary prompt interpolation; unit tests должны подтверждать одинаковые instructions при одинаковых behavioral fields и изменённых name/metadata, включая name с текстом инструкции.
- [x] 2.3 Подключить существующие Memory selection/policy к Day 12, при необходимости узко отделить их от A–E fixtures; проверить прежние Day 11 exact messages/order, Working MVI override, retained inactive sources и snapshot mismatch tests без обобщения MemoryStore.

## 3. Day 12 application composition and lifecycle

- [x] 3.1 Добавить отдельные Day 12 memory/profile adapters и lifespan wiring с fixed config из design; проверить namespace/path isolation, resource close и startup/current без identity creation или provider calls, включая частично подготовленное state.
- [x] 3.2 Реализовать authoritative active-profile resolution и общий owner guard для profile/memory/dispatch operations; проверить stale memory/profile/binding rejection, in-flight edit/select/lifecycle conflicts, освобождение guard при cancellation и отсутствие SQL transaction во время client await.
- [x] 3.3 Добавить typed Day 12 read/list/create/edit/select API; проверить strict bodies, server-controlled identity/revision, foreign owner rejection, create без auto-select и unknown-outcome read/reconciliation без replay.
- [x] 3.4 Подключить explicit memory initialize/write/lifecycle и Profile Switch; проверить exact before/after equality всех memory IDs/layers/revision/snapshot при switch/edit, а также неизменность Profile при New Conversation/New Task/Clear Long-term.
- [x] 3.5 Реализовать ordinary Send через существующий SimpleAgent.run_turn и current Profile/Memory; recording-client tests должны подтвердить автоматическое применение на последовательных Sends и после switch/edit, atomic pair commit, отсутствие synthetic instructions в transcript и сохранение explicit Profile edits при generation failure.

## 4. Controlled fixtures and immutable A/B

- [x] 4.1 Добавить scenario catalog и create-from-template через обычные Profile operations, explicit slot assignment и настоящий seed Send; проверить editable fixtures без name routing/hidden overwrite, raw completed seed pair и отсутствие commit/retry при failed seed.
- [x] 4.2 Реализовать explicit Freeze с exact shared Memory, одной seed pair, A/B revisions и fixed query/config; проверить preconditions, immutable comparison ID, отсутствие exact marker interpolation в query и stale checkpoint после memory/profile изменения либо ordinary Send.
- [x] 4.3 Реализовать A/B probes через SimpleAgent.generate без commit и auto-select; recording-client tests должны подтвердить один и тот же memory/transcript/query/model/settings, отличие только profile-derived instructions, отсутствие A reply в B и неизменность domain state на success/failure/repeated explicit probe.

## 5. Actual request evidence and narrow observations

- [x] 5.1 Добавить request-scoped LlmClient capture и immutable attempt receipt; проверить exact equality inspector evidence и аргументов независимого delegate, used profile/memory revisions, отсутствие secrets и отличие preview/not_dispatched от actual request.
- [x] 5.2 Добавить declared Markdown checks для summary/list limit и teaching headings/order/nonempty sections; проверить ordered/nested lists, backtick/tilde fences, code-only example sections и отсутствие count/heading matches внутри code.
- [x] 5.3 Добавить deterministic no-emoji detector для небольшого документированного набора Unicode code points/простых sequences, достаточного для Day 12 fixtures, и marker-presence diagnostics; проверить положительные/отрицательные примеры объявленного набора, plain digits/non-emoji text, whole-reply scan и узкую трактовку ORION-17/RC-42/Checkout/MVI как literal mentions. Зафиксировать границы покрытия; не строить полный Unicode Emoji compliance engine и не добавлять тяжёлую dependency.
- [x] 5.4 Разделить selection/assembly/adherence/marker/human observations без aggregate score; проверить completed violations, failed/refused/incomplete unavailable outputs, отсутствие hidden retry/LLM judge и невключение human notes/results в model context.

## 6. Android laboratory UI

- [x] 6.1 Добавить scoped typed DTO/API/repository через существующий Retrofit/AppContainer; JVM tests должны проверить serialized formats/constraints/revisions, запрет teaching max_bullets и reject inconsistent snapshot/owner responses без transport retry.
- [x] 6.2 Реализовать screen-level ViewModel с backend-authoritative selection, editor draft и recovery; JVM tests должны покрыть create/edit/select, cold read, busy/stale/unknown outcome, no optimistic activation и no replay.
- [x] 6.3 Добавить typed create/edit screen и active selector с templates через тот же editor; focused UI tests должны проверить custom profile, все поля, совместимые explanation flags, duplicate names и explicit Save/Select.
- [x] 6.4 Добавить Memory summary, компактную подготовку с raw seed review/Freeze, A/B slot/results cards и отдельный ordinary composer; UI tests должны подтвердить explicit profile switching, отсутствие auto-probe, historical snapshot labels и независимость Memory от selection.
- [x] 6.5 Добавить inspector actual receipt, раздельные checks и optional human notes; UI tests должны показать correct input + failed output, unavailable вместо fake score, used profile revision после edit и отсутствие generic prompt editor.
- [x] 6.6 Подключить Day 12 destination/catalog/title и русские labels; navigation/UI tests должны проверить main/editor/inspector/каталог round trips, rotation/drafts/scroll/in-flight no replay; сохранить существующие accessibility tests. Dedicated increased-font/font-scale check не обязателен для Day 12; expanded font-scale проверку выполнять только при реальном layout regression или отдельной accessibility задаче.

## 7. Integration and regression verification

- [x] 7.1 Запустить focused backend suites новых profile/API/experiment tests и затронутые Agent/Memory regression tests; подтвердить syntax/import correctness, старые exact payload/call-count/commit contracts и отсутствие изменения SimpleAgent.run_turn ради будущей validation.
- [x] 7.2 Выполнить deterministic end-to-end lifecycle/restart test с recording client: seed + A/B + ordinary Sends, switch invariants, storage reopen и partial-setup recovery; проверить zero generation/count/replay на read/restart и неизменность старых namespace данных.
- [x] 7.3 Запустить Android JVM tests, сборку и затронутые UI/navigation tests: preferred path — PowerShell 7 scripts/dev.ps1 unit/build и ui -Test по scripts/README.md; при недоступном pwsh или блокировке ExecutionPolicy разрешены прямые Gradle commands для тех же проверок. Подтвердить актуальные DTO/editor/selector/comparison/inspector/recovery paths без backend/OpenAI в UI tests. Починка PowerShell/tooling не входит в Day 12.

## 8. Live acceptance and documentation

- [x] 8.1 Отдельно подготовить backend/emulator по scripts/README.md: scripts/dev.ps1 остаётся preferred path; при недоступном pwsh или блокировке ExecutionPolicy разрешён fallback — прямые Gradle commands для Android и `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` из backend. Починка PowerShell/tooling не входит в Day 12. Проверить доступность backend с эмулятора; выполнить real seed, review нейтральности, explicit Freeze и A/B на одном snapshot, сохранить фактические selection/assembly/checks/human observations и call count без перезапуска ради идеального score.
- [x] 8.2 Выполнить ordinary Send без style hints, explicit switch и следующий Send, затем restart backend/Android на непустом state; сопоставить before/after profiles/binding/Memory и подтвердить automatic Profile application, zero restore generation/replay и честную потерю runtime dashboard при её наличии.
- [x] 8.3 Создать краткий day-12-agent-personalization/README.md по проектному шаблону и обновить relevant component README; проверить, что результаты основаны только на выполненных/подтверждённых наблюдениях, live blockers указаны честно, команды не дублируются и секретов нет. Повторно выполнить openspec validate day-12-agent-personalization --strict и просмотреть scoped git diff; commit/push только по отдельному explicit запросу.

## Completion verification

- Live acceptance подтверждён пользователем: seed без retry/editing; A/B на одном frozen snapshot, probes без commit и без попадания A в input B. Compact: selection/assembly/summary/no_emoji pass, list_limit FAIL (8/3); Mentor: selection/assembly/headings/nonempty_sections/no_emoji pass. Failure сохранён как model-adherence observation, без повторного прогона ради улучшения результата.
- Ordinary Send и restart acceptance подтверждены пользователем: Profile применяется автоматически до/после explicit switch; records/revisions, active binding и Memory identities/state восстановлены read-only без generation/replay.
- Run при завершении: `python -m pytest tests/test_profiles.py tests/test_personalization.py tests/test_personalization_boundaries.py tests/test_memory_layers.py -q` — 59 passed.
- Reused из текущей реализации без последующих изменений соответствующего поведения: `python -m pytest -q` — 412 passed; `scripts/dev.ps1 unit` — 88 JVM tests; `scripts/dev.ps1 build` — successful; focused `PersonalizationUiTest` (4 tests) и `RootNavigationUiTest` (7 tests) — successful. UI/JVM/recording tests не использовались как подмена live observations.
- Run при завершении: strict non-interactive change validation, main spec validation (21 passed), scoped diff/whitespace и secret-pattern checks. Optional ast-index update пропущен; rebuild не выполнялся.
