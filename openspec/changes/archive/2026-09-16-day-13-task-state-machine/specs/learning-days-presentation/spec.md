## ADDED Requirements

### Requirement: Day 13 presentation separates task facts workflow position and model observations

Каталог и экран SHALL показывать «День 13» и «Состояние задачи / Task State Machine». Тексты SHALL различать Memory как сведения, Profile как поведение ответа и Task State как положение в workflow. UI SHALL показывать понятные labels этапа, шага, ожидаемого действия, статуса, Pause/Resume и явных подтверждений. VALIDATION_CONFIRMED SHALL называться подтверждением проверки пользователем/application, не автоматическим Validator pass. New Conversation SHALL не называться reset задачи. Model adherence SHALL не объединяться с FSM correctness; unavailable SHALL не становиться нулём. Canonical tokens, exact markers, raw replies и IDs SHALL сохраняться в inspector без искажения.

#### Scenario: User understands paused expected action
- **WHEN** показан PAUSED execution
- **THEN** expected action подписано как действие после возобновления, composer остаётся доступным, UI не утверждает, что любой ответ модели автоматически означает progress

#### Scenario: Confirmation does not imply automatic validation
- **WHEN** пользователь находится на VALIDATION_CHECK
- **THEN** доступное событие обозначено как explicit confirmation, без обещания semantic/code validation backend-ом

#### Scenario: Narrow screen keeps controls and evidence usable
- **WHEN** Day 13 открыт на узком экране с увеличенным шрифтом и клавиатурой
- **THEN** labels/replies переносятся, controls/composer/inspector доступны прокруткой и не перекрываются системными панелями
