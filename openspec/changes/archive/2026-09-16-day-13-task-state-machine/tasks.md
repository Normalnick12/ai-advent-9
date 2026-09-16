## 1. Reusable FSM domain

- [x] 1.1 Добавить strict immutable TaskState/TaskStatus и definition/node/event contracts без provider/harness imports; проверить unit cases identities, unknown status, extra fields, negative/non-integer revisions и отсутствие independent phase/step/action writes.
- [x] 1.2 Добавить definition validation и derived metadata/allowed events; проверить missing initial/target, ambiguous edges, reserved control events, terminal exits, unknown machine version/node и coherent node projections.
- [x] 1.3 Реализовать pure resolver с workflow transitions и Pause/Resume; параметризованно проверить все node/status/event combinations, unchanged invalid snapshots, revision+1, DONE и round trip каждого non-terminal node.
- [x] 1.4 Добавить отдельную harness definition checkout-v1 с утверждёнными пятью nodes и VALIDATION_CONFIRMED; проверить exact metadata/table, initial-to-DONE path и независимость core от fixture import.

## 2. Durable State adapter

- [x] 2.1 Определить layout-independent TaskStateStore create/read/CAS contract и SQLite schema adapter; проверить initial ACTIVE/revision 0, duplicate create без reset и отсутствие зависимостей от Memory/Profile paths.
- [x] 2.2 Реализовать transactional CAS и typed stale/storage errors; проверить competing updates, immutable identities, revision increment и fault-injected rollback без runtime publication.
- [x] 2.3 Добавить strict decode/schema/version/corruption checks; проверить unknown node/machine/status, terminal+PAUSED, invalid revisions, missing versus corrupt и отсутствие silent repair.
- [x] 2.4 Добавить isolated Day13 storage wiring/resource cleanup в composition root; проверить несовпадение paths со старыми namespaces, сохранение inactive task rows и exact ACTIVE/PAUSED/DONE reopen при нуле provider calls.

## 3. Request preparation and actual capture

- [x] 3.1 Добавить pure TaskStateRenderer с workflow authority и PAUSED guidance; проверить deterministic node projection, отсутствие semantic task_id/revision/Memory interpolation и независимость от stores/provider/preparation object.
- [x] 3.2 Добавить небольшой prepare_agent_request/PreparedAgentRequest поверх existing Memory policy/Profile renderer; проверить exact instructions order и active-only messages/query, immutable inputs, Working override и отсутствие State в Memory/transcript.
- [x] 3.3 Выделить/переиспользовать provider-neutral capturing client; recording delegate должен видеть ровно captured messages/config, а targeted Day12 tests должны подтвердить прежние receipts/payloads/call counts.
- [x] 3.4 Добавить immutable attempt/last-transition observations с раздельными storage/selection/assembly/human adherence и not_dispatched/unavailable; проверить historical receipts после mutations и отсутствие observations/oracles в input.

## 4. Day13 application service and API

- [x] 4.1 Добавить explicit initialization, component readiness и initialize-state для current task; API tests должны подтвердить read-only startup, missing setup gate, partial failure между stores, idempotent completion без reset и без replay New Task.
- [x] 4.2 Добавить current/task ownership resolution и event endpoint с expected references/CAS; проверить foreign/inactive/stale/direct-state/unknown requests, exact allowed_events и ноль provider calls для всех FSM operations.
- [x] 4.3 Скомпозировать existing Memory lifecycle и typed Profile operations; проверить New Conversation same State, New Task initial State, retained inactive records, Profile select/edit и Clear Long-term без State changes.
- [x] 4.4 Подключить ordinary Send к existing run_turn и current non-committing probe к generate без State branches в SimpleAgent; проверить completed/failed/incomplete/refused outcomes, paused pair commit, unchanged State и отсутствие output-derived events/retries.
- [x] 4.5 Добавить единый application guard, safe errors и unknown-outcome read recovery; проверить concurrent Pause/lifecycle/profile writes during generation, cancellation освобождает guard, SQL transaction не удерживается на provider await и dispatch выполняется не более одного раза.

## 5. Deterministic cross-subsystem acceptance

- [x] 5.1 Проверить pause-any-stage matrix на настоящих Memory/Profile/State stores: same node, revision+2, точное равенство Working/Long-term/Profile/binding/IDs/Short-term/Memory snapshot и ноль provider calls.
- [x] 5.2 Проверить controlled planning/execution/validation requests с same Memory/Profile/query/config через recording client и explicit events; assert, что отличается только State section, probes не commit-ятся и previous outputs отсутствуют.
- [x] 5.3 Воспроизвести весь two-New-Conversation flow deterministic integration test с обязательным execution Send и различимыми execution/status reply markers; подтвердить настоящую committed pair S0 до Pause, проверить empty pre-turn history и отсутствие S0/S1 transcript в final actual request, unchanged State после каждого из трёх ordinary Sends и отдельный IMPLEMENTATION_READY.
- [x] 5.4 Проверить reopen и partial/unknown-outcome recovery с новым service instance, сохранение domain data без replay/fake observations; targeted shared Agent/Day11/Day12 regression tests должны подтвердить старые namespace/payload/commit contracts.

## 6. Android laboratory

- [x] 6.1 Добавить strict DTO/Repository и AppContainer wiring для current/setup/events/lifecycle/messages/probe; JVM tests должны проверить source identities/revisions, partial readiness, errors и отсутствие Android transition table.
- [x] 6.2 Добавить отдельный Day13 ViewModel с backend-confirmed state, busy/recovery и composer; JVM tests должны проверить paused Send, explicit Resume, stale/lost response -> read без replay и отсутствие optimistic progress.
- [x] 6.3 Добавить compact main/setup/State card/allowed event buttons/Pause-Resume/New Conversation-New Task/session count/response; scoped UI tests должны покрыть ACTIVE/PAUSED/DONE, readiness gate и доступный paused composer.
- [x] 6.4 Добавить inspector actual snapshots/sections/request/outcome/conversation_committed и last transition, optional human notes; UI tests должны различать historical/current, preview/actual, not_dispatched/unavailable без aggregate score.
- [x] 6.5 Добавить Day13 catalog/navigation/presentation и сохранение draft/scroll/attempt на rotation; проверить scoped navigation/UI tests, two-New-Conversation controls, narrow screen/IME/insets и изоляцию старых Days.

## 7. Integrated checks and separate live acceptance

- [x] 7.1 Выполнить необходимые backend syntax/tests, Android JVM/build и затронутые UI tests по component docs; preferred path — PowerShell 7 `scripts/dev.ps1`. При недоступном `pwsh` или блокировке ExecutionPolicy разрешить прямые Android Gradle commands для тех же tasks; исправление PowerShell/tooling вне scope Day 13. Зафиксировать команды/результаты, не запускать конкурирующий Gradle, не повторять успешные проверки неизменного кода и не запускать live provider в offline suite.
- [x] 7.2 Подготовить отдельный live run: preferred запуск через PowerShell 7 `scripts/dev.ps1`; при недоступном `pwsh` или блокировке ExecutionPolicy использовать `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` из `backend`, без исправления PowerShell/tooling в scope Day 13. Проверить backend status и доступ с эмулятора, явно сохранить Working fixture/выбрать Compact Engineer при fixed empty Long-term и unchanged config, применить REQUIREMENTS_READY/PLAN_APPROVED; readiness и нулевые setup/event calls должны быть видны перед generation.
- [x] 7.3 Выполнить live EXECUTION_IMPLEMENT/ACTIVE -> обязательный ordinary execution Send -> подтвердить реальный committed transcript S0 -> Pause -> New Conversation #1 -> ordinary «Где мы остановились?» -> New Conversation #2 -> empty Short-term -> Resume -> ordinary «Продолжим»; сохранить реальные input/outcome observations и human assessment, проверить отсутствие обеих inactive histories и State EXECUTION_IMPLEMENT/ACTIVE после ответа. Provider failure не отмечать как passed acceptance и не скрывать автоматическим retry.
- [x] 7.4 Подтвердить отдельно formal progress/call budget: IMPLEMENTATION_READY только explicit event, никакой auto-transition от reply; записать фактические calls (ровно 3 generation calls при успешном flow: execution Send, status Send, continuation Send; setup/events/lifecycle/read — 0 provider calls) и deterministic reopen evidence без обязательного live restart/video шага.

## 8. Documentation and completion boundary

- [x] 8.1 Создать day-13-task-state-machine/README.md с разделами «Суть эксперимента», «Что проверяет», «Результаты» и ссылками на components; записывать только фактические проверки/подтверждённый live итог, при отсутствии явно указать not-run. Добавить ordered относительную ссылку в корневой README и проверить target existence/no duplicates.
- [x] 8.2 Обновить backend/Android component README только необходимыми Day13 setup/API/verification details, описать partial setup и layout-independent storage boundary; проверить ссылки, отсутствие секретов и отсутствие дублирования длинных инструкций в Day README.
- [x] 8.3 После реализации сверить scoped diff и acceptance evidence с specs, выполнить openspec validate day-13-task-state-machine --strict и отразить фактический статус tasks; не добавлять Invariants/Validator/retries/Playground, не archive/commit/push без отдельного запроса на завершение дня.
