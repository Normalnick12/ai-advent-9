## ADDED Requirements

### Requirement: Day 11 presentation explains layers and independent checks

Каталог и Day 11 main SHALL показывать «День 11» и название «Модель памяти агента». Описание SHALL объяснять отдельную память разговора, задачи и владельца и её влияние на context/response. Статические labels SHALL быть русскими; cards SHALL включать понятные названия «Краткосрочная», «Рабочая», «Долговременная» с Short-term/Working/Long-term как пояснениями. Exact markers, technical keys и model replies SHALL сохраняться без перевода. Подписи «Сохранено», «Выбрано в контекст», «Исключено», «Доступно в запросе», «Использовано в ответе» SHALL различать хранение, selection и output. New SHALL не называться удалением. Узкие экраны/увеличенный шрифт SHALL сохранять читаемость карточек, inspector и actions.

#### Scenario: User distinguishes the three scopes
- **WHEN** пользователь читает Day 11 cards
- **THEN** понимает связь разговора с Short-term, задачи с Working и владельца с Long-term; durable Short-term не называется RAM-only

#### Scenario: Excluded does not mean deleted
- **WHEN** MVVM исключено из effective context либо прежняя session стала inactive
- **THEN** UI называет данные сохранёнными и объясняет исключение, не сообщает их удаление

#### Scenario: Russian labels preserve exact evidence
- **WHEN** UI показывает ORION-17, RC-42 и Сбой-47 рядом с переведёнными labels
- **THEN** inspector, Send и verification сохраняют exact исходные значения

#### Scenario: Narrow phone remains usable
- **WHEN** Day 11 открыт на узком экране с увеличенным шрифтом
- **THEN** заголовки/values переносятся, controls доступны прокруткой и не перекрываются системными панелями
