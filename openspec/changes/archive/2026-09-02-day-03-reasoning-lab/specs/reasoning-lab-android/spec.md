## Purpose

Определяет русскоязычный экран существующего Android-приложения, на котором результаты четырёх reasoning-стратегий и их метрики легко сравнить и показать на видео.

## ADDED Requirements

### Requirement: Reasoning Lab is a new screen in the existing app
Приложение SHALL предоставлять отдельный экран «Лаборатория рассуждений» внутри существующего Android-проекта и SHALL сохранять доступ к экрану Day 02 без создания нового app module или Android-проекта.

#### Scenario: User opens the Reasoning Lab screen
- **WHEN** пользователь выбирает раздел «Лаборатория рассуждений» в навигации приложения
- **THEN** отображается новый экран Reasoning Lab
- **AND** пользователь может вернуться к существующему экрану управления ответом

### Requirement: All user-facing Reasoning Lab text is Russian
Экран SHALL использовать русские пользовательские строки и SHALL отображать названия режимов точно как «Прямой ответ», «Пошаговое решение», «Мета-промпт» и «Группа экспертов». Технические enum и идентификаторы SHALL оставаться внутренними и не заменять русские подписи.

#### Scenario: Strategy names are localized
- **WHEN** результаты четырёх стратегий показаны пользователю
- **THEN** каждая карточка имеет требуемое русское название режима

#### Scenario: Errors and metrics have Russian labels
- **WHEN** экран показывает метрики, loading, empty state или ошибку
- **THEN** все поясняющие пользователю подписи и сообщения написаны по-русски

### Requirement: User launches all strategies together
Экран SHALL иметь основную кнопку «Запустить все стратегии», которая одним пользовательским действием запускает batch Reasoning Lab. Во время выполнения повторный запуск SHALL быть заблокирован, а экран SHALL явно показывать состояние загрузки.

#### Scenario: Successful launch
- **WHEN** пользователь нажимает «Запустить все стратегии» в idle-состоянии
- **THEN** приложение запрашивает полный batch у backend и показывает индикатор выполнения
- **AND** после ответа отображает результаты всех полученных стратегий

#### Scenario: Repeated tap while loading
- **WHEN** batch уже выполняется
- **THEN** кнопка запуска недоступна и дублирующий запрос не отправляется

### Requirement: Results are readable and comparable
Экран SHALL показывать отдельную читаемую Material 3 карточку для каждой стратегии с выбранными фичами, total cost, total value, explanation, latency, token usage и API call count. Карточка SHALL явно показывать «Правильно» или «Неправильно» и SHALL оставаться читаемой в вертикальной прокрутке на телефонном экране для видеодемонстрации.

#### Scenario: Correct result card
- **WHEN** backend возвращает `correct=true`
- **THEN** карточка заметно показывает статус «Правильно» и все доступные решение и метрики

#### Scenario: Incorrect result card
- **WHEN** backend возвращает `correct=false`
- **THEN** карточка заметно показывает статус «Неправильно» и доступную причину verifier или upstream error

#### Scenario: Partial backend failure
- **WHEN** одна стратегия содержит ошибку, а другие имеют решения
- **THEN** экран показывает ошибку внутри соответствующей карточки и сохраняет успешные карточки остальных стратегий

### Requirement: Generated meta-prompt can be inspected
Карточка «Мета-промпт» SHALL предоставлять элемент управления для раскрытия и скрытия сгенерированного prompt без перегрузки основного списка результатов.

#### Scenario: User expands the generated prompt
- **WHEN** META_PROMPT результат содержит `generated_prompt` и пользователь нажимает элемент просмотра
- **THEN** экран показывает полный prompt в выделяемом прокручиваемом тексте
- **AND** повторное действие скрывает его

### Requirement: Android never handles the OpenAI credential
Reasoning Lab Android client SHALL обращаться только к локальному FastAPI backend и SHALL не запрашивать, не хранить и не передавать OpenAI API key.

#### Scenario: App runs against emulator backend
- **WHEN** пользователь запускает Reasoning Lab на Android Emulator
- **THEN** запрос направляется на существующий backend URL `http://10.0.2.2:8000/`
- **AND** в Android UI, DTO и настройках отсутствует поле для `OPENAI_API_KEY`
