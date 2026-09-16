## ADDED Requirements

### Requirement: Day 13 composes task state without changing shared agent lifecycle

Day 13 SHALL использовать существующие общие generation, context preparation и atomic conversation pair primitives в отдельном namespace по task-state-experiment. Ordinary Send, включая PAUSED conversation, SHALL сохранять только completed пригодную pair; probes SHALL оставаться без commit. State events SHALL быть отдельными explicit operations, не ветками model output processing или результатом conversation commit. Task State SHALL не требовать второго Agent stack. Day 02–12 API contracts, exact payloads, settings, retries/deadlines, provider call counts и storage semantics SHALL сохраняться; State instructions SHALL не попадать в старые namespaces. Android SHALL не передавать raw history/instructions/provider config/credentials. Conversation commit и State update SHALL не объявляться общей атомарной операцией Day 13.

#### Scenario: Shared generation preserves old experiments
- **WHEN** при подключённом Day 13 выполнены существующие Day 06–12 generation/comparison scenarios
- **THEN** прежние input/config/call-count и commit contracts сохранены, State section присутствует только в Day 13

#### Scenario: Reply and progress are separate operations
- **WHEN** Day 13 normal Send вернул пригодный completed ответ о готовой реализации
- **THEN** conversation pair committed, State прежний до отдельного explicit IMPLEMENTATION_READY

#### Scenario: Failed generation and probes preserve conversation semantics
- **WHEN** Day 13 ordinary response failed/incomplete/refused либо выполнен non-committing probe
- **THEN** новая confirmed pair отсутствует и State не меняется

#### Scenario: Namespace identity does not select foreign state
- **WHEN** Day 13 task/session/profile ID передан старому namespace либо чужой ID использован в Day 13
- **THEN** чужие данные не читаются/изменяются, generation и fallback отсутствуют
