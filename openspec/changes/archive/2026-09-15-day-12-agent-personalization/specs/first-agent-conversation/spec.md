## ADDED Requirements

### Requirement: Day 12 personalizes through composition while preserving shared conversation semantics

Day 12 SHALL переиспользовать общий generation и atomic conversation pair lifecycle в отдельном namespace по profile-personalization-experiment. Каждый Day 12 request SHALL получать current Profile и selected Memory, ordinary completed пригодный ответ SHALL сохранять одну настоящую pair, controlled probe SHALL оставаться без commit. Profile selection/edits SHALL не менять session/task/owner или Memory. Day 02–11 API contracts, exact payloads, configurations, retries/deadlines и call counts SHALL сохраняться; Day 12 profile instructions/operations SHALL NOT попадать в старые namespaces. Никакие старые данные SHALL не мигрироваться автоматически. Android SHALL NOT отправлять history, raw instructions, provider settings или credentials.

#### Scenario: Old requests remain unchanged with Day 12 enabled
- **WHEN** при включённом Day 12 выполняются существующие Day 06–11 normal/evaluation scenarios
- **THEN** сохраняются прежние input/config/call counts, memory selection и atomic commits; Profile subsystem не меняет старое поведение

#### Scenario: Ordinary personalization and probes share generation semantics
- **WHEN** один и тот же active Profile используется для normal Send и side-effect-free probe
- **THEN** оба получают выбранные typed preferences и Memory через общий generation contract; только normal completed пригодная pair становится transcript

#### Scenario: Namespace identifiers cannot open another lesson
- **WHEN** Day 12 session/profile identity передана старому API либо старый session ID использован как Day 12 target
- **THEN** чужие данные не читаются/изменяются, generation/fallback отсутствуют
