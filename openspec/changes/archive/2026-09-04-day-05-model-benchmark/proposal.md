## Why

Day 05 должен показать, как выбирать модель для конкретного продукта по качеству, времени ответа и стоимости одного и того же запроса. Финальный предварительный probe при лимите 6000 tokens дал Luna 4/5 и Terra/Sol 5/5 без truncation; это основание для учебного эксперимента, а не статистически установленный рейтинг моделей.

## What Changes

- Добавить в существующий backend Model Benchmark Lab: один Responses API call на каждую из трёх выбранных моделей, общий неизменяемый benchmark из пяти задач, strict Structured Output, medium reasoning и лимит 6000 output tokens. Между вызовами меняется только model id; retries и fallback отсутствуют.
- Вычислять эталоны и проверять решения обычным Python-кодом; возвращать verdict и фактический ответ каждой задачи, эталон для ошибки и quality N/5 только при проверяемом полном результате. Incomplete, refusal и ошибки не превращать в 0/5.
- Возвращать latency, nullable фактический usage, requested/resolved model, status, API call count и оценку стоимости фактического запроса по централизованным официальным тарифам backend.
- Добавить backend-controlled каталог разрешённых совместимых моделей и defaults Luna/Terra/Sol для ролей «Экономичная», «Сбалансированная», «Флагманская»; выбирать model id только из каталога.
- Добавить русскоязычный экран «Лаборатория моделей»: три компактные карточки результатов, раскрываемые детали задач и метрик, общий read-only блок параметров и кнопка «Запустить сравнение».
- Включить Day 05 в существующий каталог Android с сохранением состояния текущей сессии. Во время apply создать краткий `day-05-model-benchmark/README.md` с запуском, конфигурацией и учебным выводом; зафиксировать историю probes отдельно от runtime-результатов.
- Оставить playground, редактирование benchmark/параметров, графики, историю запусков, автоматическое ранжирование и статистические серии вне Day 05.

## Capabilities

### New Capabilities

- `model-benchmark-experiment`: фиксированный benchmark, каталог моделей, честное выполнение трёх вызовов, независимая проверка, ошибки, usage и стоимость.
- `model-benchmark-android`: выбор моделей, запуск, mobile dashboard и детали результатов на русском языке.

### Modified Capabilities

- `learning-days-navigation`: добавить Day 05 в каталог и переходы без автозапуска эксперимента.
- `learning-days-presentation`: добавить описание Day 05 и распространить русские пользовательские подписи на новый урок.

## Impact

- Новые backend domain/models/service/pricing-модули и `GET /api/v1/model-benchmark/catalog`, `POST /api/v1/model-benchmark/run`; контракты Day 02–04 сохраняются.
- Новый экран/ViewModel/Repository/DTO внутри единственного Android `app` module; wiring в AppContainer/MainActivity/AppRoot/LearningDaysHome, отдельный HTTP-клиент с подходящим timeout.
- Переиспользуются FastAPI, Pydantic, официальный OpenAI Python SDK, Kotlin/Compose Material 3, Retrofit и coroutines; новые framework/dependencies не требуются.
- Нужны deterministic backend tests, mocked API/service tests, Android JVM/UI tests и проверка навигации. Ключ остаётся только в backend `OPENAI_API_KEY`; тарифы и вычисление quality не переносятся в Android.
- На propose этапе создаются только planning-артефакты; production-код, Day README, commit и push не входят в этот шаг.
