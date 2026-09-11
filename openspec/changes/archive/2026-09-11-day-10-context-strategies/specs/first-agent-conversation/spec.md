## ADDED Requirements

### Requirement: Day 10 shares agent primitives while isolating strategy state

Day 10 SHALL развивать общий Agent subsystem с прежними generation/validation primitives, без отдельных Agent implementations на Window/Facts/Branching. Стратегии SHALL подключаться только внутри Day 10 namespace по `context-strategies-experiment`; Branching topology SHALL разрешаться отдельно от обычного выбора linear context. Day 02–09 HTTP contracts, payloads, configurations, deadlines, retry semantics и provider call counts SHALL сохраняться. В частности, Day 06–08 full-history, Day 08 counting/pricing/overflow, Day 09 rolling summary и atomic pair lifecycle SHALL оставаться прежними. Optional Structured Output support SHALL не добавлять fields в старые provider payloads. Старые namespaces SHALL NOT получать Facts extraction, branch operations, evaluation calls или новые count requests. Android SHALL по-прежнему не отправлять conversation history.

#### Scenario: Older exact payloads and call counts remain stable
- **WHEN** при подключённом Day 10 выполняются existing Day 02–09 сценарии
- **THEN** exact payload/call-count tests сохраняют прежние результаты, включая отсутствие extraction в старых namespaces

#### Scenario: Day 10 identifiers do not cross namespace boundaries
- **WHEN** Day 10 run ID передан в Day 06–09 API либо старый ID в Day 10 API
- **THEN** чужая history не открывается, provider не вызывается и migration/fallback отсутствует

#### Scenario: Evaluation output is not conversation history
- **WHEN** Day 10 evaluation results сохранены рядом с durable experiment
- **THEN** эти результаты не меняют atomic conversation pair semantics и не становятся source при любом последующем Agent context assembly
