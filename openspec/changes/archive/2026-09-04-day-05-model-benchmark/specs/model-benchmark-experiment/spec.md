## Purpose

Определяет воспроизводимое сравнение трёх моделей на одном benchmark: независимую проверку пяти задач, честные состояния завершения, фактический usage и стоимость каждого запроса.

## ADDED Requirements

### Requirement: Backend owns the compatible model catalog
Backend SHALL предоставлять каталог разрешённых моделей через `GET /api/v1/model-benchmark/catalog` без OpenAI-вызовов. Каталог SHALL содержать model id, отображаемое имя, описание tier, доступные для каждой роли ids и defaults: `economical` — `gpt-5.6-luna`, `balanced` — `gpt-5.6-terra`, `flagship` — `gpt-5.6-sol`. Начальный allowlist SHALL включать только эти три модели, совместимые с общими параметрами и имеющие настроенные официальные тарифы. Каждая роль SHALL позволять выбрать любую из этих моделей; роль обозначает слот сравнения и его default, а не меняет параметры запроса.

#### Scenario: Client loads defaults
- **WHEN** клиент получает каталог
- **THEN** получает три роли с defaults Luna/Terra/Sol, разрешённые ids и общую read-only конфигурацию benchmark
- **AND** OpenAI API call count равен нулю

#### Scenario: User selects the same allowed model twice
- **WHEN** два слота содержат один разрешённый model id
- **THEN** backend сохраняет оба слота и выполняет отдельный вызов для каждого без дедупликации или изменения параметров

### Requirement: One explicit run compares exactly three selected slots
`POST /api/v1/model-benchmark/run` SHALL принимать ровно по одному model id для каждой из трёх ролей. Backend SHALL до любых OpenAI-вызовов проверять структуру, allowlist и наличие тарифной конфигурации выбранных моделей; неизвестные поля, произвольный prompt, настройки запроса и неизвестные model ids SHALL отклоняться. Валидный запуск SHALL возвращать три результата в порядке economical, balanced, flagship с идентификатором запуска и снимком применённой конфигурации. Метаданные каждого результата SHALL относиться к выбранной модели именно этого запуска.

#### Scenario: Valid comparison
- **WHEN** клиент явно запускает сравнение с тремя разрешёнными selections
- **THEN** backend выполняет по одному Responses API call на слот и возвращает три изолированных результата в стабильном порядке

#### Scenario: Invalid selection or configuration
- **WHEN** отсутствует роль, передан неизвестный id, лишнее поле или для выбранной модели нет тарифа
- **THEN** запрос отклонён до отправки в OpenAI с безопасной диагностикой
- **AND** ни одна модель не вызывается

### Requirement: Only model id varies between upstream requests
Каждый слот SHALL получать все пять задач в одном Responses API request. Общий payload SHALL сохранять точный prompt, instructions и strict JSON Schema финального третьего probe. Для всех слотов SHALL применяться `reasoning.effort=medium`, `max_output_tokens=6000`, `store=false`, `service_tier=default`; `temperature`, `top_p`, tools, conversation state, дополнительные reasoning/cache-параметры SHALL отсутствовать. После удаления `model` payload трёх вызовов SHALL быть равным. Автоматические SDK/application retries, repair-вызовы, смена модели, снижение параметров и скрытый fallback SHALL отсутствовать. Benchmark и параметры SHALL быть read-only в Day 05.

#### Scenario: Equal envelopes
- **WHEN** запускается сравнение default моделей
- **THEN** три отправленных payload отличаются только `model`, а каждый содержит все пять задач
- **AND** отсутствуют model-specific instructions и значения temperature/top_p

#### Scenario: Provider rejects a model or parameter
- **WHEN** OpenAI отклоняет один вызов
- **THEN** этот слот возвращает ошибку первого вызова с API call count 1
- **AND** backend не повторяет вызов и не меняет конфигурацию остальных слотов

### Requirement: Fixed benchmark covers five independent tasks
Benchmark SHALL сохранять следующие пять независимых задач и их данные; точная формулировка canonical prompt SHALL соответствовать финальному probe и фиксируется полностью в design для переноса при apply.

1. Из 240 запросов 35% обслужены из cache без БД, каждый оставшийся делает ровно три запроса к БД; требуется общее число DB requests.
2. Анна, Борис, Вера и Глеб дежурят по одному дню с понедельника по четверг, один человек в день. Анна раньше Бориса; Вера не в понедельник и не в четверг; Глеб ровно на следующий день после Анны. Требуется полное расписание.
3. Budget 15; cost/value: A=4/8, B=6/11, C=5/10, D=3/6, E=7/13, F=2/4, G=4/7, H=5/8. B/E несовместимы; C требует F; A/D несовместимы; G/H несовместимы. Требуется допустимый набор максимальной value при cost <=15.
4. Массив `[7, 2, 5, 1, 8, 3, 6, 4]`, индексация с нуля. В прямом цикле `i=1..7`, если `(a[i-1]+i) mod 3 == 0`, выполнить `a[i]=a[i]+a[i-1]`, иначе `a[i]=a[i-1]-a[i]`. Затем в обратном цикле `i=6..0` для чётного i выполнить `a[i]=a[i]+a[i+1]`, для нечётного — `a[i]=a[i]-a[i+1]`. Всегда используются уже изменённые значения. Вернуть final array и `sum((i+1)*a[i])` по i=0..7.
5. Строки длины 10 над `{A,B,C}`: ровно четыре A, без одинаковых соседей, первый символ не C, для каждого B есть C в одной из двух следующих существующих позиций, ровно две соседние подстроки AB. Если для B, в том числе у конца строки, среди существующих следующих позиций нет C, строка SHALL отклоняться. Требуется число подходящих строк; AB occurrence определяется позицией i с `s[i]=A` и `s[i+1]=B`.

#### Scenario: Canonical benchmark is requested
- **WHEN** backend формирует upstream input
- **THEN** передаётся один неизменяемый текст пяти задач из финального probe
- **AND** ни ожидаемые ответы, ни результаты probes не добавляются к input или instructions

### Requirement: Strict output fixes shape without leaking answers
Одинаковая schema SHALL требовать объект с `task1.database_queries: integer`; `task2.monday/tuesday/wednesday/thursday: string`; `task3.selected_features: string[]`, `total_cost: integer`, `total_value: integer`; `task4.final_array: integer[]`, `checksum: integer`; `task5.count: integer`. Все поля SHALL быть required, каждый объект SHALL запрещать дополнительные поля, `strict=true`. Schema SHALL фиксировать только форму и типы без эталонных значений, перечисления правильных решений или подсказок ответа. Backend SHALL проверять типы без coercion, включая запрет bool вместо integer.

#### Scenario: Structurally valid wrong answer
- **WHEN** модель завершает JSON правильной формы с Task 5 count 21
- **THEN** результат проходит проверку формы, а Task 5 оценивается как incorrect относительно независимо вычисленного эталона

#### Scenario: Malformed or mismatched output
- **WHEN** output нельзя разобрать либо он не соответствует strict форме
- **THEN** quality равна null, все verdict равны `unverified`, а результат обозначен как «Нет проверяемого результата»
- **AND** доступный фактический output сохраняется для просмотра без repair-вызова

### Requirement: Python verifier computes references independently
Backend SHALL вычислять эталоны без LLM-судьи: арифметический расчёт; все 24 перестановки расписания; все 256 subsets фич; прямое выполнение двух циклов; все 59049 строк. Эталоны SHALL вычисляться отдельно от ответов модели и не извлекаться из probe fixtures. Для расписания SHALL приниматься любое полное допустимое распределение без повторов; для оптимизации — любой допустимый набор без дублей с максимальной value и совпадающими пересчитанными totals; порядок выбранных фич не влияет на verdict. Task 4 SHALL быть correct только при совпадении и массива, и checksum. Quality SHALL быть числом correct задач из пяти только для completed полного структурно корректного результата. Backend SHALL возвращать verdict `correct`/`incorrect`/`unverified`, фактический ответ для каждой задачи и verifier answer для каждой incorrect задачи.

#### Scenario: Independent references
- **WHEN** verifier решает canonical benchmark
- **THEN** получает 468; Пн Анна, Вт Глеб, Ср Вера, Чт Борис; A+C+F+G с cost 15/value 29; массив `[22, 15, -10, -10, 11, 18, -28, -12]` с checksum -147; count 24
- **AND** эти значения используются только для проверки и отображения эталонов после ответа, не в модельном prompt/schema

#### Scenario: Incorrect combinatorial count
- **WHEN** completed ответ содержит правильные Task 1–4 и Task 5 count 21
- **THEN** quality равна 4/5, Task 5 имеет verdict incorrect, actual count 21 и verifier count 24

#### Scenario: Optimization data is inconsistent
- **WHEN** модель повторила фичу, нарушила ограничение или сообщила totals, не совпадающие с выбранным набором
- **THEN** Task 3 получает incorrect даже если сообщённая value равна оптимальной

### Requirement: Missing results are not incorrect solutions
Каждый слот SHALL отдельно возвращать нормализованный status, исходный response status при наличии, reason/error, requested model, nullable resolved model, latency и API call count. Incomplete, refusal, timeout, API error и invalid output SHALL приводить к quality null и `unverified`, а не 0/5. Даже syntactically valid output при status incomplete SHALL оставаться непроверенным. Реальный completed ответ с пятью неверными решениями SHALL иметь quality 0/5. Ошибка одного слота SHALL NOT уничтожать результаты остальных. Учёт API calls SHALL отражать фактические попытки: 0 до вызова и 1 после начала единственной попытки, включая timeout; сетевой timeout не означает подтверждённое отсутствие обработки провайдером.

#### Scenario: Output limit is exhausted
- **WHEN** API возвращает incomplete с reason `max_output_tokens`
- **THEN** слот показывает «Нет проверяемого результата», quality null и сохранённый reason/usage/output при наличии
- **AND** этот случай не считается пятью incorrect задачами

#### Scenario: One model fails while two complete
- **WHEN** один вызов завершается timeout или API error, а два других дают валидные ответы
- **THEN** клиент получает все три слота с доступными оценками двух ответов и отдельным непроверенным слотом ошибки

### Requirement: Usage and latency describe each actual API call
Latency SHALL измерять полное ожидание соответствующего OpenAI-вызова монотонными часами, исключая локальный verifier и очередь других моделей. Backend SHALL возвращать фактические input, cached input, cache write, output, reasoning и total tokens; недоступные значения SHALL быть null, а не выдуманными нулями. Reasoning tokens SHALL обозначаться как часть output. Неизвестный usage SHALL сохраняться неизвестным даже при timeout. Конфигурация и метрики SHALL позволять отличить модельный timeout от клиентского transport error.

#### Scenario: Response includes full usage
- **WHEN** API возвращает usage, включая cached input и reasoning details
- **THEN** backend сохраняет эти числа без пересчёта от лимита и показывает per-model latency

#### Scenario: Usage is absent
- **WHEN** API response не получен или не содержит usage
- **THEN** недоступные token counts и cost равны null и не отображаются как бесплатный запрос

### Requirement: Backend prices actual usage from a central official rate catalog
Стоимость SHALL рассчитываться backend в USD по фактическому usage и одной централизованной versioned конфигурации официальных тарифов: input, cached input, cache write, output, источник, дата проверки и применяемый tier. Для standard short-context запросов стоимость SHALL равняться `((I-C-W)*Ri + C*Rc + W*Rw + O*Ro)/1_000_000`, где I включает cached/write tokens, а reasoning уже входит в O. Лимит 6000 SHALL NOT использоваться как фактический O. Backend SHALL возвращать стоимость как decimal string, статус available/unavailable, тарифную модель, rates и источник/дату для объяснения расчёта. Для неизвестного resolved id без явного mapping, неизвестного тарифа/usage или несовместимого service tier cost SHALL быть null с причиной, без молчаливого предположения. При incomplete с известным usage стоимость SHALL по-прежнему вычисляться. Android SHALL только отображать стоимость backend.

#### Scenario: Cache and reasoning billing
- **WHEN** I=1000, C=200, W=100, O=500 и доступны standard Luna rates 0.20/0.02/0.25/1.20 USD за миллион
- **THEN** cost равна 0.000769 USD
- **AND** reasoning, входящий в O, не добавляется второй раз

#### Scenario: Incomplete still consumed tokens
- **WHEN** ответ incomplete имеет известные input/output/cache counters и разрешённый тариф
- **THEN** стоимость вычисляется по ним независимо от отсутствия quality

#### Scenario: Unrecognized resolution or unknown usage
- **WHEN** фактическая модель или обязательные данные для расчёта неизвестны
- **THEN** cost unavailable с причиной; backend не подменяет данные тарифом другой модели и не возвращает ложный ноль

### Requirement: New lab preserves existing services and secret handling
Day 05 SHALL добавляться без изменения контрактов и параметров Day 02–04. OpenAI credentials SHALL читаться только backend из `OPENAI_API_KEY`; Android, API responses, tests/fixtures и tracked документация SHALL NOT содержать секреты. Ошибки upstream SHALL возвращаться безопасно, без echo заголовков авторизации. Runtime SHALL выполнять живые вызовы, а результаты предварительных probes SHALL использоваться исключительно в документации, не как предзаданные ответы.

#### Scenario: Existing lesson is used after adding Day 05
- **WHEN** клиент вызывает любой существующий endpoint Day 02–04
- **THEN** получает прежний контракт и поведение

#### Scenario: Probe history is documented
- **WHEN** пользователь читает Day 05 README
- **THEN** видит вывод о выборе модели по use case и оговорку, что одиночные probes не являются статистически значимым benchmark
- **AND** runtime показывает результат текущего вызова, даже если он отличается от исторического probe
