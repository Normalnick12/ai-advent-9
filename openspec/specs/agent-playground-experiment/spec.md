# agent-playground-experiment Specification

## Purpose

Определяет Day 15 как изолированный интеграционный Coding Agent experiment: настраиваемая policy задачи, настоящий разговор и контролируемый lifecycle с честными границами гарантии.

## Requirements

### Requirement: Task creation accepts only supported typed coding configuration

Перед созданием новой task Playground SHALL принимать Profile preset Compact Engineer либо Mentor и ровно четыре policy fields: required_architecture=MVI|MVVM, required_ui_toolkit=Compose|Views, required_async_model=CoroutinesFlow|RxJava, payment_confirmation_required=true|false. Default configuration SHALL быть Compact Engineer/MVI/Compose/CoroutinesFlow/true. Retry mode SHALL NOT быть policy setting. Unknown fields, unsupported values, arbitrary instructions и DSL SHALL отклоняться до durable mutation и provider calls. Task SHALL использовать demo Checkout loading/error/success + retry и Day 15 workflow checkout-v2: Requirements/Plan Approval/Implementation/Validation/Done с прежними forward edges и двумя explicit recovery edges.

#### Scenario: Alternative supported configuration is accepted
- **WHEN** пользователь подтверждает новую task с Mentor, MVVM, Views, RxJava и payment_confirmation_required=false
- **THEN** создана задача с этими exact values; проверка decisions использует эту policy, а не defaults

#### Scenario: Invalid configuration cannot partially initialize sources
- **WHEN** создание содержит unsupported enum, неверный boolean type, retry_mode policy field или raw prompt
- **THEN** конфигурация отклонена до создания task/sources, generation отсутствует

### Requirement: Reviewed setup retains the confirmed configuration across failures

Создание SHALL требовать explicit confirmation видимых task/Profile/workflow/policy. Setup SHALL сохранять machine_id=checkout-v2 вместе с reviewed configuration и проверять его совместимость с materialized State при completion/restore. Setup SHALL выполнять ноль provider calls, детерминированно создавать coherent sources и сохранять подтверждённую конфигурацию для восстановления. Initial Working.current_architecture SHALL совпадать с выбранной policy. Partial setup SHALL быть видимым и блокировать обычные operations до явного completion на тех же identities с той же конфигурацией. Reads SHALL NOT завершать setup автоматически. Повторное completion SHALL дополнять только отсутствующие совместимые компоненты; conflicts SHALL NOT исправляться overwrite/default reset. Пока setup pending, новая setup configuration SHALL NOT заменять её.

#### Scenario: Failure preserves nondefault setup choices
- **WHEN** после подтверждения MVVM/Views/RxJava/false setup частично сохранён и процесс перезапущен
- **THEN** read показывает те же target IDs и выбранные values, Send заблокирован; explicit completion не создаёт ещё одну task и не возвращает MVI defaults

#### Scenario: Setup succeeds but its response is lost
- **WHEN** task уже создана, но клиент не получил подтверждение
- **THEN** read показывает созданную task; второй create не выполняется автоматически

### Requirement: Coding policy is immutable per task

Каждая task SHALL иметь отдельный immutable policy snapshot с identity/version/fingerprint и typed values, совместимый с существующим durable policy contract. Identical installation SHALL быть no-op, replacement для той же task SHALL отклоняться. New Task SHALL требовать нового review/confirmation, получать новый policy record и сохранять предыдущую task/policy как inactive. New Conversation и Profile switch SHALL сохранять policy. Значение payment_confirmation_required SHALL проверяться на exact equality, включая false; false SHALL NOT отключать этот predicate.

#### Scenario: Two tasks retain different policies
- **WHEN** после Task A с MVI/Compose/CoroutinesFlow/true явно создана Task B с альтернативной policy
- **THEN** A и её policy сохранены, B использует собственные values и initial State, sources A не попадают в input B

#### Scenario: Runtime policy replacement is rejected
- **WHEN** для текущей task пытаются установить иной policy snapshot
- **THEN** durable policy не меняется и provider не вызывается

### Requirement: Profile changes remain independent preferences

Playground SHALL предоставлять explicit Compact Engineer/Mentor selection в собственном owner scope. Switch SHALL изменять только active binding и влиять на следующие Send; task, State, вся Memory и policy SHALL оставаться прежними. Presets SHALL использовать существующие profile semantics; full editor и автоматическая синхронизация с Day 12 namespace SHALL отсутствовать. Profile preferences SHALL NOT автоматически становиться hard invariants.

#### Scenario: Switch does not rewrite a previous answer
- **WHEN** после ответа Compact Engineer выбран Mentor
- **THEN** следующие request instructions используют Mentor, conversation/task/policy прежние и предыдущий receipt показывает Compact Engineer

### Requirement: Natural conversation has explicit bounded candidate coverage

Playground SHALL принимать произвольный непустой query и получать отдельный versioned conversation candidate с answer text и обязательными typed decisions architecture, ui_toolkit, async_model, payment_confirmation_required. Candidate SHALL быть structurally strict, поддерживать policy-compatible и incompatible values и не содержать executable lifecycle/tool commands. Четыре predicates SHALL проверять decisions до acceptance/commit. Free-form answer SHALL иметь structural checks, но SHALL NOT маркироваться как полностью semantic invariant-safe, проверенный source code или выполненное действие. Natural query SHALL NOT получать fabricated trusted intent или обещание zero-call semantic conflict detection. Старый Day 14 bounded CodingProposal, extra-field rejection и trusted-template rendering SHALL сохраняться.

#### Scenario: Matching metadata does not certify prose
- **WHEN** conversation candidate содержит совместимые decisions, но prose семантически противоречит им или текущему этапу
- **THEN** evidence подтверждает только проверенные decisions и structural validity, не объявляет prose/code validated и не меняет State; semantic correctness остаётся отдельным наблюдением

#### Scenario: Candidate decision violates configured policy
- **WHEN** structurally valid conversation candidate содержит MVI при policy MVVM
- **THEN** accepted answer не публикуется, commit содержит deterministic policy-specific refusal без rejected text

#### Scenario: Free text is not a structured request conflict
- **WHEN** пользователь естественным текстом просит изменить stack
- **THEN** система не объявляет precheck passed/violated без trusted classified intent; generation по прежней policy проходит обычный candidate gate и не меняет policy

### Requirement: Workflow version preserves earlier lesson semantics

Day 15 SHALL использовать отдельную definition checkout-v2 и отдельный State namespace поверх неизменённых TaskStateDefinition, resolver, allowed_events, CAS store и Pause/Resume. Checkout-v1, его пять узлов, четыре forward edges, contracts и persisted данные Days 13–14 SHALL сохраняться. Checkout-v2 SHALL сохранять эти пять узлов и их metadata, четыре forward edges и добавлять только два явно объявленных recovery edges. Machine identity SHALL закреплять смысл graph; несовместимый machine_id SHALL отклоняться без reinterpretation/migration/reset.

#### Scenario: Earlier workflow does not acquire recovery events
- **WHEN** checkout-v1 Days 13–14 проверяется с REQUIREMENTS_REVISION_REQUIRED либо VALIDATION_FAILED
- **THEN** события отсутствуют в allowed_events и отклоняются с прежними State/revision/sources; forward и Pause/Resume semantics прежние

#### Scenario: Reopen preserves the versioned recovered node
- **WHEN** Day 15 сохраняет recovery и stores открываются заново
- **THEN** setup и State сохраняют checkout-v2, target node и revision без provider call или replay

#### Scenario: A different machine version is not silently reinterpreted
- **WHEN** v2 store получает stored checkout-v1 state либо setup/state versions расходятся
- **THEN** возвращается явная incompatibility/configuration error без изменения durable records или defaults

### Requirement: The existing forward path remains authoritative

Day 15 checkout-v2 SHALL переиспользовать forward переходы PLANNING_REQUIREMENTS/REQUIREMENTS_READY/PLANNING_APPROVAL/PLAN_APPROVED/EXECUTION_IMPLEMENT/IMPLEMENTATION_READY/VALIDATION_CHECK/VALIDATION_CONFIRMED/DONE в существующем порядке. PLAN_APPROVED SHALL означать явное user/application approval, VALIDATION_CONFIRMED — явное подтверждение проверки, не автоматическую проверку качества плана/кода. Natural replies SHALL NOT выполнять events. Semantic запрет implementation prose до approval SHALL NOT заявляться как FSM guarantee.

#### Scenario: Implementation cannot skip plan approval
- **WHEN** в PLANNING_APPROVAL отправлен IMPLEMENTATION_READY
- **THEN** переход отклонён, State/revision и остальные sources прежние, provider calls равны нулю

#### Scenario: Finalization cannot skip validation stage
- **WHEN** в EXECUTION_IMPLEMENT отправлен VALIDATION_CONFIRMED
- **THEN** переход отклонён с требованием сначала перейти к validation через IMPLEMENTATION_READY; state unchanged и ноль provider calls

#### Scenario: Explicit validation confirmation completes the task
- **WHEN** актуальный VALIDATION_CHECK получает VALIDATION_CONFIRMED
- **THEN** State становится DONE без требования LLM call, без скрытого дополнительного этапа и без утверждения, что backend выполнил тесты

### Requirement: Explicit domain recovery follows only declared reverse edges

Checkout-v2 SHALL разрешать PLANNING_APPROVAL + REQUIREMENTS_REVISION_REQUIRED -> PLANNING_REQUIREMENTS и VALIDATION_CHECK + VALIDATION_FAILED -> EXECUTION_IMPLEMENT. Только explicit user/application event SHALL применять recovery. Каждый accepted recovery SHALL менять ровно state_id и revision +1 при прежних task_id, machine_id и ACTIVE status; conversation/Memory/Working/Long-term, Profile/binding, policy, configuration и их revisions SHALL оставаться прежними, provider calls=0. Result SHALL обозначать Recovery applied и конкретный следующий шаг, dispatch not_required, conversation unchanged. Natural query/candidate/answer SHALL NOT выбирать или применять recovery. Generic Back/next_state, rollback stack, history rewind/undo, dynamic graph editing и semantic auto-detection failure SHALL отсутствовать.

#### Scenario: Requirements revision returns to requirements
- **WHEN** current ACTIVE PLANNING_APPROVAL получает REQUIREMENTS_REVISION_REQUIRED с актуальной revision
- **THEN** State становится PLANNING_REQUIREMENTS с revision +1, остальные sources прежние, calls=0, allowed_events ровно REQUIREMENTS_READY и PAUSE; result предлагает уточнить требования и снова согласовать план

#### Scenario: Validation failure returns to implementation
- **WHEN** current ACTIVE VALIDATION_CHECK получает VALIDATION_FAILED с актуальной revision
- **THEN** State становится EXECUTION_IMPLEMENT с revision +1, остальные sources прежние, calls=0, allowed_events ровно IMPLEMENTATION_READY и PAUSE; result предлагает исправить найденные проблемы

#### Scenario: Recovery cannot be applied from another node
- **WHEN** REQUIREMENTS_REVISION_REQUIRED применяется вне PLANNING_APPROVAL либо VALIDATION_FAILED вне VALIDATION_CHECK, включая повтор события после успешного recovery
- **THEN** переход rejected, State/revision и все non-State sources unchanged, calls=0; result не объявляет recovery applied

#### Scenario: Recovered task can follow the forward path again
- **WHEN** после requirements recovery явно применяются REQUIREMENTS_READY и PLAN_APPROVED либо после validation recovery продолжается implementation
- **THEN** обычные IMPLEMENTATION_READY и VALIDATION_CONFIRMED снова приводят через Validation к Done без bypass approval/validation, auto event или rewind conversation

#### Scenario: Failure wording in conversation is not a recovery event
- **WHEN** natural Send либо model answer сообщает о проваленной проверке или возврате к реализации
- **THEN** State/revision прежние, lifecycle event не создаётся; следующий отдельный explicit VALIDATION_FAILED проверяется resolver как обычно

### Requirement: Pause conversation and terminal behavior are explicit

PAUSE/RESUME SHALL сохранять workflow node и применять существующие revision semantics. В PAUSED SHALL разрешаться обычный Send с paused guidance для уточнений, но forward/recovery events SHALL отклоняться; Send SHALL NOT возобновлять task. Pause SHALL NOT отменять provider request и SHALL подчиняться общему busy guard. DONE SHALL иметь read-only conversation и Inspector/history, без Send/progress events или automatic reset; новая задача SHALL создаваться только явно.

#### Scenario: Pause and resume preserve execution
- **WHEN** execution task приостановлена, выполнен clarification Send и затем explicit Resume
- **THEN** после Resume сохранён EXECUTION_IMPLEMENT, clarification не применял event, после него действуют обычные lifecycle actions

#### Scenario: Recovery cannot bypass pause or terminal state
- **WHEN** любой recovery event отправлен в PAUSED task либо DONE
- **THEN** State/revision и остальные sources прежние, calls=0; PAUSED allowed_events содержит только RESUME, DONE не содержит событий

#### Scenario: Completed task stays completed after restore
- **WHEN** backend и Android перезапущены после DONE
- **THEN** task остаётся completed, composer и progress недоступны, history доступна без generation

### Requirement: Playground persistence is isolated and conversation-scoped

Playground SHALL иметь отдельный durable namespace, не импортировать/migrate данные Days 11–14. Cold restore SHALL восстановить task, active conversation transcript, Memory, selected Profile, State и policy read-only. Explicit New Conversation SHALL создавать новую active session с сохранением предыдущей inactive history, task/Working/Long-term/Profile/State/policy; он SHALL NOT подразумевать перенос старого transcript, extraction или summary. Сохранение узла после смены conversation SHALL NOT называться сохранением полного плана/реализации в Working.

#### Scenario: New conversation preserves state but excludes old transcript
- **WHEN** пользователь явно создаёт новую conversation для paused task
- **THEN** сохраняются node/status и task sources, новая history пуста, старые messages отсутствуют в следующем input

### Requirement: Acceptance demonstrates integration rather than new laboratory matrices

Deterministic acceptance SHALL покрывать оба recovery edges (exact node/revision +1, non-State equality, zero calls, updated allowed_events), recovery из unrelated node, повтор события, PAUSED/DONE, stale CAS и reopen/lost acknowledgement без replay. Оба forbidden skips SHALL оставаться rejected/unchanged; после каждого recovery SHALL проверяться forward continuation через Validation к Done. Acceptance SHALL также сохранять configurable policies, coherent setup/reconciliation, bounded gate/commit, immutable evidence и namespace isolation без повторного A/B исследования каждого механизма. Основной live SHALL использовать один разговор и default reviewed configuration: requirements Send, REQUIREMENTS_READY, rejected IMPLEMENTATION_READY, plan Send, PLAN_APPROVED, implementation Send, Pause/Resume, IMPLEMENTATION_READY, validation Send, VALIDATION_FAILED, correction Send, IMPLEMENTATION_READY, VALIDATION_CONFIRMED, DONE. Второй forbidden skip и requirements recovery SHALL покрываться offline, без обязательного расширения live. По Send SHALL быть не более одной generation без automatic retries/repair/reviewer/extraction/count; non-generation operations SHALL иметь ноль вызовов. Фактический неуспех SHALL фиксироваться без обещания заранее успешного прохождения. Day README SHALL содержать только проверенные/подтверждённые результаты и иметь ссылку из корневого README.

#### Scenario: Successful live workflow is understandable from the screen
- **WHEN** основной live проходит успешно
- **THEN** пять Sends создают пять пар, один forbidden skip явно rejected/unchanged, VALIDATION_FAILED явно recovery applied с revision +1 и unchanged conversation, Pause/Resume сохраняет node; все lifecycle operations имеют ноль calls, DONE достигнут через повторный forward и explicit confirmation

#### Scenario: Explicit recovery does not fabricate test execution
- **WHEN** пользователь применяет VALIDATION_FAILED в live и затем обсуждает исправление
- **THEN** result описывает явное lifecycle решение без утверждения о выполненных backend тестах; correction query явно сообщает контекст, event/receipt не добавляется скрыто в history/model input

#### Scenario: Actual model failure is not hidden by a scripted success
- **WHEN** live Send дал candidate refusal или technical failure
- **THEN** записан фактический outcome, число вызовов и commit result; успешный ответ/полное прохождение не объявляются подтверждёнными без evidence
