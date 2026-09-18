## ADDED Requirements

### Requirement: Day 15 presents controlled task progress and bounded evidence clearly

Каталог и экран SHALL показывать «День 15» и «Контролируемый жизненный цикл задачи», с обозначением Agent Playground. Main SHALL объяснять Task, текущий этап/шаг, следующее действие, активный Profile и действующие ограничения понятными русскими labels. UI SHALL различать «Утвердить план», «Уточнить требования», «Реализация готова», «Подтвердить проверку», «Проверка не пройдена», «Возврат применён», «Переход отклонён», «Задача приостановлена», «Задача возобновлена» и «Задача завершена». Validation confirmation SHALL называться подтверждением пользователя/application, не автоматической проверкой кода. Technical error SHALL отличаться от policy refusal и invalid event. Allowed recovery SHALL показываться как применённый возврат по графу с новым этапом и следующим действием, не как invalid transition или technical error; forward, recovery и rejection SHALL иметь разные понятные outcomes. Evidence SHALL явно ограничивать hard checks структурированными decisions; free-form prose SHALL NOT называться полностью проверенным. Main SHALL оставаться task-oriented, а canonical values/IDs/raw output SHALL сохраняться без искажения в Raw Debug.

#### Scenario: Silent video communicates the rejected jump
- **WHEN** пользователь выполняет educational invalid event
- **THEN** экран объясняет attempted action, причину отказа, текущий этап и следующий разрешённый шаг без README или голосового комментария

#### Scenario: Silent video communicates an allowed recovery
- **WHEN** пользователь явно нажимает «Проверка не пройдена» в Validation
- **THEN** normal result объясняет применённый возврат к реализации и следующий шаг исправления; Inspector различает Recovery applied и rejection, conversation не меняется

#### Scenario: Bounded success does not claim semantic certification
- **WHEN** accepted conversation candidate прошёл четыре predicates
- **THEN** Inspector сообщает о проверке четырёх coding decisions, не обещая проверку всего prose, архитектуры исходников или реальной оплаты

#### Scenario: Provider absence is a normal lifecycle outcome
- **WHEN** показан applied forward, applied recovery или rejected lifecycle event
- **THEN** provider обозначен «Не требовался», а conversation commit — «Не применимо», без ложной provider error
