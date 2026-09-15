# agent-profiles Specification

## Purpose

Определяет самостоятельные owner-scoped пользовательские профили поведения, их явное редактирование и durable выбор независимо от памяти агента и конкретного LLM provider.

## Requirements

### Requirement: Profiles are typed owner-scoped behavioral state

Profile SHALL содержать immutable profile_id и owner_id, metadata name, backend revision, language, tone, verbosity, typed response_format и typed constraints. Profile SHALL быть отдельным state от Short-term, Working и Long-term; общий owner SHALL NOT означать включение Profile в memory records. Contract SHALL NOT зависеть от размещения памяти/профилей в одном или разных storage files. Model/provider settings, arbitrary instructions, purpose/domain, skills/tools/pipelines SHALL NOT приниматься как profile fields.

#### Scenario: Several profiles belong to one owner
- **WHEN** один owner создаёт два профиля с разными typed preferences
- **THEN** оба имеют отдельные profile_id и независимо читаются в списке этого owner; Memory не изменяется

#### Scenario: Storage layout is not part of domain identity
- **WHEN** persistence adapter заменён при сохранении profiles и active binding
- **THEN** downstream create/read/edit/select contracts продолжают использовать прежние owner/profile identities без database paths или знания расположения Memory

### Requirement: Supported fields are strictly validated without artificial semantic conflict

Language SHALL принимать ru/en; tone — technical/explanatory; verbosity — concise/detailed. Response format SHALL быть summary_bullets с integer max_bullets от 1 до 5 либо teaching_sections без max_bullets. Constraints SHALL иметь boolean no_emoji, skip_basic_explanations и explain_unfamiliar_terms. Оба explanation flags SHALL разрешаться одновременно: пропускать базовые Android/Kotlin объяснения и пояснять вводимые специальные термины за пределами этой подготовки. Name SHALL быть непустым после trim и не длиннее 80 символов. Неизвестные enum values, extra fields, неверные types, null вместо обязательного значения и несовместимая структура format SHALL отклоняться целиком без effects/provider calls.

#### Scenario: Both explanation preferences are supported
- **WHEN** пользователь сохраняет skip_basic_explanations=true и explain_unfamiliar_terms=true
- **THEN** profile сохраняется с обоими flags, а behavioral instructions отражают обе совместимые предпочтения

#### Scenario: Invalid format does not partially update the profile
- **WHEN** edit содержит teaching_sections вместе с max_bullets либо max_bullets вне 1–5
- **THEN** edit отклонён, прежние fields/revision и selection сохраняются, Memory неизменна

### Requirement: Profile name is metadata only

Name SHALL служить только UI/metadata label и SHALL NOT автоматически включаться в behavioral instructions, routing или execution choices. Одинаковые behavioral fields SHALL давать одинаковые instructions независимо от name/profile_id/owner_id/revision. Name SHALL NOT требовать уникальности и SHALL NOT определять принадлежность к fixture.

#### Scenario: Rename cannot become a hidden prompt
- **WHEN** name изменён на строку с поведенческой инструкцией без изменения typed fields
- **THEN** label/revision обновляются, но model instructions остаются точными прежними; текст name не исполняется

#### Scenario: Duplicate labels preserve identities
- **WHEN** у двух profiles одинаковый name
- **THEN** read/edit/select различают их по profile_id, без неявного объединения записей

### Requirement: Create edit read list and select are explicit operations

Subsystem SHALL поддерживать create/edit/read/list/select для произвольных допустимых typed combinations, не только fixtures. Create SHALL выдавать новую identity с revision 0 без изменения active selection. Edit SHALL сохранять identity/ownership, обновлять только указанный profile и увеличивать revision при фактическом изменении. Read/list SHALL быть side-effect-free. Все операции SHALL выполняться без LLM calls. Chat, assistant replies, opening screen и startup SHALL NOT создавать, редактировать или выбирать Profile автоматически.

#### Scenario: User creates a custom profile
- **WHEN** сохранена допустимая комбинация detailed + technical + summary_bullets с лимитом 5
- **THEN** появляется самостоятельный редактируемый profile, прежний active profile и память не меняются

#### Scenario: Conversation cannot mutate settings
- **WHEN** в user message или model response присутствует просьба сохранить другой стиль
- **THEN** durable Profile и binding остаются прежними до отдельного explicit profile operation

### Requirement: Selection is durable and restricted to the owner

Active binding SHALL содержать owner_id, active_profile_id и отдельную revision. До первого explicit select состояние SHALL быть unselected; reads SHALL NOT выбирать fallback. Select SHALL принимать только существующий Profile того же owner. После restart SHALL восстанавливаться тот же выбор. Foreign-owner/unknown profile SHALL отклоняться без утечки его данных, изменения binding или provider call. Profile domain SHALL NOT использовать LLM router/classifier.

#### Scenario: Creation does not implicitly activate
- **WHEN** создан первый profile, но select не выполнен
- **THEN** current сообщает unselected, generation требует явного выбора и не вызывает provider

#### Scenario: Selecting another owner's profile fails
- **WHEN** owner A пытается read/edit/select Profile owner B
- **THEN** чужие данные не возвращаются и не изменяются, binding A остаётся прежним

#### Scenario: Durable active selection survives restart
- **WHEN** после select B backend перезапущен и выполнен current read
- **THEN** profiles, их revisions и binding B/revision совпадают с сохранёнными, generation/replay отсутствуют

### Requirement: Profile switch preserves every memory layer and identity

При explicit switch A -> B SHALL изменяться только active_profile_id и binding revision. memory_owner_id, task_id, session_id, Short-term, Working, Long-term, memory revision и memory snapshot SHALL оставаться неизменными. Profile records/revisions SHALL NOT меняться из-за select. Switch SHALL NOT означать New Conversation, New Task или Memory Reset.

#### Scenario: Switch with nonempty memory
- **WHEN** пользователь переключает A на B при непустых трёх слоях памяти
- **THEN** active_profile_id=B, binding revision увеличена, все три identity и все данные/порядок transcript/memory snapshot точно совпадают с before state

#### Scenario: Switching back preserves the same conversation
- **WHEN** пользователь после B снова явно выбирает A без промежуточного Send
- **THEN** возвращается A при прежних session/task/owner и побайтово неизменном transcript

### Requirement: Revisions and atomic writes reject stale operations

Edit SHALL проверять expected profile revision; select SHALL проверять expected profile revision и binding revision. Stale/failed writes SHALL NOT публиковать частичные изменения. No-op с актуальными revisions SHALL сохранять revisions; stale request SHALL отклоняться даже если желаемые fields совпадают с current state. Edit активного Profile SHALL увеличивать profile revision без изменения binding revision; следующий запрос SHALL разрешать новую profile revision. Unknown HTTP outcome SHALL восстанавливаться read, без automatic replay.

#### Scenario: Stale editor does not overwrite a newer profile
- **WHEN** edit отправлен с предыдущей revision после уже committed edit
- **THEN** возвращается stale conflict, новый profile state сохраняется и provider не вызывается

#### Scenario: Binding write failure preserves the previous selection
- **WHEN** storage не подтверждает select B
- **THEN** после rollback/reopen читается прежний committed binding A без частичного переключения

#### Scenario: Repeated current selection is a no-op
- **WHEN** выбран уже активный Profile с актуальными revisions
- **THEN** binding/profile revisions и все memory state остаются прежними

### Requirement: Profile lifecycle is independent of memory operations

New Conversation, New Task и Clear Long-term SHALL сохранять profiles и active binding включая revisions. Edit Profile SHALL сохранять все Memory данные/identities. Startup/cold reads SHALL восстанавливать durable records без generation/replay; отсутствие initialized state SHALL отличаться от storage corruption. Corruption SHALL возвращать явную ошибку без silent recreation/repair. Эти contracts SHALL сохраняться независимо от storage layout.

#### Scenario: New task keeps personalization
- **WHEN** создана новая task с новой session
- **THEN** active Profile и все profile records/revisions прежние, новая task использует этот Profile при следующем Send

#### Scenario: Clearing long-term is not clearing the profile
- **WHEN** Long-term текущего owner очищена
- **THEN** Profile settings/selection, Working и Short-term не меняются

#### Scenario: Corrupt profile storage is not an empty first launch
- **WHEN** restore обнаружил invalid record или binding reference
- **THEN** возвращается storage error, profiles/owner не создаются заново и provider не вызывается

### Requirement: Behavioral instructions are a deterministic projection of typed fields

Profile instructions SHALL детерминированно отражать только поддерживаемые behavioral fields. Fixed base SHALL быть нейтральна к language/tone/verbosity/format; typed Profile SHALL быть единственным источником выбранных Day 12 behavioral preferences. Metadata и Memory values SHALL NOT интерполироваться как profile instructions. Projection SHALL выполняться без storage/provider calls и без знания fixtures/expected answers. False constraint SHALL означать отсутствие дополнительного требования, а не предписание противоположного поведения. Instructions SHALL NOT становиться confirmed transcript.

#### Scenario: Mentor does not conflict with a fixed concise base
- **WHEN** активен detailed/explanatory Profile
- **THEN** effective instructions содержат его подробность и не содержат fixed требования always concise

#### Scenario: Repeated projection is stable and provider independent
- **WHEN** одни и те же typed preferences подготовлены дважды или для другого provider adapter
- **THEN** behavioral instructions совпадают; profile contract не содержит model, reasoning, service tier, truncation или provider payload
