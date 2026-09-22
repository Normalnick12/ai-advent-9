## ADDED Requirements

### Requirement: Day 17 provides independent MCP lab navigation without replay
Каталог SHALL добавлять доступный Day 17 после Day 15, сохраняя существующий порядок и destinations предыдущих Days. Day 16 остаётся самостоятельным CLI-заданием. Day 17 SHALL открывать отдельный MCP lab, не используя destination/state Day 15 Playground. Открытие и возврат SHALL быть read-only navigation и MUST NOT вызывать generation.

#### Scenario: Open Day 17 from the catalog
- **WHEN** пользователь выбирает Day 17 в каталоге
- **THEN** открывается отдельный Day 17 lab и до нажатия отправки backend operation не выполняется

#### Scenario: Return and reopen without affecting other days
- **WHEN** пользователь возвращается из Day 17 в каталог и повторно открывает lab
- **THEN** сохраняется доступное состояние его session без replay
- **AND** навигация и состояние прежних Days, включая Day 15 Playground, остаются независимыми
