## ADDED Requirements

### Requirement: Day 12 presentation separates profile preferences memory facts and observed adherence

Каталог и main Day 12 SHALL показывать «День 12» и «Персонализация ассистента». Описание SHALL объяснять пользовательские настройки поведения поверх памяти и сравнение разных profiles при одинаковом контексте. Русские labels SHALL различать «Активный профиль», «Создать профиль», «Редактировать профиль», «Выбор профиля», «Сборка запроса», «Проверки ответа», «Наблюдения человека» и Memory summary. Profile switch SHALL не называться новым разговором/reset. Human notes SHALL не называться automatic score. Model replies, exact markers, IDs и technical values SHALL сохраняться без перевода; unavailable SHALL не становиться нулём.

#### Scenario: User understands personalization without a system prompt editor
- **WHEN** пользователь открывает Day 12 и editor
- **THEN** видит понятные typed controls языка/тона/подробности/формата/ограничений, а name обозначен названием профиля, не инструкцией модели

#### Scenario: Shared memory and different presentation are visible
- **WHEN** показаны A/B на одном comparison snapshot
- **THEN** UI объясняет одинаковую Memory и различающиеся preferences, показывает natural replies и раздельные checks без общего процента качества

#### Scenario: Narrow screen keeps actions usable
- **WHEN** Day 12 открыт на узком экране с увеличенным шрифтом
- **THEN** длинные names/replies/labels переносятся, editor/selector/comparison/inspector доступны прокруткой и не перекрываются системными панелями
