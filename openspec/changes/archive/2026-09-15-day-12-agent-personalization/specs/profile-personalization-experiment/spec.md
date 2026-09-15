## Purpose

Определяет Day 12 сравнение персонализации поверх настоящей модели памяти, автоматическое применение выбранного профиля и раздельное наблюдение selection, actual input и ответа модели.

## ADDED Requirements

### Requirement: Day 12 composes profiles with actual three-layer memory

Day 12 SHALL использовать независимые session-scoped Short-term, task-scoped Working и owner-scoped Long-term с semantics memory-layers-experiment: только active sources, retained inactive history/tasks и deterministic Working current_architecture override над Long-term preferred_architecture. Profile SHALL подключаться отдельно от memory data blocks. Day 12 SHALL иметь изолированное от старых Days состояние без migration/import и без создания второго generation/commit lifecycle.

#### Scenario: Task architecture remains a fact selected by code
- **WHEN** Working.current_architecture=MVI и Long-term.preferred_architecture=MVVM
- **THEN** selected memory содержит MVI, MVVM сохранено, но исключено с причиной working_override; switch Profile не меняет этот результат

#### Scenario: Inactive memory does not return through profile assembly
- **WHEN** после New Task прежние данные сохранены inactive
- **THEN** Profile применяется к новой current Memory, а inactive records/observations не становятся model input

### Requirement: Every request automatically resolves the active profile

Каждый Day 12 seed Send, ordinary Send и controlled probe SHALL разрешать active Profile на backend и включать его instructions вместе с current selected Memory и query. Пользователь SHALL NOT вручную добавлять Profile в query или передавать instructions/history/provider settings. Profile ID из expected references SHALL проверять authoritative selection, а не обходить её. Unselected/unknown/foreign/stale Profile SHALL отклоняться до generation, без fallback. Profile instructions SHALL NOT записываться как synthetic transcript messages.

#### Scenario: Ordinary query has no style instructions
- **WHEN** отправлен обычный вопрос при active Mentor
- **THEN** actual request содержит Mentor behavioral instructions без ручных стилевых указаний в query

#### Scenario: Explicit switch affects the next normal request
- **WHEN** после Send с A выполнен explicit switch B и отправлен следующий вопрос
- **THEN** следующий actual request использует B и текущую history, сохранённая ранее pair остаётся неизменной

### Requirement: Requests capture coherent immutable state before dispatch

Каждый dispatch SHALL фиксировать согласованные Memory snapshot, Profile snapshot/revision и binding revision до provider call. Конфликтующие memory/profile writes, lifecycle и generation SHALL сериализоваться либо отклоняться по owner. Stale expected references SHALL отклоняться до effects/provider call. Во время provider ожидания SQL transaction SHALL NOT удерживаться. Snapshot конкретной попытки SHALL NOT меняться из-за последующего read/edit. Неизвестный transport outcome SHALL вести к read/recovery без hidden retry.

#### Scenario: Profile cannot change during an in-flight request
- **WHEN** Send/probe уже захватил current state, а другой запрос пытается edit/select Profile
- **THEN** conflicting operation не меняет state незаметно; исходная попытка использует зафиксированные profile/memory snapshots

#### Scenario: Stale dispatch is rejected
- **WHEN** memory hash, profile revision или binding revision уже отличаются от отправленных expected references
- **THEN** возвращается stale/conflict без generation/commit, клиент перечитывает state

### Requirement: Preparation is explicit and preserves a real neutral seed turn

Reads/startup SHALL NOT создавать demo data или вызывать provider. Initialize SHALL создавать только отсутствующую Day 12 Memory и не сбрасывать существующую. Fixture profiles SHALL создаваться теми же create/edit/select operations, что пользовательские записи. Setup SHALL содержать ровно одну настоящую completed seed pair с максимально нейтральным по содержанию acknowledgment, показанным пользователю до freeze. Ответ SHALL NOT синтезироваться, переписываться или обрезаться ради нейтральности. Нейтральность SHALL обозначаться human observation, не автоматической гарантией. Failure SHALL NOT вызывать повтор автоматически. Частичная подготовка SHALL читаться явно, без обещания общей транзакции разных stores.

#### Scenario: Seed is a real profiled conversation
- **WHEN** на пустой active Memory с явно выбранным Profile отправлено подготовительное подтверждение
- **THEN** выполняется одна normal generation с этим Profile и сохраняется только её completed пригодная pair; raw ответ доступен для review

#### Scenario: Setup cannot overwrite user edits
- **WHEN** profile, созданный из шаблона, уже отредактирован пользователем
- **THEN** повторный read/setup не восстанавливает fixture values скрыто; create из шаблона и любые edits остаются явными

### Requirement: Comparison freezes one identical memory and transcript snapshot

Explicit Freeze SHALL фиксировать immutable comparison_id, raw memory/transcript snapshot, A/B profile identities/revisions, один query и одну non-profile generation configuration. Preconditions SHALL требовать LONG project_code=ORION-17/preferred_architecture=MVVM, WORKING task=Checkout/current_architecture=MVI/release_marker=RC-42 и одну real completed seed pair. Query SHALL спрашивать обработку loading/error/success текущего экрана, учитывать task/architecture и называть project/release без подстановки exact values в question. Оба profiles SHALL использовать ru: A technical/concise/summary_bullets(max=3)/no_emoji/skip_basic_explanations, B explanatory/detailed/teaching_sections/no_emoji/explain_unfamiliar_terms. Принадлежность fixture SHALL определяться typed fields, не name.

#### Scenario: Both probes receive the same frozen facts and history
- **WHEN** после Freeze выполнены A и B с explicit select между ними
- **THEN** memory snapshot, transcript roles/text/order, query, model и все non-profile settings совпадают; только profile-derived instructions отличаются в actual model requests

#### Scenario: Memory mutation makes a checkpoint historical
- **WHEN** после Freeze выполнен ordinary Send или изменена Memory
- **THEN** прежний checkpoint не используется для новых probes, historical observations сохраняют свою маркировку; требуется explicit новая подготовка/Freeze

#### Scenario: Editing a fixture does not silently change the comparison
- **WHEN** изменена revision A или B после Freeze
- **THEN** probe старого comparison отклонён как stale, новая версия не подставляется молча и прежний результат не переименовывается в новый

### Requirement: Probes are side effect free and profile switching stays explicit

A/B probe SHALL выполняться только для явно активированного соответствующего Profile и подходящего frozen snapshot. Каждая probe SHALL делать максимум одну generation без commit, Profile edit/select, memory mutations или изменения owner/task/session/binding. A reply SHALL NOT становиться transcript или input B. Freeze/probe SHALL NOT автоматически переключать active Profile. Повторные attempts SHALL запускаться только явно и оставаться различимыми по attempt_id.

#### Scenario: Probe A cannot teach probe B
- **WHEN** A завершилась успешно, затем пользователь явно выбрал B и запустил B
- **THEN** A question/reply/observations отсутствуют в input B; оба before/after memory snapshots совпадают с frozen snapshot

#### Scenario: Wrong active profile prevents dispatch
- **WHEN** запрошена B при active A
- **THEN** возвращается mismatch без provider call, автоматического select B и других effects

#### Scenario: Probe failure preserves domain state
- **WHEN** probe failed/refused/incomplete либо completed с нарушением format
- **THEN** Memory, profiles и binding неизменны; hidden retry/repair отсутствует

### Requirement: Actual dispatch observations separate selection assembly and output

Каждая dispatched попытка SHALL сохранять immutable observation с использованными profile ID/revision/typed values, binding revision, rendered instructions, selected/excluded Memory sources, exact messages/query/settings и actual outcome. Inspector SHALL соответствовать реальным аргументам provider-neutral generation boundary, не повторно построенному current preview. Selection checks, assembly checks, deterministic output checks и human observations SHALL быть отдельными группами. Name SHALL показываться только metadata. Secrets/provider headers SHALL NOT отображаться. Pre-dispatch rejection SHALL обозначать actual assembly not_dispatched, а не успешный actual call.

#### Scenario: Correct assembly and wrong response are independent
- **WHEN** actual instructions соответствуют Mentor, но completed response не содержит требуемых headings
- **THEN** selection/assembly остаются успешными, конкретный heading check failed; это не storage failure

#### Scenario: Current profile differs from the last attempt
- **WHEN** после ответа профиль отредактирован или переключён
- **THEN** inspector показывает snapshot использованной попытки и отмечает историчность, не заменяет её instructions текущими

#### Scenario: Capture is verified against the delegate
- **WHEN** request записан независимым recording provider client
- **THEN** captured instructions/messages/settings точно совпадают с observation, включая query и memory blocks

### Requirement: Natural Markdown supports narrow deterministic adherence checks

Model response SHALL оставаться natural Markdown без общей Structured Output/JSON schema. Backend SHALL отдельно проверять supported summary heading/nonempty summary/max list count, teaching headings/order/nonempty sections, no_emoji и literal memory marker presence. Summary instructions SHALL задавать H2 Вывод/Summary и от нуля до max_bullets items; teaching SHALL задавать H2 Идея/Почему/Пример/Ограничения либо Idea/Why/Example/Limitations по language. При count/heading parsing SHALL учитываться fenced code: внутри него markers не являются структурой; code example SHALL считаться содержимым section. No-emoji check SHALL детерминированно проверять весь raw reply только в пределах небольшого документированного/testable набора Unicode code points/простых sequences, достаточного для Day 12 fixtures. Успех SHALL означать отсутствие emoji из объявленного набора без заявления полного Unicode Emoji compliance; полноценный compliance engine и тяжёлая dependency ради этого SHALL NOT требоваться. Marker checks SHALL называться проверками упоминания, а не доказательством semantic correctness.

#### Scenario: Code headings do not satisfy teaching sections
- **WHEN** ожидаемые headings встречаются только внутри fenced code
- **THEN** required sections check не проходит, хотя текст заголовков присутствует в reply

#### Scenario: Numbered lists do not evade the item limit
- **WHEN** summary reply содержит больше max_bullets list items вне fenced code, в том числе numbered/nested items
- **THEN** list count check failed и показывает measured count/limit

#### Scenario: Mentioning MVI is not scored as correct MVI design
- **WHEN** response содержит все четыре exact markers, но предлагает сомнительное решение
- **THEN** marker checks отражают только наличие текста, semantic usefulness и use of MVI остаются human observations

### Requirement: Human observations and unavailable measurements are explicit

Language correctness, tone, appropriate detail, explanation of unfamiliar terms, skipping basics и semantic quality SHALL оставаться human observations без automatic score или LLM-as-judge. UI SHALL поддерживать необязательные заметки человека, связанные с attempt. Единый synthetic personalization-quality score SHALL отсутствовать. Failed/refused/incomplete dispatched response SHALL сохранять доступные selection/assembly checks; output adherence SHALL быть unavailable с причиной, не fake zero. Raw available outcome SHALL не реконструироваться из expected fixtures.

#### Scenario: Incomplete reply has no invented adherence score
- **WHEN** provider вернул incomplete
- **THEN** selection/assembly evidence доступно, output checks unavailable, причина показана; automatic повтор отсутствует

#### Scenario: Human note is an observation rather than model input
- **WHEN** пользователь добавил замечание о tone/полезности ответа A
- **THEN** заметка связана с A attempt и не входит в Memory, Profile или input B

### Requirement: Ordinary Send commits independently from controlled comparison

Ordinary Send SHALL использовать current Profile и current Memory через общий normal conversation lifecycle. Только completed пригодная reply SHALL сохранять atomic user/assistant pair; failure SHALL сохранять прежнюю историю. Profile adherence violations SHALL быть observations и SHALL NOT вводить новый commit gate или validation/retry framework. Ordinary Send SHALL NOT включаться в strict A/B, поскольку меняет transcript. Следующий Send после switch SHALL автоматически использовать новый Profile без reset предыдущей history.

#### Scenario: Completed response with format violation remains an ordinary turn
- **WHEN** normal Send вернул completed пригодный text, нарушающий bullet limit
- **THEN** настоящая pair committed один раз, violation показан отдельно, Profile/Working/Long-term не меняются

#### Scenario: Failed normal request does not undo explicit profile edit
- **WHEN** после сохранённого edit активного Profile Send failed
- **THEN** profile edit остаётся durable, новая conversation pair отсутствует

### Requirement: Restart restores domain state without replay or fabricated results

Backend restart и Android cold start SHALL восстанавливать same profiles/revisions, active binding, memory owner/task/session identities и три слоя через read-only requests без generation/count/extraction/replay. Runtime comparison checkpoints/results/human notes SHALL не требоваться для restore; их отсутствие SHALL показываться как отсутствие measurements. Existing suitable Memory SHALL допускать explicit new Freeze без повторного seed. Потерянный HTTP outcome SHALL разрешаться read/reconciliation без повторения mutation/Send/probe.

#### Scenario: Nonempty profiled memory survives restart
- **WHEN** после непустой Memory и выбранного B перезапущены backend и Android
- **THEN** profile records/binding и Memory совпадают с before state; provider calls для restore равны нулю, исчезнувшие A/B scores не восстанавливаются из fixtures

#### Scenario: Lost switch response is reconciled
- **WHEN** switch committed, но Android не получил response
- **THEN** current read показывает подтверждённый binding без повторного select или создания нового owner
