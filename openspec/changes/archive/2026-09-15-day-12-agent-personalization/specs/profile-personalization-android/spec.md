## Purpose

Определяет Android лабораторию Day 12 с реальным typed profile editor, явным выбором профиля и сравнением ответов при неизменной памяти без смешения фактов и предпочтений поведения.

## ADDED Requirements

### Requirement: Users can create edit and select typed profiles

Day 12 SHALL предоставлять список/selector профилей текущего owner и форму create/edit для name, language, tone, verbosity, response_format и всех трёх constraints. Summary format SHALL позволять max_bullets 1–5; teaching format SHALL не отправлять это поле. Оба explanation flags SHALL быть выбираемыми одновременно. Форма SHALL NOT быть generic JSON/system-prompt editor. Compact Engineer/Mentor templates SHALL предзаполнять тот же editor и сохраняться теми же operations, что custom profiles. Create SHALL NOT автоматически менять active binding. UI SHALL показывать confirmed backend selection, а не неподтверждённый optimistic выбор.

#### Scenario: A custom profile is usable outside fixtures
- **WHEN** пользователь создаёт допустимый custom Profile, явно выбирает его и отправляет обычный вопрос
- **THEN** selector показывает подтверждённый profile, Send использует его typed settings и не требует соответствия A/B fixtures

#### Scenario: Both explanation constraints remain available
- **WHEN** в editor включены пропуск базовых Android/Kotlin объяснений и пояснение новых терминов
- **THEN** UI не объявляет semantic conflict, сохраняет оба flags и показывает подтверждённые backend values

#### Scenario: Editing does not accidentally change selection
- **WHEN** пользователь редактирует неактивный Profile или меняет только name
- **THEN** active selection прежняя; rename меняет UI label, но не изображается новой поведенческой инструкцией

### Requirement: Main screen combines compact preparation comparison and ordinary Send

Main SHALL показывать active Profile, entry в editor, краткую Memory summary, компактные explicit setup/freeze/A/B controls, две response cards и минимальный ordinary composer. Большой A–E stepper SHALL не требоваться. UI SHALL различать uninitialized Memory, profiles missing, unselected Profile, ready и recovery/busy. Memory actions SHALL показывать target layer/key/value; existing data SHALL не перезаписываться скрыто. New Conversation/New Task/Clear Long-term SHALL быть доступны с пояснением независимости Profile.

#### Scenario: Profile switch visibly preserves memory
- **WHEN** пользователь переключает Profile при непустой Memory
- **THEN** active label обновляется после подтверждения, Memory cards и current task/session остаются прежними, новый разговор не появляется

#### Scenario: Partial preparation is recoverable
- **WHEN** Memory уже initialized, но Profile creation не завершилось
- **THEN** UI показывает сохранённую Memory и недостающую подготовку, не предлагает скрытый reset и не отправляет generation

### Requirement: Controlled comparison displays one frozen snapshot and explicit actions

Перед Freeze UI SHALL показывать raw seed acknowledgment для human review и одинаковые Memory/query/settings сравнения. Выбор A/B slots SHALL быть явным; несовместимые typed fields/revisions SHALL обозначаться, без определения fixture по name. Select и probe SHALL быть отдельными explicit actions; кнопка probe SHALL NOT скрыто менять Profile. A/B cards SHALL относиться к одному comparison_id и своим attempt IDs; stale/mixed snapshots SHALL не изображаться controlled pair. Ordinary Send SHALL быть явно отделён от side-effect-free comparison.

#### Scenario: B is not automatically selected by probe
- **WHEN** active A, а пользователь смотрит карточку B
- **THEN** UI предлагает явный выбор B перед проверкой; просмотр/переход к карточке не меняет binding и не вызывает generation

#### Scenario: Seed response is reviewed without editing it
- **WHEN** seed completed перед Freeze
- **THEN** raw response виден, пользователь может оценить нейтральность; UI не заменяет его искусственным acknowledgment

#### Scenario: Normal chat makes an old comparison historical
- **WHEN** после A/B выполнен ordinary Send
- **THEN** старые result cards сохраняют свою snapshot маркировку, а дальнейшие controlled probes требуют подходящего нового Freeze

### Requirement: Responses and observations do not collapse into a quality score

UI SHALL показывать natural Markdown replies и отдельные группы Selection, Assembly, deterministic adherence, marker presence и Human observations. Human observations SHALL позволять optional plain text notes для tone/explanation/semantic usefulness без числового рейтинга. Общий personalization-quality score SHALL отсутствовать. Failed/refused/incomplete output SHALL обозначаться unavailable с причиной, не 0%. Completed violation SHALL не скрывать raw response и не превращаться в memory error.

#### Scenario: Correct request and noncompliant output remain distinct
- **WHEN** backend сообщает successful selection/assembly и failed section check
- **THEN** UI показывает оба независимых результата и исходный ответ, не объявляет всю персонализацию успешно пройденной либо сломанной памятью

#### Scenario: Output failure does not erase input evidence
- **WHEN** A generation incomplete, а selection/assembly подтверждены
- **THEN** input checks видны, output checks имеют unavailable/reason, human note можно связать с попыткой без выдуманного score

### Requirement: Inspector shows the immutable request actually dispatched

Inspector SHALL показывать captured profile ID/revision/typed values, binding revision, rendered profile instructions, selected/excluded Memory sources, exact query/messages/settings, outcome и per-check evidence соответствующей попытки. Current preview SHALL отличаться от actual captured request. Изменение current Profile/Memory SHALL NOT переписывать observation. Secrets и provider headers SHALL отсутствовать. Полные IDs и technical details SHALL находиться в inspector, не загромождая main flow.

#### Scenario: Rename after response does not rewrite the request
- **WHEN** profile переименован после ответа, затем открыт inspector прежней попытки
- **THEN** видны metadata и instructions использованного snapshot, а current изменённое состояние обозначается отдельно

#### Scenario: Rejection before dispatch has no fake request receipt
- **WHEN** backend отклонил stale probe до вызова модели
- **THEN** UI показывает причину и not_dispatched, не выдаёт preview за отправленный запрос

### Requirement: Backend is authoritative across navigation cold start and recovery

Opening/cold start SHALL читать backend profiles/binding/Memory без create/select/Send/probe. UI drafts SHALL не заменять durable Profile до подтверждённого save. Во время busy/recovery conflicting actions SHALL блокироваться локально, backend conflict остаётся authoritative. При неизвестном исходе операции UI SHALL перечитать current state без automatic replay, сохранив честное обозначение unknown outcome. После process restart runtime comparison/results/notes могут отсутствовать и SHALL NOT восстанавливаться из expected fixtures. In-process navigation/rotation SHALL сохранять draft/editor state, observations и выполняющуюся попытку без повторного dispatch.

#### Scenario: Cold start restores selection without replay
- **WHEN** приложение запущено заново с сохранённым active B
- **THEN** selector/Memory восстановлены read-only, generation и повторное создание fixtures отсутствуют, утраченные результаты обозначены непроверенными

#### Scenario: Lost edit response causes read rather than retry
- **WHEN** save response не получен
- **THEN** UI перечитывает confirmed profile/binding, не отправляет edit автоматически и не считает draft сохранённым без подтверждения

#### Scenario: Rotation during generation does not create another request
- **WHEN** устройство повёрнуто или пользователь вернулся из каталога во время Send/probe
- **THEN** сохраняется та же попытка или её результат, второй provider request не появляется
