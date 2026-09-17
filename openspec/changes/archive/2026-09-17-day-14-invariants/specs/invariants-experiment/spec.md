## Purpose

Определяет контролируемый Day 14 эксперимент с task-scoped coding policy, проверяемым предложением и наблюдаемым отказом до принятия результата, отдельно от качества свободного текста модели.

## ADDED Requirements

### Requirement: Day 14 uses an isolated durable task coding policy

Day 14 SHALL иметь отдельный namespace одного local demo owner, без импорта или migration Day 02–13. Для task SHALL явно сохраняться immutable coding policy snapshot с task identity, policy identity/version и typed values: required architecture=MVI, UI toolkit=Compose, async model=CoroutinesFlow, payment confirmation required=true. Policy SHALL храниться отдельно от conversation, Memory и Profile и восстанавливаться после restart. Repeated explicit installation той же policy SHALL быть no-op; другой snapshot для уже настроенной task SHALL отклоняться без overwrite. Missing policy SHALL отличаться от corruption и unsupported version; reads SHALL не создавать и не исправлять records.

#### Scenario: Reopen restores exact policy without generation
- **WHEN** после сохранения policy backend/storage открыт заново
- **THEN** task/policy identities, version и typed values совпадают с сохранёнными, generation/count/replay отсутствуют

#### Scenario: Installation cannot silently replace task constraints
- **WHEN** для task с установленной policy повторно установлены другие values или version
- **THEN** операция отклонена, прежний policy snapshot сохранён и provider не вызывается

### Requirement: Policy lifecycle follows task rather than conversation

New Conversation SHALL сохранять task policy и прочие task sources, создавая новую пустую active history с сохранением прежней inactive conversation. New Task SHALL создавать отдельную task/session и требовать собственной явной подготовки policy; прежняя task/policy SHALL оставаться inactive и не выбираться в новый input. Profile changes и Clear Long-term SHALL сохранять policy. Preparation SHALL показывать независимую готовность Memory, Profile, State и policy; partial failure SHALL блокировать proposal operation и допускать explicit completion missing component для уже созданной task без reset или повторного New Task.

#### Scenario: New conversation retains hard constraints
- **WHEN** создана новая conversation той же task
- **THEN** policy snapshot прежний, active history пуста, старый transcript не выбран, generation отсутствует

#### Scenario: Partial setup does not invent a rollback
- **WHEN** task/session уже сохранены, но policy installation завершилась ошибкой
- **THEN** current показывает существующие IDs и missing policy, proposal недоступен, read не устанавливает policy автоматически

### Requirement: Proposal operation captures coherent applicable sources

Каждая proposal operation SHALL проверять current task/session ownership, memory snapshot, profile/binding revisions, State revision и policy identity/version/snapshot до provider call. Conflicting mutations SHALL сериализоваться или отклоняться общим application guard в пределах поддерживаемого single-worker режима; source snapshots SHALL оставаться immutable в receipt. Lab proposal SHALL быть доступен только для подготовленного ACTIVE execution текущего Checkout workflow; необходимые workflow confirmations SHALL оставаться explicit и использовать существующие allowed events. Ни refusal, ни accepted result SHALL применять FSM events. PAUSED/DONE или неподходящий этап SHALL давать operation error до dispatch без новой пары.

#### Scenario: Sources change while generation is active
- **WHEN** in-flight proposal конкурирует с New Conversation, State event или другой source mutation
- **THEN** conflicting action отклоняется как busy, исходная попытка использует один согласованный snapshot

#### Scenario: Stale or inapplicable operation is rejected
- **WHEN** references устарели, task не current либо State не ACTIVE execution
- **THEN** возвращается pre-dispatch operation error без generation, refusal pair или изменений sources

### Requirement: Controlled requests have explicit trusted intent

Lab SHALL предлагать compatible action «Предложи retry после ошибки загрузки Checkout» и conflicting action со сменой architecture на MVVM, async на RxJava и отключением обязательного payment confirmation. Backend SHALL разрешать action ID в versioned typed intent и соответствующий отображаемый user text. Android SHALL NOT присылать собственные policy definitions, expected violations или raw instructions. Conflicting intent SHALL проверяться обычным кодом до generation с точными rule references. Эксперимент SHALL NOT заявлять deterministic NLU для произвольного текста; reusable mechanism SHALL допускать отсутствие classified intent без отключения candidate gate.

#### Scenario: Controlled conflict needs no classifier
- **WHEN** выбрана conflicting action при согласованной policy
- **THEN** зафиксированы три соответствующих violations, generation/count calls равны нулю, сохранена user/refusal pair при успешном commit

#### Scenario: Compatible request does not prove arbitrary intent understanding
- **WHEN** compatible action прошла precheck
- **THEN** evidence подтверждает проверку именно её typed intent, без claims о классификации любого пользовательского сообщения

### Requirement: Model guidance and actual assembly are separate from enforcement

Input SHALL сохранять selected Memory как data context, Profile как preferences и Task State как workflow authority, добавляя отдельную trusted ACTIVE_INVARIANTS section. Invariants SHALL отражаться в generation input даже при deterministic gate. Policy IDs/revisions и diagnostics SHALL оставаться metadata, а не hidden user facts; expected test results SHALL не подставляться в model response. При request conflict actual request и candidate SHALL отсутствовать, assembly SHALL обозначаться not dispatched/not applicable, не pass по preview.

#### Scenario: Actual compatible generation contains the policy
- **WHEN** выполняется compatible action
- **THEN** recording delegate получает exact captured messages/config/query с отдельной invariant section и только active Memory/history

#### Scenario: Refusal without generation has no fabricated request
- **WHEN** request conflict обнаружен до provider call
- **THEN** receipt содержит actual_request=null, candidate=null и generation_calls=0 независимо от наличия preview

### Requirement: Accepted proposal has a bounded fully checked representation

Lab candidate SHALL быть typed proposal с architecture, UI toolkit, async model, payment-confirmation requirement и bounded retry choice. Supported candidate values SHALL включать policy-incompatible альтернативы, чтобы structural validity не подменяла invariant validation. Поля SHALL иметь strict types, неизвестные/лишние поля SHALL отклоняться; произвольный explanation/prose SHALL не быть частью accepted output. После policy checks пользовательский ответ SHALL строиться только из checked fields и trusted templates. Guarantees SHALL относиться к decisions данного proposal, не к реальным source artifacts, архитектурной корректности кода или выполнению оплаты.

#### Scenario: Structurally valid incompatible proposal is rejected
- **WHEN** adapter выдал candidate с architecture=MVVM при required MVI
- **THEN** parsing успешен, invariant validation обнаруживает architecture violation, сохраняется safe refusal вместо candidate

#### Scenario: Hidden prose is not accepted through matching metadata
- **WHEN** raw output содержит architecture=MVI и дополнительное explanation с рекомендацией MVVM
- **THEN** extra field/unchecked prose не принимается как candidate, возникает technical candidate error без semantic refusal и conversation commit

#### Scenario: Compatible decisions render a safe answer
- **WHEN** все proposal fields допустимы и соответствуют policy
- **THEN** displayed/committed assistant text построен из этих полей, unchecked raw model text не добавлен

### Requirement: Receipts distinguish decisions failures and persistence

Каждая завершённая attempt SHALL предоставлять доступное evidence отдельно по source storage/selection, preparation/actual assembly, request precheck, candidate parsing, invariant assessment, final decision и conversation commit. Receipt SHALL содержать immutable Memory/Profile/State/policy snapshots, rule sources/versions, rendered invariant section, actual provider-neutral request при dispatch, доступный raw candidate и parsed candidate, violations, final reply/refusal, provider usage и generation count когда доступны. Technical failure SHALL показывать failed/unavailable stage без fabricated violations. Missing historical receipt SHALL оставаться unavailable. Raw rejected candidate SHALL быть diagnostic-only и не переиспользоваться как source.

#### Scenario: Validation and commit disagree
- **WHEN** proposal прошёл checks, но pair storage failed
- **THEN** assessment остаётся passed, terminal operation отмечена error и commit failed/unknown, UI не получает committed success

#### Scenario: Technical checker failure is not a semantic refusal
- **WHEN** checker недоступен после generation
- **THEN** receipt отмечает technical enforcement failure, candidate not accepted, no conversation commit, без invented rule violation

### Requirement: Controlled acceptance proves the gate independently of model behavior

Deterministic acceptance SHALL покрывать compatible candidate, pre-generation controlled conflict, fake generated invariant violation, configuration inconsistency и technical adapter/validator/renderer failure. SHALL проверяться no rejected candidate in history/next input, exact safe pair semantics, atomic rollback/recovery, stale/busy/namespace boundaries и policy durability. Fake candidate case SHALL использовать allowed request и structurally valid violating proposal, без обхода production acceptance gate. FSM/Working/Long-term/Profile/policy SHALL оставаться unchanged для всех turn outcomes; Short-term изменяется только при confirmed pair commit. Tests SHALL проверять provider independence и отсутствие domain/provider imports в reusable invariant mechanism без реализации дополнительных agents.

#### Scenario: Fake violating model cannot poison the next turn
- **WHEN** recording/fake provider на allowed request выдаёт valid-schema violating proposal
- **THEN** ровно один fake generation, safe refusal committed, raw candidate отсутствует после reopen и в следующем captured model input

#### Scenario: Failure matrix preserves exact commit rules
- **WHEN** отдельно воспроизведены configuration, parser, validator, renderer и pair storage failures
- **THEN** ни один не выдан за normal invariant refusal, отсутствуют неподтверждённые пары и automatic retries

### Requirement: Live acceptance is minimal and records actual outcomes

Live acceptance SHALL выполнить compatible action с реальным provider и controlled conflict с нулём provider calls. Успешный compatible path SHALL подтвердить actual invariant input, validation и committed rendered response; конфликт SHALL подтвердить exact rules и committed deterministic refusal. По одной operation SHALL выполняться максимум одна generation, без count, retries, extraction, summarization или reviewer calls. Если live candidate нарушил rules или возник technical failure, результат SHALL фиксироваться фактически, happy path SHALL оставаться неподтверждённым без повторов ради успешной картинки. Fake violation SHALL доказываться отдельно offline.

#### Scenario: Minimal successful live flow
- **WHEN** compatible candidate принят, затем выполнена conflicting action
- **THEN** за две операции выполнена ровно одна generation и сохранены две пары: accepted response и deterministic refusal; State не продвинут

#### Scenario: Live model does not provide a compatible candidate
- **WHEN** реальный compatible request дал invariant violation
- **THEN** фиксируется actual rejected candidate и safe refusal, enforcement доказан для этой попытки, compatible acceptance не объявляется пройденным
