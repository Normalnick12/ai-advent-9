## ADDED Requirements

### Requirement: Day 11 layers extend the shared conversation lifecycle in isolation

Day 11 SHALL использовать общий Agent generation/validation и atomic conversation pair lifecycle в отдельном namespace по memory-layers-experiment. Day 02–10 API contracts, exact payloads, settings, deadlines, retry semantics и provider call counts SHALL сохраняться. Day 11 memory blocks, explicit memory mutations и verification SHALL NOT появляться в старых namespaces. Android SHALL NOT передавать history, instructions, model settings или credentials. Обычный Day 11 turn SHALL сохранять только completed пригодную user/assistant pair, а verification SHALL оставаться без conversation commit. New Conversation/New Task Day 11 SHALL NOT менять destructive delete semantics старых Day.

#### Scenario: Older experiments remain unchanged
- **WHEN** при подключённом Day 11 выполняются existing Day 06–10 normal/evaluation scenarios
- **THEN** сохраняются прежние payload/call-count contracts, full-history/compression/window/facts/branching semantics и atomic commits

#### Scenario: Identity lookup does not cross Day namespaces
- **WHEN** Day 11 identity передана старому API либо старый session/run ID передан Day 11
- **THEN** чужие данные не читаются/изменяются, provider calls и global fallback отсутствуют

#### Scenario: Normal failure and verification preserve pair semantics
- **WHEN** Day 11 ordinary generation failed либо завершилась side-effect-free verification
- **THEN** новая confirmed conversation pair отсутствует; ранее committed raw history не изменена
