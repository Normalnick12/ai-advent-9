# Spec Delta

## ADDED Requirements

### Requirement: Day 18 provides independent dependency watch navigation without replay
Каталог SHALL добавлять Day 18 «Планировщик и фоновые задачи» после Day 17, сохраняя прежние карточки и порядок. Day 18 SHALL иметь независимые destination/state/receipt namespace. Открытие SHALL восстанавливать только локальные сохранённые сведения без create, summary generation или provider request. Возврат из Inspector SHALL вести в тот же Day 18 main, из main — в каталог, с обычным приоритетом закрытия IME. Navigation и Activity recreation SHALL сохранять текущую попытку и draft в процессе без отмены/replay. Day 16 SHALL оставаться самостоятельным CLI-заданием; Days 11–17 contracts MUST NOT изменяться из-за нового watch lab.

#### Scenario: Open from catalog while backend is unavailable
- **WHEN** пользователь выбирает Day 18 при недоступном backend
- **THEN** lab открывается с draft/локальным receipt без network operation, возврат к дням доступен

#### Scenario: Navigate or rotate during create
- **WHEN** пользователь выходит в каталог, возвращается либо поворачивает устройство во время отправки
- **THEN** отображается та же выполняющаяся попытка либо её результат без второго POST

#### Scenario: Older labs remain independent
- **WHEN** пользователь создал watch в Day 18 и открыл Day 17 или прежний урок
- **THEN** прежние drafts, identities, результаты и операции не заменяются Day 18 state
