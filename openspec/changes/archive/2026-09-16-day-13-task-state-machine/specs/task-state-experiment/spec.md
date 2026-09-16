## Purpose

Определяет Day 13 Checkout лабораторию поверх существующих Memory, Profile и Agent primitives: явное управление task workflow и наблюдаемое продолжение после двух смен conversations без старого transcript.

## ADDED Requirements

### Requirement: Checkout uses one explicit versioned workflow

Day 13 SHALL поддерживать одну definition checkout-v1 со следующими nodes и metadata:

| Node | Phase | Step | Expected action |
| --- | --- | --- | --- |
| PLANNING_REQUIREMENTS | planning | collect_requirements | provide_requirements |
| PLANNING_APPROVAL | planning | approve_plan | approve_plan |
| EXECUTION_IMPLEMENT | execution | implement | continue_implementation |
| VALIDATION_CHECK | validation | validate | provide_validation_result |
| DONE | done | complete | none |

Initial node SHALL быть PLANNING_REQUIREMENTS, единственный terminal node SHALL быть DONE. ACTIVE workflow mappings SHALL быть REQUIREMENTS_READY: PLANNING_REQUIREMENTS -> PLANNING_APPROVAL; PLAN_APPROVED: PLANNING_APPROVAL -> EXECUTION_IMPLEMENT; IMPLEMENTATION_READY: EXECUTION_IMPLEMENT -> VALIDATION_CHECK; VALIDATION_CONFIRMED: VALIDATION_CHECK -> DONE. Все события SHALL быть explicit пользовательскими/application confirmations. VALIDATION_CONFIRMED SHALL NOT означать semantic Validator result. Обратные переходы, automatic planning и output-derived events SHALL отсутствовать.

#### Scenario: Explicit confirmations complete the workflow
- **WHEN** initial ACTIVE task последовательно получает четыре допустимых workflow events с актуальными revisions
- **THEN** она проходит ровно объявленные nodes до DONE/revision 4, с нулём provider calls

#### Scenario: Wrong phase confirmation cannot advance
- **WHEN** PLANNING_APPROVAL получает VALIDATION_CONFIRMED либо EXECUTION_IMPLEMENT получает PLAN_APPROVED
- **THEN** event отклонён без changes/calls

### Requirement: State ownership and lifecycle are independent of memory and profile

State SHALL выбираться по current task_id существующего owner/task/session binding без отдельного active-state binding. New Conversation SHALL создавать новую пустую active session, сохранять старую durable inactive и не менять task/Working/Long-term/Profile/Task State. New Task SHALL создавать новые task/session с пустыми Working/Short-term и initial ACTIVE State/revision 0 при готовой подготовке; прежние task/State/conversations SHALL сохраняться inactive. Profile select/edit и Clear Long-term SHALL сохранять State. Pause/Resume SHALL не менять Memory/Profile/identities; ordinary Send SHALL не менять State. Новая task SHALL сохранять owner/Long-term/Profile.

#### Scenario: New conversation preserves a paused task
- **WHEN** New Conversation выполнена для EXECUTION_IMPLEMENT/PAUSED
- **THEN** новая active history пуста, task/state/profile snapshots прежние, прежняя session durable inactive и не выбрана в input

#### Scenario: New task starts its own machine
- **WHEN** New Task успешно подготовлена после progressed task
- **THEN** новые task/session имеют initial State/revision 0 и пустые Working/Short-term, старый State сохранён и не выбран

#### Scenario: Other subsystem operations do not change state
- **WHEN** отдельно выполнены Profile Switch, Profile Edit и Clear Long-term
- **THEN** canonical Task State и его revision остаются побайтово/по значениям прежними

### Requirement: Preparation is explicit and partial setup blocks dispatch

Day 13 SHALL иметь изолированный namespace одного локального demo owner без migration/import старых Days. Read/startup SHALL сообщать независимую готовность Memory, selected Profile и Task State без создания identities, State, fixtures или provider calls. Generation и event operations SHALL отклоняться при incomplete preparation. Явные Initialize/New Task SHALL создавать initial State для соответствующей task; общая транзакция разных subsystem stores SHALL NOT обещаться. При partial failure SHALL отображаться сохранённая часть и missing component, без fake rollback/success. Explicit completion of missing State setup SHALL адресовать уже созданную current task и SHALL NOT создавать ещё одну task или reset существующего State. Invalid/corrupt storage SHALL не считаться missing setup и SHALL не исправляться этой операцией.

#### Scenario: State setup fails after memory task creation
- **WHEN** Memory уже committed новую task/session, но initial State не сохранён
- **THEN** current показывает эти IDs и task-state-not-ready, Send/events не dispatch-ятся; read не создаёт State, пользователь может явно завершить подготовку той же task

#### Scenario: Setup recovery does not replay New Task
- **WHEN** после неизвестного HTTP outcome выполнен read, затем explicit completion недостающего State
- **THEN** используется подтверждённый current task_id; существующий State возвращается без reset, новая task/session не создаётся

#### Scenario: First read and corrupt read are different
- **WHEN** read видит соответственно отсутствующую подготовку либо повреждённый State
- **THEN** первый показывает missing readiness, второй явную storage error; ни один не вызывает generation или silent repair

### Requirement: Every dispatch captures coherent current sources

Каждый Send/probe SHALL на backend разрешать current Memory, active Profile/binding и Task State, проверять expected memory snapshot, task identity, State revision и profile/binding revisions до provider call. Foreign/inactive/stale targets SHALL отклоняться без утечки данных и effects. Conflicting operations SHALL сериализоваться/отклоняться одним application guard в пределах одного owner/worker; SQL transaction SHALL не удерживаться во время provider await. Pause во время выполняющейся generation SHALL возвращать busy, не изображая отмену запроса. Captured snapshots SHALL не изменяться последующими edits/transitions.

#### Scenario: In-flight generation cannot race a state transition
- **WHEN** Send уже захватил sources, а конкурирующий запрос пытается применить event/Pause/New Conversation или edit/select Profile
- **THEN** conflicting operation отклонена как busy, исходная попытка использует прежние snapshots

#### Scenario: Stale state reference prevents dispatch
- **WHEN** request содержит прежнюю State revision либо target не является current task
- **THEN** возвращается conflict/not-found до generation/commit, actual request обозначен not_dispatched

### Requirement: Request preparation keeps three semantic sources separate

Request SHALL включать selected Memory как data context, Profile как behavioral instructions и Task State как отдельную authoritative workflow section. State SHALL NOT помещаться в Working/Long-term или confirmed transcript. Актуальный State SHALL задавать workflow position при противоречии со старой conversation; Profile SHALL задавать оформление, не переходы. Memory selection SHALL сохранять Day 11 правила active-only sources и Working architecture override. Подготовка уже resolved immutable snapshots SHALL быть deterministic, без чтения stores/provider calls и без универсального prompt framework. Query SHALL оставаться текущим user message, metadata/observations/expected answers SHALL не становиться скрытыми input sources.

#### Scenario: Actual input contains a separate state section
- **WHEN** отправлено обычное сообщение для ACTIVE execution
- **THEN** actual instructions содержат EXECUTION_IMPLEMENT/execution/implement/continue_implementation/ACTIVE отдельно от Profile, Memory messages содержат только selected facts и active history с query

#### Scenario: Old planning text does not select the current node
- **WHEN** transcript упоминает planning, а current State равен execution
- **THEN** выбранный и rendered State остаётся execution, старый текст не запускает классификацию или transition

### Requirement: Paused conversation commits independently of workflow progress

PAUSED SHALL разрешать read/inspector, ordinary Send, New Conversation и Resume. Ordinary Send SHALL использовать общий normal conversation lifecycle: только completed пригодный ответ сохраняет настоящую user/assistant pair; failure/incomplete/refusal/cancellation до commit сохраняют прежнюю history. Send при любом status SHALL не применять events и не менять State/Working/Long-term/Profile. PAUSED SHALL блокировать workflow events. Instructions SHALL разрешать status/clarification conversation и запрещать самостоятельное объявление resume/progress; нарушение моделью этой инструкции SHALL быть отдельным adherence observation, не FSM mutation или semantic commit gate.

#### Scenario: Status answer is a real ordinary turn
- **WHEN** PAUSED task получает «Где мы остановились?» и пригодный completed ответ
- **THEN** одна pair committed в active session, State/node/revision, Working, Long-term, Profile/binding и identities неизменны; Short-term и содержащий его Memory snapshot отражают новую pair

#### Scenario: Model implementation text cannot resume the task
- **WHEN** модель при PAUSED возвращает пригодный completed текст реализации
- **THEN** pair сохраняется по normal contract, adherence violation наблюдается отдельно, task остаётся PAUSED и workflow events запрещены

### Requirement: Actual observations separate storage selection assembly and adherence

Каждая dispatched attempt SHALL иметь immutable receipt использованных Memory/Profile/State snapshots, selections, rendered Profile/State sections, actual instructions/messages/query/settings, outcome и conversation_committed. Capture SHALL соответствовать фактическим provider-neutral generation arguments, а preview SHALL не считаться dispatch evidence. Storage, selection, actual assembly и model adherence SHALL показываться раздельно без aggregate score. Semantic adherence SHALL быть human observation; literal markers SHALL не доказывать качество. Pre-dispatch rejection SHALL обозначаться not_dispatched; failed/refused/incomplete output SHALL оставлять input evidence доступным, output assessment unavailable. Runtime latest transition SHALL содержать before/event/after только подтверждённой операции; durable history SHALL не требоваться.

#### Scenario: Correct state input and wrong model answer remain separate
- **WHEN** stored/selected/assembled State корректно execution, а ответ предлагает заново собирать требования
- **THEN** первые три observations остаются successful, model adherence отмечается отдельно без изменения State

#### Scenario: Receipt equals delegate arguments
- **WHEN** независимый recording client фиксирует переданный ему request
- **THEN** messages/config точно совпадают с actual receipt, поздний transition не переписывает этот receipt

### Requirement: Controlled state influence isolates the state section

Deterministic acceptance SHALL сравнивать planning, execution и validation при идентичных Memory, пустом active transcript, фиксированном Profile, query «Что делать дальше?» и model/settings. Между снимками SHALL применяться supported explicit events; произвольная установка node SHALL не требоваться. Non-committing probes SHALL не сохранять query/reply, менять State или делать output источником следующего probe. Recording-client evidence SHALL доказывать только input assembly: различается State-derived section, все остальные semantic inputs совпадают. Настоящее semantic model behavior SHALL оцениваться отдельно live, без требования трёх live runs.

#### Scenario: Probe outputs do not contaminate the next state comparison
- **WHEN** при unchanged Memory/Profile последовательно проверены planning/execution/validation через explicit progress events и non-committing probes
- **THEN** delegate получает одинаковые messages/query/settings/Profile section и разные State sections; previous outputs отсутствуют, probes не меняют durable sources

### Requirement: Two new conversations isolate live continuation from transcript

Основной live acceptance SHALL использовать WORKING task=«Checkout: обработка loading/error/success», current_architecture=MVI, release_marker=RC-42 и один неизменный явно выбранный Profile Compact Engineer. Long-term SHALL оставаться фиксированной. После explicit REQUIREMENTS_READY и PLAN_APPROVED State SHALL быть EXECUTION_IMPLEMENT/ACTIVE. Обязательный ordinary execution Send SHALL создать настоящую completed user/assistant pair в session S0 без изменения State; наличие сохранённого transcript S0 SHALL быть подтверждено до Pause. Обязательный flow SHALL быть execution Send и подтверждение S0, Pause, New Conversation #1, ordinary Send «Где мы остановились?», human status assessment, New Conversation #2, проверка empty active Short-term, Resume, ordinary Send «Продолжим». Успешный live flow SHALL выполнять ровно три generation calls (execution, status, continuation); setup/events/lifecycle/read SHALL выполнять ноль provider calls. Обе New Conversation SHALL сохранять task/Working/Profile/State и исключать все inactive transcripts из model input. Финальный continuation request SHALL не содержать ни старый execution transcript, ни status query/reply, summary или receipts вместо них.

#### Scenario: Execution transcript exists before pause
- **WHEN** ACTIVE execution task выполняет обязательный ordinary execution Send перед Pause
- **THEN** настоящий completed ответ сохраняется вместе с user message в S0, сохранённая pair подтверждена, State остаётся EXECUTION_IMPLEMENT/ACTIVE; без этой pair live acceptance не считается успешно пройденным

#### Scenario: First new conversation demonstrates paused status without old history
- **WHEN** после подтверждённого execution transcript S0, Pause и New Conversation #1 отправлено «Где мы остановились?»
- **THEN** actual request содержит текущую постановку и EXECUTION_IMPLEMENT/PAUSED без прежней history; человек отдельно оценивает понимание task/step/pause и отсутствие возврата в planning; State не меняется

#### Scenario: Second new conversation removes the status answer
- **WHEN** после status turn выполнены New Conversation #2 и Resume, затем «Продолжим»
- **THEN** перед dispatch active history пуста, input содержит только fixed base/Profile/State, current selected Memory и query; обе прежние conversations отсутствуют; после completed pair State остаётся EXECUTION_IMPLEMENT/ACTIVE

#### Scenario: Continuation quality is observed rather than synthesized
- **WHEN** получен настоящий final response
- **THEN** отдельно фиксируется, продолжает ли он implementation loading/error/success в MVI без повторного запроса постановки и planning; failure/mismatch не скрывается retry или выдуманным ответом

### Requirement: Deterministic acceptance covers every pause position and durability

Acceptance SHALL проверять все non-terminal nodes через Pause/Resume с same node, revision+2 и unchanged Working/Long-term/Profile/binding/owner/task/session/Short-term/Memory snapshot. SHALL проверяться invalid/unknown/stale events, DONE behavior, rollback, corruption, namespaces и exact reopen node/status/revision. Reads, setup, lifecycle, State events, rendering и reopen SHALL делать ноль provider calls. Ordinary Send и explicit live probe SHALL иметь не более одной generation каждый, без count/extraction/summarization/retries/fallback. Backend restart SHALL быть deterministic durability acceptance, не обязательным визуальным шагом основного live flow.

#### Scenario: Offline pause matrix needs no live provider
- **WHEN** все nodes и rejection/storage cases проверены deterministic clients
- **THEN** state guarantees и unchanged subsystem snapshots подтверждены независимо от live adherence, provider calls для FSM operations равны нулю

#### Scenario: Reopen does not replay an interrupted action
- **WHEN** store/service reopened после сохранённого PAUSED State или потерянного HTTP outcome
- **THEN** current возвращает последний durable snapshot без повторного event/Send и без fabricated runtime receipt
