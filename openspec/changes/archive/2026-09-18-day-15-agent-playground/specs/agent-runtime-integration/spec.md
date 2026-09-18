## Purpose

Определяет интеграцию источников контекста, проверяемого ответа и явных lifecycle operations агента с независимыми гарантиями acceptance, persistence и workflow progress.

## ADDED Requirements

### Requirement: Integration preserves configurable mechanism boundaries

Интеграция SHALL принимать конкретные workflow, profile, domain policy и candidate-generation configuration отдельно от общих механизмов. Изменение поддерживаемых значений policy SHALL NOT требовать изменения orchestration алгоритма. Другой provider при том же typed candidate SHALL сохранять validation, lifecycle и commit semantics. Existing labs SHALL сохранять свои contracts и namespaces.

#### Scenario: Different supported policies share the same execution mechanism
- **WHEN** две новые задачи используют разные поддерживаемые policy values
- **THEN** одинаковый integration path проверяет каждую задачу по её собственному snapshot без изменения workflow engine или acceptance algorithm

#### Scenario: Another provider supplies the same candidate
- **WHEN** другой adapter возвращает тот же structurally valid candidate при тех же sources
- **THEN** policy decision, отказ и правила conversation commit совпадают независимо от provider representation

### Requirement: Send resolves coherent sources before dispatch

Send SHALL проверять current task/session ownership, memory snapshot, profile/binding revisions, State revision, policy identity/version/fingerprint и readiness до dispatch. Inconsistent authoritative facts/policy SHALL давать configuration error без generation и commit. Generation SHALL использовать один captured snapshot Memory/Profile/State/Invariants; actual input SHALL включать selected active history, Working/Long-term data, profile preferences, authoritative State и отдельную invariant guidance. Inactive conversations, rejected candidates и receipts SHALL NOT становиться model sources. Конкурирующие Send, source mutations, setup и lifecycle writes SHALL сериализоваться или отклоняться в поддерживаемом single-worker режиме.

#### Scenario: All sources reach the real client boundary
- **WHEN** готовая задача выполняет Send
- **THEN** captured actual input совпадает с аргументами recording delegate и содержит query и все четыре источника с их правильными ролями

#### Scenario: Stale or contradictory sources prevent dispatch
- **WHEN** reference устарела, task/session не current, policy отсутствует/повреждена либо Working противоречит policy
- **THEN** операция возвращает соответствующую source/configuration error, provider calls равны нулю и conversation не изменяется

#### Scenario: Lifecycle competes with generation
- **WHEN** во время Send приходит Pause, смена Profile или New Conversation
- **THEN** mutation не меняет источники in-flight attempt и не ставится скрыто в очередь для повторного применения

### Requirement: Send has a bounded acceptance and commit boundary

Send SHALL отделять generation/strict candidate preparation, mandatory checks, final rendering и atomic pair commit. Candidate SHALL приниматься только после полного набора объявленных checks. При known candidate violation SHALL сохраняться исходный user message и deterministic safe refusal вместо candidate. При наличии trusted structured request intent его known conflict SHALL давать refusal без generation. Отсутствие classified intent у natural query SHALL обозначаться not applicable, не successful NLU. Provider error/refusal/incomplete, malformed candidate, configuration error, unavailable checker или rendering failure SHALL NOT создавать synthetic assistant refusal или новую пару. Решение acceptance SHALL NOT означать подтверждённый commit.

#### Scenario: Accepted conversation answer is committed once
- **WHEN** structurally valid candidate проходит все обязательные checks и final rendering
- **THEN** сохраняется ровно одна полная user/assistant pair; raw transport envelope не публикуется как assistant message

#### Scenario: Rejected candidate cannot contaminate subsequent turns
- **WHEN** candidate нарушает policy
- **THEN** сохраняется только user/safe-refusal pair, raw candidate остаётся diagnostic-only и отсутствует в следующем input

#### Scenario: Missing evidence fails closed
- **WHEN** обязательный checker недоступен или coverage не соответствует required rules
- **THEN** candidate не принят, возвращается technical error без выдуманных violations и conversation commit

#### Scenario: Validation succeeds but storage fails
- **WHEN** проверки завершились passed, но запись пары failed либо unknown
- **THEN** receipt сохраняет passed assessment отдельно от technical operation outcome и не заявляет committed success

### Requirement: Ordinary conversation never advances task state

Любой исход Send SHALL сохранять Task State и revision, task identity, Working, Long-term, Profile и invariant policy. Только confirmed pair commit SHALL изменять Short-term и соответствующий memory snapshot. Query, candidate и rendered answer SHALL NOT интерпретироваться как lifecycle events. Passed invariant checks SHALL NOT автоматически разрешать или применять workflow progress. Это ограничение SHALL включать recovery/backward events: natural Send не меняет State даже при описании ошибки или возврата к реализации.

#### Scenario: Model announces completion
- **WHEN** query или ответ содержит PLAN_APPROVED, «реализация готова» либо «задача завершена»
- **THEN** durable State остаётся прежним до отдельного explicit event

#### Scenario: Model announces recovery
- **WHEN** query или rendered answer содержит VALIDATION_FAILED либо «проверка не пройдена, возвращаюсь в implementation»
- **THEN** Send сохраняет durable State/revision; recovery возможен только отдельным explicit lifecycle event

### Requirement: Lifecycle operations are deterministic and independent of conversation

Lifecycle operation SHALL принимать explicit event и expected State revision для current task, использовать существующие allowed transitions и CAS. Client SHALL NOT задавать next node напрямую. Разрешённый event, включая объявленное definition recovery edge, SHALL изменять только State с одной revision increment; все non-State sources, conversation, их revisions и configuration SHALL сохраняться. Domain recovery SHALL быть обычным разрешённым переходом, а не invalid transition, rewind или persistence reconciliation. Недопустимый event SHALL сохранять State включая revision, всю Memory, Profile и policy. Все lifecycle operations SHALL выполнять ноль provider calls и не создавать conversation pair. Успешный result SHALL публиковаться только после подтверждённой записи; stale revision, storage failure и unknown outcome SHALL отличаться от invalid transition.

#### Scenario: Explicit approval advances one edge
- **WHEN** PLAN_APPROVED применяется к актуальному PLANNING_APPROVAL
- **THEN** State становится EXECUTION_IMPLEMENT с revision + 1, остальные sources прежние, provider не вызван

#### Scenario: Explicit recovery applies one declared reverse edge
- **WHEN** explicit recovery event разрешён injected definition из актуального ACTIVE node
- **THEN** после confirmed CAS меняются ровно node и revision +1, остальные sources прежние, provider calls=0; result обозначает recovery applied, target и следующий шаг

#### Scenario: Rejection gives actionable deterministic evidence
- **WHEN** event недопустим для актуального State
- **THEN** result содержит attempted event, before/unchanged after, reason code, allowed events и required next action; provider обозначен not required, conversation commit not applicable

#### Scenario: Stale request is not described as a workflow violation
- **WHEN** expected revision отличается от актуальной
- **THEN** возвращается stale conflict без mutation и provider calls, требующий read/reconcile перед новым явным действием

### Requirement: Historical receipts describe the actual attempt

Завершённая attempt SHALL возвращать доступный immutable value snapshot с attempt identity и operation kind. Send receipt SHALL содержать использованные task/session/source identities и revisions, Memory selection, Profile/State/policy, rule coverage, фактический provider-neutral request при dispatch, доступные raw/parsed candidate, provider outcome/usage, decision, final reply и commit status. Lifecycle receipt SHALL содержать before/event/after, node/revision snapshots, next action и persistence outcome без выдуманного model input. Confirmed result SHALL явно различать forward_applied, recovery_applied и rejected forbidden transition; Pause/Resume SHALL иметь отдельные outcomes. Classification SHALL приходить из trusted injected workflow metadata, resolver/CAS сохраняют authority; generic success/fail недостаточен. Unknown/stale/write failure SHALL NOT маркироваться applied или known unchanged без evidence. Historical receipt SHALL NOT пересчитываться после изменения current state; commit pair association SHALL быть доступна только при её подтверждении. Потерянная diagnostics SHALL оставаться unavailable.

#### Scenario: Later configuration cannot rewrite evidence
- **WHEN** после Send изменён Profile, применён event, создан New Conversation или явно изменена Memory
- **THEN** ранее полученный receipt и его used-in-turn sections не меняются

#### Scenario: Provider was not needed
- **WHEN** receipt относится к applied forward, applied recovery, Pause/Resume либо lifecycle rejection
- **THEN** actual request/candidate отсутствуют, dispatch is not required; отсутствие generation не является provider failure

### Requirement: Restore and uncertain outcomes never replay operations

Cold restore SHALL читать durable current task, conversation, Memory, active Profile, State и policy без generation, implicit setup, source repair или replay. После неизвестного Send outcome система SHALL прочитать authoritative conversation и согласовать runtime session до новых writes. После неизвестного transition outcome SHALL перечитать State. Неизвестные delivery/commit outcomes SHALL NOT преобразовываться в автоматический повтор запроса; если recovery read не удался, mutations SHALL оставаться заблокированными с доступным read retry. Exactly-once network delivery и общая транзакция всех stores SHALL NOT обещаться.

#### Scenario: Response disappears after durable pair write
- **WHEN** backend сохранил пару, но клиент не получил response
- **THEN** recovery показывает фактическую history без второй generation/commit и без реконструкции receipt

#### Scenario: Transition acknowledgement disappears
- **WHEN** event мог сохраниться, но результат не подтверждён клиенту
- **THEN** клиент читает current State, не применяет event повторно и не объявляет состояние неизменным без evidence

#### Scenario: Recovery acknowledgement disappears
- **WHEN** reverse edge мог сохраниться, но подтверждение потеряно
- **THEN** authoritative State read сохраняет фактический recovered node/revision без replay, counter-transition, provider call или изменения conversation; domain recovery не путается с transport reconciliation

#### Scenario: Corrupt state is not replaced on startup
- **WHEN** restore обнаруживает повреждённый или неподдерживаемый источник
- **THEN** показывается соответствующая ошибка, implicit reset/migration и provider calls отсутствуют
