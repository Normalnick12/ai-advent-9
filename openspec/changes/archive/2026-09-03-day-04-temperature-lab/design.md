## Context

См. `proposal.md` для мотивации и delta specs для внешнего поведения. Репозиторий уже содержит один FastAPI backend с `/api/v1/generate` и `/api/v1/reasoning-lab/run`, один Android `app` module на Compose/Material 3, Retrofit/kotlinx.serialization, coroutines и ручной `AppContainer`. OpenAI вызывается только backend через официальный Python SDK и Responses API; Day 03 уже имеет изолированные per-result errors, usage и concurrent batch orchestration.

Day 04 пересекает backend, Android и документацию, а выбранная комбинация модели, sampling, reasoning и strict Structured Output требует живой проверки до реализации. Официальная документация подтверждает, что alias `gpt-5.6` направляется на GPT-5.6 Sol и поддерживает `reasoning.effort=none`; Responses API принимает `temperature` от 0 до 2, рекомендует менять temperature или `top_p`, но не оба, и поддерживает text/JSON Schema output formats. Она не гарантирует совместимость всей комбинации параметров для конкретного account/runtime, поэтому probe остаётся отдельным gate: [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model), [Responses API create](https://developers.openai.com/api/reference/resources/responses/methods/create).

## Goals / Non-Goals

**Goals:**

- Обеспечить машинно проверяемый инвариант: внутри одного запуска request envelopes отличаются только `temperature`.
- Сохранить raw prompt без нормализации и определять benchmark/free mode авторитетно на backend.
- Разделить structural guarantee strict JSON Schema и пять формальных benchmark-проверок.
- Сохранить partial results и отдельно измерять каждый вызов при конкурентном batch.
- Дать Android компактное session-only состояние для текущей истории и накопительной benchmark-уникальности.

**Non-Goals:**

- Статистически значимый научный вывод по трём единичным samples или обещание полной детерминированности при `temperature=0`.
- Автоматическая численная оценка креативности, семантической уместности, accuracy или LLM-as-a-judge.
- Редактирование model, temperature, reasoning, token limit, output contract или controls Day 02/03 на экране Day 04.
- Серверная история, Room, DataStore, файлы, синхронизация между process sessions или экспорт результатов.
- Изменение существующих Day 02/03 endpoint contracts и экранов.

## Decisions

### 1. A live compatibility probe gates every implementation step

Первой apply-задачей выполнить через установленный официальный SDK три живых Responses API вызова с точным canonical prompt, planned strict schema и полной общей конфигурацией: `model="gpt-5.6"`, `reasoning={"effort":"none","mode":"standard"}`, `max_output_tokens=600`, `store=false`, explicit cache policy, отсутствующий `top_p` и temperature 0/0.7/1.2. Probe использует только `OPENAI_API_KEY` окружения, не печатает и не сохраняет credential и фиксирует sanitized status/model/parameter error для каждого значения.

Gate считается пройденным, только если API принимает все три комбинации и возвращает разбираемый strict object. Если хотя бы одна temperature или совместное использование reasoning/Structured Output отклонены, apply останавливается до решения пользователя и обновления planning artifacts. Запрещены молчаливые fallback на другую model, reasoning effort/mode, temperature, text response, `top_p` или schema. Отсутствующий API key также блокирует дальнейшую реализацию, потому что mocked test не отвечает на вопрос совместимости.

Альтернатива — сначала реализовать сервис и оставить live проверку на финальный smoke test. Она отклонена: реальная несовместимость тогда обнаружится после того, как архитектура и UI уже будут построены вокруг недействительной предпосылки.

### 2. Add one isolated batch endpoint and keep mode selection on backend

Добавить `POST /api/v1/temperature-lab/run` с request `{prompt: string}`. Клиент не передаёт mode, temperatures или controls. Backend хранит canonical benchmark как одну константу и сравнивает request prompt с ней оператором точного равенства; `trim`, line-ending repair и иная нормализация перед сравнением или OpenAI-вызовом не выполняются. Response содержит `request_id`, определённый `mode`, read-only config и три typed results в порядке 0, 0.7, 1.2.

Новые Pydantic-модели и orchestration располагаются в отдельном Temperature Lab slice, но переиспользуют общий `ErrorInfo` и совместимый token-usage shape Day 03. Существующие services и endpoints не меняют публичные contracts.

Альтернатива — определять mode в Android или принимать Boolean `benchmark`. Она отклонена: изменённый клиент мог бы запросить validator для произвольного текста, а backend потерял бы единый источник истины output contract.

### 3. Build requests from one immutable envelope plus temperature

Service сначала строит один base envelope для batch:

- `model="gpt-5.6"`;
- `input` равен точной request string;
- `reasoning={"effort":"none","mode":"standard"}`;
- `max_output_tokens=600`;
- `store=false`;
- `prompt_cache_options={"mode":"explicit"}` без breakpoints, чтобы отключить implicit cache;
- без `top_p`, `instructions`, `previous_response_id` и tools;
- один output contract, выбранный по backend mode.

Для каждой temperature создаётся копия base envelope с добавленным единственным полем `temperature`. Отдельный invariant test удаляет это поле из трёх captured SDK kwargs и проверяет полное равенство словарей. SDK client использует одинаковый timeout и `max_retries=0`: скрытый retry искажает latency и фактическое число обращений.

В benchmark mode `text.format` — strict JSON Schema с корневым обязательным `variants`, item fields `name`/`slogan`, `additionalProperties=false` на обоих уровнях и без `minItems`, `maxItems`, `uniqueItems` или семантических ограничений. В free mode общий contract — явный обычный text format. Различие output contract между разными modes допустимо; внутри одного batch contract идентичен.

Альтернатива — добавить developer instruction, который объясняет формат. Она отклонена: canonical prompt должен передаваться неизменно, а schema уже задаёт structural contract.

### 4. Validate semantics after parsing and expose normalized names

После успешного benchmark parsing отдельная pure domain-функция вычисляет пять Boolean checks и `requirements_met=sum(passed)`. Word count для `name` и `slogan` использует непустые whitespace-separated tokens. Exact-name normalization выполняется как `" ".join(value.split()).casefold()`. Для запрещённых отдельных слов строка разбивается на максимальные Unicode letter/digit tokens (например, Python regex `[^\W_]+`), затем tokens сравниваются через `casefold`; поэтому `AI-Pro` запрещён, а `AIMentor` — нет.

Model-facing schema остаётся ровно `{variants:[{name,slogan}]}`. Backend response для каждого parsed variant дополнительно содержит вычисленный `normalized_name` либо эквивалентный aligned normalized-name список. Android использует это серверное значение для cumulative uniqueness, чтобы Python `casefold` и Kotlin lowercase rules не разошлись. Raw `name` и `slogan` сохраняются для отображения.

Validation details имеют стабильные ids для пяти checks, Boolean `passed` и русское объяснение; UI строит только формулировку «Соблюдение требований: N/5». Для incomplete, upstream error или parse failure validation равна `null`, а не `0/5`. Никакая функция не оценивает содержание продукта, креативность или качество слогана сверх пяти формальных правил.

Альтернатива — encode `minItems=maxItems=5` и uniqueness в JSON Schema. Она отклонена: это скрыло бы одну из измеряемых ошибок и смешало structural enforcement с benchmark outcome.

### 5. Run three calls concurrently and isolate metrics/errors

Backend запускает три независимые coroutine через `asyncio.gather(return_exceptions=True)`, сохраняя стабильный result order независимо от completion order. `latency_ms` измеряется monotonic clock внутри каждой coroutine от непосредственного начала SDK call до её terminal normalization; batch wall time не используется как latency конкретной temperature.

Per-temperature result содержит `temperature`, normalized status, `latency_ms`, usage input/output/reasoning/total, parsed `variants` или text `content`, nullable validation и safe `error`. Usage извлекается даже для доступных incomplete responses; если upstream не вернул usage, используются нули с сохранением error/status. Bad request logs могут содержать redacted parameter/code для диагностики probe/runtime incompatibility, но response получает allowlisted код и русское безопасное сообщение без prompt и credential.

Конкурентность улучшает UX, но UI и README явно трактуют latency как наблюдение конкретного запуска, зависящее от сети и нагрузки. Никакая temperature не ранжируется автоматически.

Альтернатива — три Android HTTP requests. Она отклонена: fairness checks, mode selection, partial failures и config drift должны контролироваться в одном backend batch.

### 6. Extend the existing Android MVVM slice and keep two independent session stores

Добавить Temperature Lab DTO/API/repository к общему Retrofit instance в `AppContainer`, screen-level ViewModel через существующую constructor factory и третью destination в простом root `NavigationBar`. Новая navigation или DI dependency не нужна.

ViewModel хранит:

- редактируемый `prompt`, изначально точную shared Kotlin copy canonical benchmark, и loading/error/latest state;
- active history bucket `{prompt, up to 3 batches}` с newest-first eviction;
- отдельные session-long benchmark accumulators по temperature: `Set<normalized_name>` и `totalGenerated`.

История видима только при точном равенстве текущего editor text и `history.prompt`. Во время запуска нового prompt старая история скрыта; после принятого batch с новым prompt active bucket заменяется. Возврат текста назад до нового принятого batch снова может показать прежний bucket, но после запуска другого prompt прежняя история не сохраняется. Transport failure без batch не записывается как run и не уничтожает прежний bucket.

Benchmark accumulators независимы от трёхэлементной истории и переживают переключение в free mode в пределах жизни ViewModel. Они обновляются только `normalized_name` из успешно parsed benchmark results: каждый variant увеличивает denominator, а Set определяет numerator отдельно по temperature. Free mode скрывает секцию и не изменяет counters; process death очищает и историю, и counters.

Screen использует многострочный `OutlinedTextField`, основные действия «Запустить сравнение»/«Вернуть benchmark», expandable read-only config, три result cards, expandable selectable response content, active history и benchmark-only uniqueness section. Status и error codes отображаются русскими labels, а technical enum/string не выводятся напрямую.

Альтернатива — сохранять map истории для каждого введённого prompt. Она отклонена: scope может неограниченно расти и выходит за требование максимум трёх прогонов текущего prompt.

### 7. Verify deterministic seams and preserve existing labs

Backend tests покрывают exact canonical comparison, schema без item-count constraints, пять validator rules и Unicode/whitespace edge cases, request-envelope equality кроме temperature, отсутствующий `top_p`, benchmark/free parsing, concurrency, stable order, usage/latency, incompatible bad request, partial failure и endpoint serialization. Все automated SDK tests используют mocks; live probe остаётся отдельным обязательным apply gate.

Android tests покрывают request DTO с неизменным prompt, one-request loading lock, русские status labels, three-card/expand behavior, active history hiding/reset/eviction, benchmark accumulator duplicate handling и отсутствие обновления в free mode. Полный backend suite, Android unit tests и debug assemble защищают Day 02/03 regressions; emulator smoke проверяет навигацию и реальный batch.

`day-04-temperature-lab/README.md` становится точкой входа и документирует цель, fixed/default параметры, canonical/free semantics, пять checks, оговорки о креативности и latency, environment setup, `OPENAI_API_KEY`, запуск, live probe outcome и команды проверок без реального secret.

## Risks / Trade-offs

- [Live API отклоняет temperature вместе с выбранным reasoning/Structured Output] → Остановить apply на первом gate, показать sanitized incompatibility и пересогласовать specs/design; не применять fallback молча.
- [Strict Structured Output сам влияет на разнообразие] → Использовать абсолютно одинаковую schema для трёх benchmark-вызовов и описать выводы только как сравнение внутри этого contract.
- [`temperature=0` не гарантирует битовую повторяемость] → Не называть режим детерминированным; показывать накопительные наблюдения нескольких ручных запусков.
- [Один или три запуска недостаточны для статистического вывода] → Позиционировать лабораторию как учебное наблюдение, сохранять raw ответы и exact uniqueness, не строить significance/average score.
- [Concurrent calls могут получить rate limit или разную server load] → Изолировать ошибки, не делать hidden retries и не использовать latency как основной вывод о temperature.
- [Точное benchmark-сравнение чувствительно к невидимой правке whitespace] → Дать «Вернуть benchmark» и явно показывать free-mode сообщение; не нормализовать prompt за пользователя.
- [Alias `gpt-5.6` со временем может указывать на обновлённый snapshot] → Показывать requested model/config и считать результаты наблюдениями текущего API, не заявлять долговременную воспроизводимость snapshot.
- [Третья destination уплотняет нижнюю навигацию телефона] → Использовать короткие Day labels/icons и русские полные labels, проверить на phone-size emulator без новой navigation dependency.
- [Refactor shared AppContainer/API wiring может задеть Day 02/03] → Делать additive slice, сохранить старые interfaces и прогнать существующие regression tests.

## Migration Plan

1. Выполнить live compatibility gate; при любом несовместимом параметре остановиться до обновления плана.
2. Добавить backend domain/models/service tests, затем batch endpoint и regression tests существующих API.
3. Добавить Android DTO/repository/ViewModel/screen и третью destination, затем unit/UI checks для history и uniqueness.
4. Создать Day 04 README, обновить необходимые index README и выполнить backend tests, Android unit tests/debug assemble, emulator smoke и secret scan.

Изменение additive и не требует data migration. Rollback удаляет только новый endpoint/modules, Android destination/screen и Day 04 документацию; существующие Day 02/03 продолжают работать.
