# memory-layers-experiment Specification

## Purpose

Определяет явную conversation-, task- и owner-scoped память Day 11, её durable lifecycle и контролируемую проверку различия сохранённых данных, выбранного контекста и ответа модели.

## Requirements

### Requirement: Three memory layers have independent ownership

Day 11 SHALL иметь три раздельно хранимых слоя: Short-term transcript принадлежит session_id; structured Working принадлежит task_id; durable Long-term принадлежит memory_owner_id. Identities SHALL быть независимыми. Durable current binding SHALL выбирать task и session одного memory owner с согласованной session-to-task принадлежностью. Short-term SHALL сохранять завершённые user/assistant пары и SHALL NOT означать RAM-only. Scope одного слоя SHALL NOT выводиться из identity другого.

#### Scenario: New session retains task ownership
- **WHEN** у одного owner создаётся новая conversation в текущей task
- **THEN** session_id меняется, task_id и memory_owner_id сохраняются, Working остаётся привязанной к task, Long-term к owner

#### Scenario: Invalid ownership cannot become current
- **WHEN** операция или restore обнаруживает session, принадлежащую другой task/owner, в current binding
- **THEN** возвращается явная ошибка без context generation, подстановки другой identity или изменения сохранённых данных

### Requirement: Initialization and reads do not implicitly run the experiment

Day 11 SHALL поддерживать одного локального demo owner в отдельном namespace. Только explicit Initialize SHALL создавать отсутствующего owner, пустую task, session, три слоя и binding атомарно. Повторная инициализация существующего owner SHALL возвращать current state без очистки. Reads и startup SHALL NOT создавать identities или вызывать provider. Отсутствующий initialized state SHALL отличаться от повреждения storage.

#### Scenario: First visit is read only
- **WHEN** Day 11 впервые открывается без initialized owner
- **THEN** read сообщает not_initialized, ни session, ни task, ни provider call не создаются

#### Scenario: Initialize is not reset
- **WHEN** Initialize повторён после успешной записи памяти
- **THEN** возвращаются прежние current identities и содержимое слоёв

### Requirement: Explicit typed writes select their layer deterministically

Working SHALL поддерживать task, current_architecture, release_marker; Long-term SHALL поддерживать project_code, preferred_architecture. Explicit set/remove SHALL указывать слой и ключ, проверяться обычным кодом и сохраняться без LLM calls. Set SHALL принимать непустую строку в пределах объявленного лимита; remove SHALL удалять только указанный ключ и быть no-op при его отсутствии. Неизвестные keys/layers, null values, неверные types и extra fields SHALL отклоняться без частичной записи. Natural-language chat и assistant replies SHALL NOT автоматически менять Working/Long-term. Подтверждённая explicit запись SHALL сохраняться независимо от результата следующей generation.

#### Scenario: Working write is isolated
- **WHEN** записано WORKING.current_architecture=MVI
- **THEN** меняется только этот ключ current task; transcript и Long-term неизменны, provider calls отсутствуют

#### Scenario: Invalid patch has no partial effects
- **WHEN** mutation содержит поле другого слоя, null или неизвестный ключ
- **THEN** весь mutation отклонён, значения/identities/revision остаются прежними

#### Scenario: Response failure does not undo saved memory
- **WHEN** после подтверждённого Long-term set следующий ordinary Send завершается ошибкой
- **THEN** Long-term запись остаётся, новая conversation pair не сохраняется

### Requirement: New Conversation preserves inactive durable history

New Conversation SHALL атомарно создать новую пустую session в current task и переключить current_session_id. Предыдущая session и вся её history SHALL оставаться durable, inactive. Current task_id, Working и Long-term SHALL сохраняться. New SHALL NOT выполнять delete/reset прежней conversation.

#### Scenario: Conversation becomes inactive rather than deleted
- **WHEN** New Conversation выполнена после Short-term error_title=Сбой-47
- **THEN** новая active history пуста, старая session/history читается в storage после reopen и не выбирается в новый model input

### Requirement: New Task preserves prior tasks and conversations

New Task SHALL атомарно создать новый task_id с пустой Working и новый session_id с пустой Short-term и переключить binding. Owner identity и Long-term SHALL сохраняться. Предыдущая task, Working и все её conversations SHALL оставаться durable, inactive. Повторная активация и destructive reset SHALL не входить в обязательные операции Day 11.

#### Scenario: Previous task is retained outside current context
- **WHEN** New Task выполнена после Working Checkout/RC-42
- **THEN** активные task/session IDs новые, активные Working/Short-term пусты; прежние Working и session associations сохранены, но не входят в prompt

### Requirement: Clear Long-term changes only owner memory

Clear Long-term SHALL очищать Long-term текущего owner без изменения Short-term, Working и всех identities. Операция SHALL NOT обещать удаление старых упоминаний тех же значений из conversation history.

#### Scenario: Clear is layer specific
- **WHEN** Long-term очищается при непустых Working и Short-term
- **THEN** обе последние памяти и identities побайтово/по значениям неизменны; только Long-term становится пустой

### Requirement: Durable transitions and restart preserve coherent current state

Day 11 storage SHALL быть отдельным от Day 02–10 без migration/import. Составные Initialize/New Conversation/New Task SHALL иметь all-or-nothing durable результат. Runtime session cache SHALL соответствовать committed binding; rollback SHALL NOT публиковать новые current identities. Restart SHALL восстанавливать same owner/task/session identities, active transcript, Working и Long-term; inactive данные SHALL сохраняться. Busy, pending calls и observations SHALL NOT требоваться для restore. Повреждённый state SHALL давать ошибку без silent repair/recreation.

#### Scenario: New Task rollback
- **WHEN** storage failure возникает между созданием task/session и commit binding
- **THEN** reopen и runtime read показывают прежний binding/слои, частично созданные identities не видны и cache не переключён

#### Scenario: Nonempty memory survives restart without replay
- **WHEN** backend остановлен на непустом A-state и запущен заново, затем выполнен read
- **THEN** IDs и три слоя совпадают с before snapshot; provider generation/count/extraction calls равны нулю

#### Scenario: Committed transition with lost response
- **WHEN** New Conversation committed, но HTTP outcome клиенту неизвестен
- **THEN** read возвращает новую durable current session, не создаёт ещё одну и не удаляет старую

### Requirement: Active context selects only current memory sources

Каждый Day 11 model input SHALL содержать fixed instructions, маркированные selected Long-term и Working data blocks, Full History только active session и current query/message. Raw roles/text/order SHALL сохраняться. Inactive sessions/tasks, observations, expected answers и audit diagnostics SHALL NOT добавляться как sources. Synthetic blocks SHALL NOT становиться confirmed transcript. Memory values SHALL передаваться как данные ниже instruction priority, без интерполяции в fixed instructions. Snapshot inspector SHALL различать stored и selected sources.

#### Scenario: Retained inactive markers are absent from provider input
- **WHEN** active task/session пусты, а прежние durable sources содержат Checkout, RC-42 и Сбой-47
- **THEN** assembled input не включает эти inactive sources; source manifest ссылается только на current identities

#### Scenario: Exact ordinary context
- **WHEN** active session содержит U1/A1 и приходит U2
- **THEN** после selected memory blocks input содержит ровно U1, A1, U2 в исходном порядке, без verification questions/replies

### Requirement: One deterministic architecture override preserves stored preference

При наличии Working current_architecture backend SHALL исключать Long-term preferred_architecture из selected Long-term block и использовать Working architecture как effective. При отсутствии override SHALL использовать доступную Long-term preference; при отсутствии обоих effective SHALL быть unknown. Long-term stored value SHALL NOT изменяться. Diagnostics SHALL показывать stored value, exclusion и причину working_override отдельно от provider input. Это SHALL быть одним явно заданным правилом Day 11 без generic priority/merge framework.

#### Scenario: Working overrides without overwriting
- **WHEN** Working current_architecture=MVI и Long-term preferred_architecture=MVVM
- **THEN** selected architecture=MVI, Long-term MVVM остаётся сохранённой, diagnostics объясняет exclusion, исключённое значение не возвращается в provider input через diagnostics

#### Scenario: Removing override activates fallback
- **WHEN** удалён только Working current_architecture
- **THEN** selected architecture=MVVM из Long-term, остальные memory records и identities сохраняются

### Requirement: Verification is side effect free and uses one fixed query

A–E SHALL использовать один и тот же verification query и одинаковые generation settings. Structured output SHALL содержать required nullable strings project_code, release_marker, current_task, effective_architecture, last_error_title и свободный string next_step, без extra fields и expected-value enums. Неизвестные точные поля SHALL ожидаться как null. Каждая explicit probe SHALL выполнять максимум одну generation и SHALL NOT append query/response, mutate Working/Long-term или менять binding/identities/revision. Expected values SHALL использоваться только локальным verifier, не добавляться в prompt/schema. Malformed/refused/incomplete/failed responses SHALL отображаться без hidden retries.

#### Scenario: Repeated probes cannot teach the next probe
- **WHEN** A и B verification завершились либо завершились ошибкой
- **THEN** memory snapshot до/после каждой probe совпадает, предыдущие verification outputs не являются input sources следующей

#### Scenario: Invalid structured response stays observable
- **WHEN** provider вернул malformed JSON либо incomplete response
- **THEN** output check unavailable/invalid с причиной, raw outcome доступен, память неизменна и повторный call автоматически не выполняется

### Requirement: Exact marker experiment follows A through E

Setup SHALL создавать один настоящий committed turn с exact error_title=Сбой-47 при пустых active Working/Long-term, затем отдельными explicit writes сохранять LONG project_code=ORION-17/preferred_architecture=MVVM и WORKING task=Checkout/current_architecture=MVI/release_marker=RC-42. A–E SHALL проверять actual stage preconditions, не доверять только UI label. Поля SHALL сравниваться точно; free next_step SHALL не входить в exact score. При непустом/несовместимом setup SHALL требоваться явная подготовка через lifecycle, без скрытого reset.

#### Scenario: A uses all layers
- **WHEN** проверяется A после setup
- **THEN** expected project/release/task/architecture/error = ORION-17 / RC-42 / Checkout / MVI / Сбой-47

#### Scenario: B removes only the override
- **WHEN** после A явно удалён Working current_architecture и выполнена B
- **THEN** expected fields = ORION-17 / RC-42 / Checkout / MVVM / Сбой-47

#### Scenario: C starts a new conversation
- **WHEN** после B выполнены New Conversation и C
- **THEN** expected fields = ORION-17 / RC-42 / Checkout / MVVM / null; previous Short-term остаётся durable inactive

#### Scenario: D starts a new task
- **WHEN** после C выполнены New Task и D
- **THEN** expected fields = ORION-17 / null / null / MVVM / null; MVVM является общим default, не решением вымышленной task

#### Scenario: E clears owner memory
- **WHEN** после D выполнены Clear Long-term и E
- **THEN** все пять exact fields ожидаются null; inactive данные не возвращаются как sources

#### Scenario: Stage label cannot prove acceptance
- **WHEN** запрошена stage с несоответствующим actual state
- **THEN** reported scenario_not_applicable без успешного score и без provider dispatch

### Requirement: Input availability and model use are independent observations

До generation backend SHALL фиксировать snapshot и раздельные per-field результаты available/absent/conflict в реально assembled sources. После generation SHALL независимо сравнивать model fields с oracle этапа. Dashboard SHALL различать expected absence и unavailable measurement. Stored existence без selection SHALL NOT доказывать availability; output match без source evidence SHALL NOT доказывать memory correctness. Конфликтующие exact assertions SHALL не маскироваться substring score. Observation SHALL быть привязан к snapshot_id и сохранять фактический outcome; durable persistence results SHALL не требоваться.

#### Scenario: Correct input and incorrect answer
- **WHEN** assembled selected architecture корректно MVI, а model field равен MVVM
- **THEN** input selection check остаётся correct, output field check incorrect; ошибка не переклассифицируется в storage failure

#### Scenario: Expected absence is checked explicitly
- **WHEN** на E fields отсутствуют в selected sources и модель возвращает null
- **THEN** показаны отдельно successful expected absence и successful output-null checks

#### Scenario: Lost runtime results are not restored as facts
- **WHEN** process restart уничтожил observations при сохранённой памяти
- **THEN** результаты обозначаются not measured/unavailable, generation не replay-ится и фиктивный success не создаётся

### Requirement: Provider calls and stale operations are explicit

Reads, writes, lifecycle, startup/restart и context preview SHALL выполнять ноль provider calls. Ordinary Send и explicit verification SHALL выполнять максимум одну generation каждый, без extraction, summarization, count requests, automatic retries или silent model fallback. Conflicting operations SHALL сериализоваться/отклоняться по owner; stale snapshot или inactive target SHALL отклоняться до effects. Transaction SHALL NOT удерживаться во время provider await. Unknown transport outcome SHALL разрешаться read/reconciliation без автоматического replay.

#### Scenario: Full successful experiment has a bounded call budget
- **WHEN** выполнены один seed Send и A–E без explicit retries
- **THEN** записано шесть generation calls и ноль maintenance/count calls; restart read не увеличивает счётчики

#### Scenario: Mutation cannot race a probe snapshot
- **WHEN** probe/Send выполняется и приходит competing memory mutation либо запрос со stale snapshot
- **THEN** conflict/busy возвращается без изменения памяти или второго provider call
