## Context

См. `proposal.md` для мотивации и delta specs для внешнего поведения. Сейчас репозиторий содержит один FastAPI backend с `/api/v1/generate` и один Android `app` module на Compose/Material 3. Android использует Retrofit, kotlinx.serialization, coroutines и ручной `AppContainer`; OpenAI вызывается только backend через `AsyncOpenAI` Responses API.

Изменение пересекает backend, Android и документацию, но не требует нового проекта, app module, DI framework или сторонней solver-библиотеки. Официальная документация подтверждает, что alias `gpt-5.6` направляется на GPT-5.6 Sol, Responses API поддерживает `reasoning.effort`, strict Structured Outputs, `max_output_tokens` и usage с token breakdown: [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model), [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).

## Goals / Non-Goals

**Goals:**

- Изолировать эксперимент Day 03 от существующего Day 02 API и UI, переиспользуя общую инфраструктуру.
- Сделать четыре pipelines сравнимыми на уровне модели, effort, задачи, финальной схемы, token limit, transport timeout и cache policy.
- Дать verifier право окончательного решения о корректности и объяснимые причины отклонения.
- Уложить полный batch в существующий Android timeout budget и сохранить частичные результаты.
- Сделать новый экран компактным, русскоязычным и предсказуемым для записи видео.

**Non-Goals:**

- Настоящие subagents, Agents SDK, tool calls, multi-agent beta или несколько экспертных сессий.
- Пользовательское редактирование benchmark, модели, effort, prompts или token limit.
- Статистически значимый benchmark, хранение истории запусков, стоимость в валюте или серверная база данных.
- Перенос, переписывание или удаление функциональности Day 01/02.

## Decisions

### 1. Additive backend slice with one batch endpoint

Добавить `POST /api/v1/reasoning-lab/run` с пустым строгим request object и единым batch response. Новые transport-модели живут рядом с текущими Pydantic-моделями, а orchestration, prompts и verifier — в отдельных Day 03 backend-модулях. Существующий `/api/v1/generate` и `OpenAIResponseService` не меняют контракт.

Ответ верхнего уровня содержит `request_id`, фиксированную experiment configuration, reference optimum и массив результатов в стабильном порядке DIRECT, STEP_BY_STEP, META_PROMPT, EXPERT_PANEL. Каждый результат содержит:

- `strategy`, русское `display_name`, `correct`;
- `latency_ms`, `api_call_count`;
- `usage.input_tokens`, `usage.output_tokens`, `usage.reasoning_tokens`, `usage.total_tokens`;
- `solution` либо `error`;
- verification details с пересчитанными cost/value и списком нарушений;
- nullable `generated_prompt`, заполненный только у META_PROMPT.

Альтернатива — четыре отдельных Android-запроса. Она отклонена: клиенту пришлось бы координировать partial failures и агрегацию, а правила fairness и META_PROMPT оказались бы размазаны между слоями.

### 2. Canonical benchmark is one immutable domain definition

Фичи, лимит и ограничения задаются один раз в backend domain-модели. Из неё строятся канонический русский task text, полный перебор и verifier; prompt literals не дублируют числа вручную. Enumeration проходит маски `0..255`, фильтрует допустимые subsets и выбирает максимальный value с детерминированным tie handling.

Ожидаемый regression oracle — единственное решение `{A, C, F, G}`, cost 15, value 29. Verifier нормализует регистр/порядок, но отвергает дубликаты и неизвестные ids, независимо пересчитывает итоги и не доверяет числам модели. `correct=true` требует одновременно валидного набора, оптимальной ценности и совпадающих reported totals.

Альтернатива — сравнивать с захардкоженным списком. Она отклонена: enumeration лучше демонстрирует требуемую детерминированную проверку и защищает тесты при будущей правке данных задачи.

### 3. One shared OpenAI request envelope, strategy-only prompt variation

Каждый OpenAI-вызов Reasoning Lab использует:

- `model="gpt-5.6"`;
- `reasoning={"effort": "medium"}` в standard mode;
- `max_output_tokens=1200`;
- `store=false`;
- `prompt_cache_options={"mode": "explicit"}` без breakpoints, чтобы отключить implicit cache и не давать более поздней стратегии преимущество порядка;
- одинаковый timeout 75 секунд и `max_retries=0`.

Отключение SDK retries делает `api_call_count` фактическим числом HTTP-вызовов и ограничивает worst-case META_PROMPT двумя timeout-окнами (~150 секунд), что помещается в существующий Android call timeout 190 секунд. Day 02 сохраняет текущий retry budget.

Финальные вызовы используют одну strict JSON Schema `optimization_solution` с четырьмя обязательными полями и `additionalProperties=false`. Для preparatory META_PROMPT вызова нужна отдельная strict схема `{generated_prompt: string}`, поскольку этот вызов намеренно не является решением; требование общего solution contract относится ко всем четырём финальным solver-вызовам.

`DIRECT` не получает strategy instruction. `STEP_BY_STEP` получает короткую инструкцию выполнить декомпозицию и отразить проверку в `explanation`. `EXPERT_PANEL` одним developer instruction последовательно моделирует аналитика, инженера и критика, после чего возвращает один solution object. Для `META_PROMPT` первый вызов получает canonical task и генерирует instruction, которая обязана сохранять исходные данные; второй вызов получает неизменный canonical task как input и generated prompt как strategy instruction. `previous_response_id` не используется: переносится только видимый generated prompt, поэтому experiment остаётся аудируемым.

Альтернатива — отдельные модели/efforts или pro mode для сложных стратегий. Она отклонена, поскольку тогда менялась бы не только prompting strategy.

### 4. Pipelines run concurrently, calls inside META_PROMPT remain sequential

Backend запускает четыре strategy pipelines через обычные coroutines и `gather(return_exceptions=True)`. Это не agent delegation: каждый pipeline — ограниченный Responses API request, а EXPERT_PANEL остаётся одним request. META_PROMPT выполняет свои два зависимых вызова последовательно.

`latency_ms` измеряется monotonic clock от начала pipeline до его terminal result. DIRECT, STEP_BY_STEP и EXPERT_PANEL имеют call count 1; META_PROMPT — 2 при полном успехе и 1, если preparatory call завершился ошибкой. Usage суммируется по доступным ответам; reasoning tokens берутся из `output_tokens_details`. Ошибка одной стратегии превращается в её typed result и не отменяет batch.

Альтернатива — полностью последовательный batch. Она проще для rate limits, но пять timeout-окон могут превысить Android budget и делают видеодемонстрацию заметно медленнее. Частичные rate-limit ошибки при параллельном запуске остаются видимыми и повторяемыми через основную кнопку.

### 5. Android adds a second MVVM screen without a navigation dependency

`AppContainer` строит один Retrofit instance и создаёт существующий Day 02 API/repository и новый Reasoning Lab repository. Новый screen-level ViewModel получает repository через текущую constructor factory и хранит явные idle/loading/content/error states; во время loading повторный запуск блокируется.

Корневой Compose UI использует Material 3 `NavigationBar` с двумя русскими destinations и переключает существующий `ResponseControlScreen` и новый `ReasoningLabScreen`. Новая navigation library не нужна. Экран Reasoning Lab содержит краткую карточку фиксированной задачи, одну full-width кнопку «Запустить все стратегии», progress indicator и вертикальный список карточек в стабильном порядке.

Карточка показывает цветовой status badge «Правильно»/«Неправильно», решение и метрики с русскими labels. Ошибка живёт в карточке стратегии. META_PROMPT использует `OutlinedButton`/expand state для «Показать сгенерированный промпт» и `SelectionContainer` для текста. Технические enum не выводятся напрямую.

Альтернатива — заменить Day 02 экран или создать второй Android module. Обе отклонены как нарушение условия расширять существующее приложение.

### 6. Tests are layered around deterministic seams

Backend tests отдельно покрывают enumeration, каждое constraint, mismatch reported totals, prompt/request parameters, META_PROMPT aggregation, partial failure и endpoint serialization через mock `AsyncOpenAI`. Live API не нужен для automated tests.

Android tests используют fake repository для ViewModel (один batch на tap, loading lock, content/error states), проверяют DTO serialization и русское отображение strategy ids. Compose UI smoke test либо manual emulator checklist подтверждает навигацию, scroll и expand prompt; новых test dependencies не требуется.

`day-03-reasoning-strategies/README.md` документирует цель, fixed configuration, expected optimum, архитектуру, `OPENAI_API_KEY`, запуск backend/app, API пример и проверки. Root README получает ссылку на Day 03, а backend/Android README — только необходимые additive сведения.

## Risks / Trade-offs

- [Один запуск LLM не является научным benchmark] → Позиционировать экран как учебное сравнение и позволять повторный запуск без хранения/усреднения.
- [Параллельные запросы могут попасть в rate limit] → Изолировать ошибку по стратегии, не делать скрытых retries и оставить повторный batch явным действием пользователя.
- [`max_output_tokens` включает reasoning tokens и может дать incomplete] → Использовать 1200 для простой задачи, трактовать incomplete как typed incorrect result и показывать причину.
- [META_PROMPT generated instruction может исказить исходные данные] → Передавать canonical task отдельно неизменным, требовать не менять факты и всё равно проверять итог независимым verifier.
- [Latency зависит от сети и одновременной нагрузки] → Измерять одинаково monotonic clock, отключить implicit caching и показывать метрику как наблюдение конкретного запуска.
- [Refactor AppContainer/navigation может случайно задеть Day 02] → Сохранить старый repository contract, добавить regression tests и проверить оба экрана до сдачи.
- [Сырые upstream errors могут раскрыть лишние детали] → Возвращать allowlisted безопасные коды/русские сообщения, логировать только request id, strategy, duration и status без prompts/секретов.

## Migration Plan

1. Добавить solver/verifier, модели и tests без подключения endpoint.
2. Добавить OpenAI strategy service и batch endpoint, затем прогнать backend tests и один ручной запрос с настроенным `OPENAI_API_KEY`.
3. Добавить Android DTO/repository/ViewModel/screen и корневую навигацию, сохранив Day 02.
4. Обновить README и выполнить backend tests, Android unit tests/assemble, emulator smoke test и проверку отсутствия секретов.

Изменение полностью additive и не требует data migration. Для rollback удалить новый endpoint/modules, Android destination/screen и Day 03 README; существующие Day 02 API и экран останутся работоспособными.
