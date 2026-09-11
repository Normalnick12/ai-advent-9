## ADDED Requirements

### Requirement: Day 10 presentation distinguishes strategies and measured results

Каталог и main Day 10 SHALL показывать «День 10» и полное название «Управление контекстом: разные стратегии». Описание SHALL объяснять сравнение окна, structured facts и независимых веток без summary/compression и обещания победителя. Статические labels SHALL быть русскими; raw fixtures, replies, keys и typed values SHALL не изменяться ради compact presentation или локализации. Main SHALL иметь понятные labels «Окно», «Факты», «Ветки», «Показать исходное сообщение», «Создать checkpoint», «Проверить ТЗ A», «Проверить ТЗ B». Dashboard SHALL называться «Сравнение стратегий» и возвращать «Назад к сценарию». Неприменимые/unavailable metrics SHALL иметь явную подпись вместо нуля.

#### Scenario: Day 10 is distinct from compression
- **WHEN** пользователь просматривает каталог и открывает Day 10
- **THEN** номер и полное название совпадают, описание отличает три strategies от summary Day 09, а layout сохраняет перенос длинного названия

#### Scenario: Metric labels do not overclaim
- **WHEN** пользователь видит N/11 и token totals
- **THEN** подписи говорят о требованиях в конкретном ТЗ и сохранности перед evaluation, отличают actual tokens от last-context measurement и не называют N/11 общим качеством модели

#### Scenario: Compact fixture presentation preserves raw values
- **WHEN** UI отображает «6 недель» или «Вход по magic link» вместо полного raw fixture
- **THEN** раскрытие и Send сохраняют исходные deadline_weeks=6 и auth=magic_link без переписывания message
