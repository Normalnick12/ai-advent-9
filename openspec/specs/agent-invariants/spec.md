# agent-invariants Specification

## Purpose

Определяет обязательную проверку допустимости результата агента до его принятия и сохранения, с явной границей гарантии и независимостью от конкретной domain policy и LLM provider.

## Requirements

### Requirement: Mandatory rules are distinct from facts and preferences

Invariant SHALL определять обязательное условие допустимости защищаемого результата или действия. Факты Memory, preferences Profile и workflow position SHALL сохранять собственную семантику; содержание поля само по себе SHALL NOT превращать его в hard rule. Применённые правила SHALL иметь stable ID, scope/source и доверенное описание. Scope SHALL обозначать применимость правила, а не требование хранить все rules в одном store. Правила FSM и других subsystem SHALL оставаться на соответствующих границах enforcement.

#### Scenario: The same content has different acceptance semantics
- **WHEN** max_bullets используется только как Profile preference, а architecture задана обязательной policy
- **THEN** Profile mismatch сам по себе не становится invariant refusal; нарушение обязательной architecture блокирует принятие proposal

#### Scenario: Existing workflow constraints retain their authority
- **WHEN** workflow event запрещён текущей FSM
- **THEN** event отклоняется существующим subsystem без необходимости дублировать transition rule в task invariant records

### Requirement: Enforcement states the checked object and its coverage

Система SHALL различать prevention instructions, фактически выполненные checks и наблюдение поведения модели. Passed check SHALL подтверждать только объявленные свойства проверенного объекта; он SHALL NOT означать universal semantic safety или корректность реализации по одним metadata. Обязательная проверка SHALL различать passed, known violation и unavailable/error; отсутствие выполненной проверки SHALL NOT считаться pass. Все пути принятия защищённого результата SHALL проходить обязательный gate до публикации как ответа и conversation commit.

#### Scenario: Correct instructions are not validation evidence
- **WHEN** invariants правильно собраны в model input, но обязательный checker не выполнился
- **THEN** assembly отмечается отдельно, candidate не принимается и enforcement не показывается successful

#### Scenario: Typed architecture does not certify source code
- **WHEN** проверено значение architecture в structured proposal без проверки исходников
- **THEN** guarantee относится к proposal decision, а не к соблюдению архитектуры произвольным кодом или prose

### Requirement: Policy and candidate contracts remain provider independent

Invariant validation SHALL получать parsed, structurally valid candidate abstraction. Provider structured-output mechanism, raw payload decoding и candidate parsing SHALL находиться за candidate-generation adapter boundary. Замена provider/parser SHALL NOT требовать изменения invariant policy, predicates, violations/results, acceptance gate или deterministic refusal rendering при сохранении candidate contract. Concrete policies SHALL использовать typed programmatic predicates; metadata SHALL NOT интерпретироваться как field/operator/value DSL, expression tree или runtime policy language.

#### Scenario: Another adapter supplies the same candidate
- **WHEN** два adapter возвращают одинаковый typed candidate из разных provider representations
- **THEN** policy assessment, violations и rendered refusal/accepted result одинаковы независимо от provider

#### Scenario: Malformed output cannot masquerade as a domain violation
- **WHEN** adapter не может получить structurally valid candidate из completed output
- **THEN** результат является technical candidate preparation error, без acceptance, semantic invariant refusal или conversation commit

### Requirement: Source consistency is checked before generation

Система SHALL до provider call проверять согласованность identities, поддерживаемость policy versions, готовность источников и объявленные domain cross-checks. Противоречие authoritative fact и invariant либо взаимно несовместимые обязательные правила SHALL давать configuration/consistency operation error с нулём provider calls и без conversation commit. Недостающий обязательный источник SHALL отличаться от corrupt/contradictory source. Soft preference SHALL NOT автоматически считаться противоречащим authoritative fact. Система SHALL NOT молча исправлять Memory или ослаблять rules.

#### Scenario: Working fact contradicts the mandatory architecture
- **WHEN** current_architecture=MVI, а applicable policy требует MVVM
- **THEN** до generation возвращается configuration inconsistency, все durable sources и conversation неизменны

#### Scenario: Owner preference is not an authoritative contradiction
- **WHEN** current_architecture=MVI и invariant=MVI при preferred_architecture=MVVM
- **THEN** preference не вызывает configuration error и не отменяет task invariant

### Requirement: Terminal outcomes have distinct conversation semantics

Known request conflict SHALL давать deterministic refusal без generation и commit исходного user message вместе с refusal. Known generated candidate invariant violation SHALL исключать raw candidate из принятого ответа и Short-term, формировать deterministic safe refusal и commit user/refusal. Internal consistency/configuration error SHALL давать operation error с нулём provider calls и без conversation commit. Technical validator/enforcement failure SHALL fail closed: candidate не принимается, возвращается technical operation error без semantic refusal и conversation commit. Provider error, refusal, incomplete и cancellation до commit SHALL NOT автоматически преобразовываться в semantic invariant refusal или новую пару. Accepted candidate SHALL проходить обязательную проверку и безопасное rendering до commit user/final-answer.

#### Scenario: Structured request conflicts before generation
- **WHEN** валидный structured intent противоречит действующему invariant при согласованных источниках
- **THEN** provider calls равны нулю, deterministic refusal объясняет rules и одна user/refusal pair сохраняется при успешном storage commit

#### Scenario: Model returns a known invariant violation
- **WHEN** допустимый запрос дал structurally valid candidate с известным policy violation
- **THEN** raw candidate не принимается и не сохраняется в conversation, одна user/safe-refusal pair сохраняется при успешном commit

#### Scenario: Validator crashes or becomes unavailable
- **WHEN** обязательная проверка выбрасывает исключение, истекает по timeout или не может получить необходимые данные
- **THEN** candidate не принимается, technical operation error не обвиняет пользователя в нарушении policy, history не меняется

#### Scenario: Provider does not produce a usable candidate
- **WHEN** provider завершает запрос error, refused или incomplete либо generation отменена до commit
- **THEN** сохраняется соответствующий технический/provider outcome без новой conversation pair и без выдуманных violations

#### Scenario: All required checks pass
- **WHEN** candidate прошёл обязательные checks и final answer построен доверенным renderer
- **THEN** сохраняется одна user/final-answer pair, raw provider output не становится assistant message напрямую

### Requirement: Refusals are deterministic safe results

Semantic refusal SHALL строиться из trusted rule descriptions и проверенных domain values, объяснять отклонённое предложение, применимое ограничение и доступную совместимую альтернативу. Refusal SHALL NOT требовать дополнительного LLM call, содержать unchecked raw candidate или выполнять отклонённое действие. Candidate violation SHALL объясняться как неприемлемость полученного варианта без ложного утверждения, что пользователь запросил нарушение. Refusal rendering failure SHALL считаться technical enforcement failure без commit.

#### Scenario: Refusal distinguishes user conflict from model failure
- **WHEN** пользователь отправил compatible intent, а candidate нарушил invariant
- **THEN** ответ говорит, что полученный вариант не прошёл проверку, и не приписывает пользователю conflicting intent

#### Scenario: Candidate text cannot enter refusal through diagnostics
- **WHEN** raw candidate содержит произвольные инструкции или prose рядом с диагностикой
- **THEN** эти строки не копируются в refusal или subsequent conversation context

### Requirement: Commit confirmation is separate from acceptance decision

Conversation write SHALL сохранять полную user/assistant pair атомарно. Candidate acceptance или refusal decision SHALL NOT означать подтверждённый commit. Storage failure SHALL возвращать technical operation error без ложного committed success. При неизвестном durable/HTTP outcome система SHALL читать authoritative conversation и согласовать runtime session перед следующей операцией без automatic replay generation/commit. Cancellation до commit SHALL сохранять прежнюю history; уже подтверждённый commit SHALL NOT объявляться отменённым из-за потери HTTP response. Общая транзакция Memory/Profile/State/policy stores и exactly-once network delivery SHALL NOT обещаться.

#### Scenario: Final pair write rolls back
- **WHEN** запись accepted answer или safe refusal не завершилась и rollback подтверждён
- **THEN** ни user, ни assistant не добавлены, прежняя history восстановлена, committed=false и operation error доступны

#### Scenario: Response is lost after durable commit
- **WHEN** пара сохранена, но клиент не получил response
- **THEN** recovery читает фактическую history без второго Send, неизвестный receipt не реконструируется из fixtures

### Requirement: Rejected candidates stay outside conversation sources

Raw rejected candidate SHALL NOT попадать в Short-term, Memory updates, subsequent model input или обычный response panel как принятый ответ. Диагностический просмотр SHALL маркировать его rejected/untrusted и оставаться отдельным от conversation. Conversation commit SHALL NOT изменять Working, Long-term, Profile, policy или Task State; Short-term и содержащий history snapshot SHALL отражать только committed pair.

#### Scenario: Next request follows a candidate refusal
- **WHEN** после rejected candidate и committed safe refusal выполняется следующий запрос
- **THEN** context содержит только исходный user message и safe refusal из предыдущего turn, без raw rejected candidate или inspector receipt
