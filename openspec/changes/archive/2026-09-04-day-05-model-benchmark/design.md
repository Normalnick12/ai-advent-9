## Context

Мотивация и scope — [proposal.md](proposal.md). Backend уже разделяет Day 02–04 на domain/models/service; `main.py` предоставляет отдельные endpoints с dependency injection. Android использует один `app` module, Compose Material 3, Retrofit/kotlinx.serialization и Activity-scoped ViewModel через `AppContainer`. `AppRoot` открывает дни из каталога и сохраняет saveable UI state. Эти границы подходят для новой лаборатории без нового framework.

Общий Android HTTP-клиент сейчас имеет read timeout 180 s/call timeout 190 s. В третьем probe отдельные вызовы заняли 57–93 s, а их последовательная сумма превысила 190 s. Day 05 получит собственный transport budget; настройки существующих уроков не меняются. Существующий `TokenUsage` требует non-null integers и не содержит cache breakdown; его переиспользование скрыло бы unknown usage за нулями, поэтому для Day 05 нужен отдельный DTO.

## Goals / Non-Goals

**Goals:** сохранить точный измеренный payload; отделить verifier, wire contract, вызовы OpenAI и Decimal pricing; явно разделить качество решения, завершение и доступность измерений; подключить Day 05 к существующей сессии и навигации.

**Non-Goals:** очередь jobs/polling/streaming, хранение истории между процессами, динамическое перечисление всех моделей OpenAI, автоматическая загрузка тарифов во время запроса, настройка reasoning/лимита, playground, live LLM в unit/UI tests, новый предварительный compatibility probe перед реализацией. Propose не реализует код или README.

## Decisions

### 1. Самодостаточный фиксированный benchmark

При apply добавить `backend/app/model_benchmark_domain.py` с canonical prompt, instructions, pure schema builder и verifier; отдельные `model_benchmark_models.py`, `model_benchmark_service.py`, `model_benchmark_pricing.py` сохраняют существующий стиль проекта. Canonical payload приведён ниже полностью и не зависит от временных вложений этой беседы. Общий request builder добавляет только выбранный `model`; не переиспользует recipe/temperature builder с другими instructions, schema и cache/reasoning-настройками.

Версия benchmark: `day05-v1`. Fingerprint — SHA-256 UTF-8 результата `json.dumps(common_payload, ensure_ascii=False, sort_keys=True)` с default separators. `common_payload` не содержит `model`, содержит `input` из блока Canonical prompt, `instructions` из отдельного блока и поля JSON-блока Request fields. В prompt используются LF, без завершающего перевода строки. Ожидаемый fingerprint: `01914c54838704723619457331e4d787299a23d010fdb23b1e66f725947d755c`. Для того же payload с лимитом 3000 fingerprint второго probe: `d5eb59535f47c2f94ffc89c94324b8882b3dc0e03a706273bd7de42b44051571`.

Schema ограничивает форму, а не правильность: нет enum ответов, min/max/const эталонов или подсказок. Локальная строгая Pydantic-валидация не приводит bool/string к integer. Альтернатива — editable prompt и свободный ответ — увеличивает scope и лишает experiment фиксированного quality contract.

### 2. Независимый verifier и область quality

Verifier строит эталоны из исходных данных: точная арифметика, permutations, все subsets, прямые изменяемые циклы и `product('ABC', repeat=10)`. Малый объём позволяет вычислить immutable reference один раз и переиспользовать в процессе; это cache детерминированного расчёта, не hardcoded probe result. Нельзя извлекать reference из ответа модели или использовать ответ модели для сокращения пространства перебора.

Расписание проверяется как полная перестановка имён с ограничениями; допускается только trim краёв имён, без fuzzy сопоставления. Набор фич сравнивается независимо от порядка, дубли и неизвестные ids отвергаются; cost/value пересчитываются, принимается любой допустимый optimum. В Task 4 отдельно сравниваются весь массив и checksum. В Task 5 проверяется integer count, проверка B использует только `s[i+1:i+3]`, а AB считается по соседним позициям. Known values из probes используются в unit tests для самопроверки verifier, не как runtime-источник эталона.

Только `response.status=completed` + отсутствие refusal + полное соответствие schema дают `quality: {correct_count: N, total_tasks: 5}` и пять correct/incorrect verdict. Иначе quality null, пять unverified verdict и сохранённый доступный raw output. Частичную оценку извлечённых из обрезанного JSON задач не вводим: пользователю нужна сравнимая оценка полного пятизадачного запроса. Альтернатива с 0/5 при любом сбое смешивает две разные причины результата и отвергнута.

### 3. Каталог и выбор трёх слотов

`GET /api/v1/model-benchmark/catalog` возвращает `benchmark_version`, `config` (prompt, instructions, fingerprint и общие read-only параметры), `models` (id/display_name/tier), `roles` (id/display_name/default_model_id/allowed_model_ids). Начальные разрешённые ids во всех ролях: Luna/Terra/Sol. Каталог статический backend-controlled и доступен без OpenAI-вызова/ключа. Он подтверждает совместимость настроек в приложении, но не гарантирует доступ конкретного API account; отказ доступа отображается runtime-ошибкой.

`POST /api/v1/model-benchmark/run` принимает `{"models":{"economical":"gpt-5.6-luna","balanced":"gpt-5.6-terra","flagship":"gpt-5.6-sol"}}`. Все три role fields required; extra fields запрещены. Валидация структуры/allowlist выполняется целиком до любых оплачиваемых вызовов: ошибки клиента дают 422. Неверная backend rate configuration даёт безопасную configuration error до старта; неполный registry не публикуется как готовый каталог. Клиент не передаёт prompt, тарифы, schema или настройки.

Повторы разрешены: два слота одной модели — два отдельных API calls с тем же payload. Не требуем уникальности, иначе при начальном каталоге из трёх моделей выбор может превратиться в неудобную перестановку взаимно занятых полей. UI объясняет повтор без запрета. Название роли — preset слота; выбранное display_name/id всегда видно, capability tier выбранной модели берётся из каталога. Нельзя выводить «флагманская» как качество фактически выбранной Luna.

### 4. Конкурентные вызовы с одинаковыми границами ожидания

После общей валидации запускать три независимые coroutine через `asyncio.gather(..., return_exceptions=True)`; возвращать результаты в фиксированном порядке ролей. У каждой попытки fresh одинаково настроенный `AsyncOpenAI` client/context, `max_retries=0`, `httpx.Timeout(240.0, connect=15.0)`, плюс wall-clock bound 240 s вокруг единственного `responses.create`. Это предотвращает бесконечный ожидательный сценарий при чтении сети по частям. Таймер monotonic охватывает сам вызов, не verifier/serialization и не ожидание других слотов; измерять фактическую latency и при исключении.

Слоты не отменяют друг друга. Отдельная неожиданная ошибка нормализуется локально; SDK/API exceptions не пробрасываются в gather как ошибка всего batch. API call count инкрементируется непосредственно перед единственным upstream call: 1 для ответа/refusal/API error/timeout; 0 если локальная ошибка не позволила начать вызов. До run API validation отказ возвращается без batch и без upstream calls. В ответе batch есть sum вызовов.

Конкурентность сокращает ожидание dashboard примерно до самого медленного вызова. Альтернатива — последовательность — проще сопоставима с probes по расписанию запуска, но суммирует до 720 s. Выбранная конкурентность фиксирована для всех runtime runs; исторические latency probes измерены последовательно и не являются нормативами runtime. Нет warm-up или дополнительных control calls.

Для нового Retrofit instance в AppContainer: connect 10 s, write 30 s, read 260 s, call 300 s, `retryOnConnectionFailure(false)`. Старый instance и его tests не меняются. `GET catalog` и `POST run` используют новый интерфейс/repository. Слой приложения не повторяет POST автоматически. При client transport failure completion неизвестен: прошлый batch сохраняется отдельно с подписью «Предыдущий результат», показывается ошибка нового запуска. Новое нажатие — новый batch, серверная idempotency/history не вводится.

### 5. Wire contract разделяет результат, статус и цену

Новые модели не расширяют старые API contracts. Batch response содержит `request_id`, `config` snapshot, `results` (ровно три роли), `api_call_count`. `X-Request-ID` и безопасные logs сохраняют проектный подход.

| Поле per-model result | Семантика |
| --- | --- |
| `role`, `requested_model`, `display_name` | Снимок выбранного слота этого batch |
| `resolved_model` | `response.model`, null при отсутствии ответа; не подставлять requested |
| `status`, `response_status` | Normalized completed/incomplete/refused/invalid_response/timeout/api_error/internal_error; исходный API status или null |
| `reason`, `error` | Безопасная причина, включая max_output_tokens, без credentials/сырого exception dump |
| `quality` | `{correct_count, total_tasks:5}` либо null |
| `tasks` | Пять `{task_id, verdict, actual_answer, reference_answer}`; reference только для incorrect, иначе null |
| `raw_output` | Фактический output_text при наличии; не hidden reasoning; отсутствие = null |
| `latency_ms`, `api_call_count` | Время единственной попытки и её счётчик |
| `usage` | Nullable `input_tokens`, `cached_input_tokens`, `cache_write_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens` |
| `cost` | `{status, amount_usd, currency:'USD', reason, pricing_model, rates, source_url, checked_at, service_tier}` |

У корректно распарсенного ответа actual_answer — typed task object, который Android рендерит read-only; при invalid/incomplete не предпринимается частичный JSON repair, доступный текст остаётся в raw_output. Потеря usage не мешает оценить завершённый валидный ответ; потеря pricing не мешает показывать usage/quality. Refusal не считается ошибочным решением. Числовой 0 показывается только если он получен или вычислен из известных данных. Новые nullable DTO исключают имеющийся helper `_zero_usage()`.

### 6. Централизованные официальные тарифы и Decimal

Единый backend registry хранит allowlist metadata, standard short-context rates и явный mapping разрешённых resolved ids к rate entries. Alias/snapshot нельзя угадывать по prefix; неизвестный resolved id даёт cost unavailable. Сейчас requested/resolved ids в probes совпали. Перед apply тарифы нужно перепроверить по официальным источникам и записать `checked_at`; runtime сеть для pricing не использует. Добавлять модель в allowlist можно только вместе с подтверждённой совместимостью fixed payload и полным тарифом.

Тарифы за 1M tokens, проверены 2026-09-04: [официальная таблица OpenAI](https://developers.openai.com/api/docs/pricing), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol).

| Model | Input Ri | Cached Rc | Cache write Rw | Output Ro |
| --- | ---: | ---: | ---: | ---: |
| gpt-5.6-luna | $0.20 | $0.02 | $0.25 | $1.20 |
| gpt-5.6-terra | $2.00 | $0.20 | $2.50 | $12.00 |
| gpt-5.6-sol | $4.00 | $0.40 | $5.00 | $20.00 |

Использовать Decimal, rates как decimal strings, результат также decimal string без float-roundtrip. Формула: `((I-C-W)*Ri + C*Rc + W*Rw + O*Ro)/1_000_000`. I — input total, C — cached reads, W — cache writes, O — output включая reasoning. Проверить неотрицательность и `C+W <= I`. Cost вычисляется и для incomplete, если известны необходимые данные. Missing I/C/W/O, неизвестная тарифная модель/tier или противоречивые counters => amount null с причиной. Отсутствие reasoning или total counter само по себе не мешает цене при известных I/C/W/O. Не превращать отсутствующий W в ноль без официально подтверждённого контракта провайдера; в текущем SDK probe W явно равен 0.

Fixed short-context benchmark не требует long-context калькулятора: registry и calculator явно покрывают только этот режим; при неожиданных >272K input tokens цена unavailable, пока не добавлен соответствующий тариф. Аналогично неожиданный service tier нельзя молча считать standard. Сравнение выполняется direct API без регионального endpoint и дополнительных tools. Фраза UI — «Стоимость по тарифам, USD»: это расчёт конкретного запроса по usage, не выписка с billing account.

Альтернатива — цены в Android либо фиксированная цена запуска — устаревает независимо от backend и не учитывает cache/output. Округлять только для отображения (до 8 десятичных знаков, сохраняя малую ненулевую стоимость); raw decimal и формула доступны в деталях.

### 7. Android state и экран

Добавить ModelBenchmarkLabViewModel с constructor-injected repository и Activity scope как у существующих лабораторий. State содержит catalog loading/error/data, selections, running snapshot, last batch и run error. Каталог загружается один раз при первом открытии Day 05, повторяется только явным действием после ошибки; создание всех ViewModel в MainActivity само по себе не должно запрашивать каталог и тем более запускать benchmark. Defaults берутся из каталога, не из отдельного Android allowlist. Backend остаётся окончательным валидатором stale selections.

Добавить destination и карточку 05 в AppRoot/LearningDaysHome; верхняя область «День 05», «Лаборатория моделей», «Назад к дням» использует текущий подход. SaveableStateHolder и ключи по request_id/role сохраняют раскрытие и scroll только для неизменившихся результатов. При новом batch detail state сбрасывается; выбранные модели и ViewModel данные переживают навигацию/rotation в пределах процесса. Process-death persistence не обещается.

Основной layout: три role selectors; кнопка; read-only параметры; три вертикальные result cards. У карточки компактная сетка из четырёх метрик (качество/время/токены/стоимость), status и раскрываемые детали; при большом шрифте метрики переносятся в одну колонку. `Токены` в summary — total; details показывают breakdown и явно называют reasoning частью output. Нет широкой desktop-таблицы или графиков. Ответы selectable, ids переносятся, технические значения не переводятся. API keys отсутствуют во всех DTO/UI.

При partial failure карточки остаются равноправными, cost/quality не сортируются автоматически. Для quality null основная строка «Нет проверяемого результата», внутри задач «Не проверено». Полный неправильный ответ получает N/5, в том числе 0/5. Исторические результаты из probes не показываются вместо loading и не задают ожидаемую оценку Luna.

### 8. Проверки и документация

Backend tests покрывают verifier/shape, equality трёх upstream kwargs после удаления model, canonical fingerprint, запрет retries/fallback, mixed completed/incomplete/refusal/error, nullable usage, реальные и неизвестные resolved ids, cache-aware Decimal pricing, API validation до calls и stable result ordering при разном времени завершения. Использовать существующий pytest без настоящих ключей/LLM; schema wrong-type/bool, duplicate features, неверный checksum при верном массиве, конец строки B — отдельные содержательные кейсы.

Android JVM tests проверяют DTO null/decimal, один POST и loading lock, immutable snapshots, каталог/selection и transport error. Compose tests на fake repository проверяют четыре карточки каталога, toolbar/system back, session state/rotation, отсутствие автозапуска, dashboard/детали и отличие incomplete от 0/5. Проверить узкий экран и крупный шрифт. Полный UI-прогон оправдан изменением root navigation, но только после завершения связанных правок, без повторов на каждом шаге.

Во время apply создать краткий Day README: что делает лаборатория, зависимости и ссылки на setup backend/Android, `OPENAI_API_KEY` только на backend, команды запуска через `scripts/dev.ps1`, основной вывод «самая сильная модель не обязательно является лучшим продуктовым выбором; качество, latency и стоимость нужно сравнивать для конкретного use case». Подробный wire contract и pricing maintenance остаются в OpenSpec/component README. Live E2E — один отдельный явный запуск через готовый UI после offline checks, не новый предварительный gate и не тест ожидаемых N/5. Не повторять paid run ради воспроизведения исторической ошибки.

### 9. Предварительные probes — наблюдения, не runtime fixtures

Все проведены 2026-09-04, по одному запросу на модель, SDK 2.54.0, без retries. Первый benchmark содержал более простые Task 4 (граф) и Task 5 (двоичные строки): все модели 5/5. Второй — текущие algorithm tracing/counting при 3000 tokens: Luna incomplete/max_output_tokens без проверяемого результата, Terra/Sol 5/5. Третий — тот же payload с единственным изменением лимита на 6000: все completed, Luna Task 5 count 21 вместо verifier 24, остальные ответы правильны.

| Третий probe | Quality | Latency s | Input / Output / Reasoning / Total | Cost USD |
| --- | --- | ---: | --- | ---: |
| Luna | 4/5 | 86.044 | 953 / 5800 / 5691 / 6753 | 0.0071506 |
| Terra | 5/5 | 57.488 | 953 / 3215 / 3106 / 4168 | 0.040486 |
| Sol | 5/5 | 92.996 | 953 / 5511 / 5402 / 6464 | 0.114032 |

Во всех трёх вызовах третьего probe cached input/cache write=0, requested=resolved, service_tier=default. Стоимость посчитана по фактическим counters, не лимиту. Это одиночные наблюдения, не статистически значимое доказательство; runtime обязан честно показывать иные ответы/latency/usage. В README достаточно кратко перечислить эти три этапа без implementation dump.

## Risks / Trade-offs

- [Нестабильное качество одного запуска] → не присваивать постоянного победителя и не тестировать живой ответ на обязательные 4/5 или 5/5.
- [6000 всё ещё конечный лимит] → incomplete остаётся отдельным unverified результатом с фактической стоимостью, без автоматического увеличения budget.
- [Конкурентные запросы влияют на rate limits и latency] → одинаковая стратегия запуска для всех, per-call monotonic таймер, отсутствие retries; не сравнивать runtime latency напрямую с последовательными probes как контролируемое изменение модели.
- [Тарифы/aliases могут измениться] → versioned backend registry с проверенной датой и ссылкой, явный resolved mapping, unavailable при неизвестных данных.
- [Backend завершил работу после transport timeout Android] → клиент сообщает неопределённость результата и не повторяет POST автоматически; отдельный timeout budget снижает вероятность преждевременного разрыва.
- [Новая лаборатория случайно наследует старые defaults] → отдельные модели/client/builder и equality/fingerprint regression tests, сохранение старых endpoint tests.

## Migration Plan

После отдельного запроса на apply реализовать additive backend domain/contracts/catalog/run, затем Android data/state/UI/navigation и документацию. Сначала offline tests; затем перезапустить backend в управляемой терминальной сессии, проверить `status` и доступ из эмулятора и выполнить один E2E run. Новых секретов, env-переменных, database migrations или framework не требуется; сохраняется текущий `OPENAI_API_KEY` и debug URL.

Rollback до публикации — убрать интеграцию Day 05 и новые модули/endpoint, сохранив существующие уроки. Старый Android продолжает работать с backend с добавленными endpoints; новый Day 05 на старом backend показывает catalog error без нарушения навигации. Commit/push выполняются только по отдельному запросу пользователя.

## Canonical prompt

```text
Реши 5 независимых задач. Верни только результат каждой задачи в указанном
Structured Output. Не пропускай задачи.

Задача 1 — арифметика.
Сервис обработал 240 запросов. 35% запросов были обслужены из кэша и не
обращались к базе данных. Каждый оставшийся запрос сделал ровно 3 запроса
к БД. Сколько всего запросов к БД было выполнено?

Задача 2 — логическая дедукция.
Есть четыре разработчика: Анна, Борис, Вера и Глеб, и четыре дня:
понедельник, вторник, среда, четверг. Каждый дежурит ровно один день.
Условия:
- Анна дежурит раньше Бориса.
- Вера не дежурит ни в понедельник, ни в четверг.
- Глеб дежурит ровно на следующий день после Анны.
Определи полное расписание.

Задача 3 — оптимизация.
Лимит — 15 story points.

Фичи:
A: cost 4, value 8
B: cost 6, value 11
C: cost 5, value 10
D: cost 3, value 6
E: cost 7, value 13
F: cost 2, value 4
G: cost 4, value 7
H: cost 5, value 8

Ограничения:
- B и E нельзя брать вместе;
- C можно взять только вместе с F;
- A и D нельзя брать вместе;
- G и H нельзя брать вместе;
- total cost <= 15.

Выбери допустимый набор с максимальной total value.

Задача 4 — algorithm tracing.
Индексация массива с нуля.

Начальное состояние:
a = [7, 2, 5, 1, 8, 3, 6, 4]

Сначала выполнить для i от 1 до 7 включительно:

if (a[i - 1] + i) mod 3 == 0:
    a[i] = a[i] + a[i - 1]
else:
    a[i] = a[i - 1] - a[i]

Каждая следующая итерация использует уже изменённый массив.

После этого выполнить для i от 6 до 0 включительно в обратном порядке:

if i mod 2 == 0:
    a[i] = a[i] + a[i + 1]
else:
    a[i] = a[i] - a[i + 1]

Здесь также используются текущие уже изменённые значения.

После обоих циклов вычислить:
checksum = sum((i + 1) * a[i]) для i от 0 до 7.

Верни final_array и checksum.

Задача 5 — combinatorial counting.
Посчитай количество строк длины 10 над алфавитом {A, B, C}, которые:
1. содержат ровно 4 символа A;
2. не содержат одинаковых соседних символов;
3. первый символ не C;
4. для каждого B среди одного или двух следующих существующих символов должен встретиться C;
5. соседняя подстрока AB встречается ровно 2 раза.

Для B около конца строки учитываются только реально существующие следующие позиции.
Если среди них нет C, строка не подходит.

Occurrence AB — это позиция i, где s[i]=A и s[i+1]=B.
Верни только count.
```

## Canonical instructions

```text
Верни только JSON, соответствующий заданной схеме. Реши все пять задач; не добавляй пояснения вне JSON.
```

## Request fields

Следующие поля дополняются только `input`, `instructions` из блоков выше и `model` выбранного слота. Никаких других per-model полей нет.

```json
{
  "reasoning": {"effort": "medium"},
  "max_output_tokens": 6000,
  "store": false,
  "service_tier": "default",
  "text": {
    "format": {
      "type": "json_schema",
      "name": "five_task_benchmark",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "task1": {
            "type": "object",
            "properties": {"database_queries": {"type": "integer"}},
            "required": ["database_queries"],
            "additionalProperties": false
          },
          "task2": {
            "type": "object",
            "properties": {"monday": {"type": "string"}, "tuesday": {"type": "string"}, "wednesday": {"type": "string"}, "thursday": {"type": "string"}},
            "required": ["monday", "tuesday", "wednesday", "thursday"],
            "additionalProperties": false
          },
          "task3": {
            "type": "object",
            "properties": {"selected_features": {"type": "array", "items": {"type": "string"}}, "total_cost": {"type": "integer"}, "total_value": {"type": "integer"}},
            "required": ["selected_features", "total_cost", "total_value"],
            "additionalProperties": false
          },
          "task4": {
            "type": "object",
            "properties": {"final_array": {"type": "array", "items": {"type": "integer"}}, "checksum": {"type": "integer"}},
            "required": ["final_array", "checksum"],
            "additionalProperties": false
          },
          "task5": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
            "additionalProperties": false
          }
        },
        "required": ["task1", "task2", "task3", "task4", "task5"],
        "additionalProperties": false
      }
    }
  }
}
```
