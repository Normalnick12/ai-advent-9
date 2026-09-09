## Context

Мотивация и границы изменения — в [proposal.md](proposal.md). Текущий `SimpleAgent.run_turn` собирает `(*session.history, user)`, вызывает `LlmClient.complete` и commit'ит только непустой completed без error. `AgentSession.commit` сначала пишет пару в SQLite, затем заменяет immutable RAM tuple; busy освобождается в finally. Один backend worker владеет соединением и session manager. Существующий adapter теряет usage и обобщает OpenAI errors.

Day 06/07 используют одну конфигурацию `gpt-5.6`, reasoning none, output budget 1200; старые HTTP DTO разрешают только message до 20000 символов. Android `ChatViewModel` уже управляет сложным restore/reset/unknown-outcome lifecycle. Day 05 имеет независимые benchmark usage/pricing DTO и проверенные исторические суммы.

Официальные источники проверены 2026-09-09:

- [GPT-4o Mini](https://developers.openai.com/api/docs/models/gpt-4o-mini): context window 128000, max output 16384, Responses API, alias/snapshot, Standard rates 0.15/0.075/0.60 USD за input/cached/output MTok.
- [Counting tokens](https://developers.openai.com/api/docs/guides/token-counting) и [Python count API](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens): provider preflight учитывает message formatting; это отдельная операция до generation. Установленный SDK 2.54.0 уже содержит метод.
- [Responses create](https://developers.openai.com/api/reference/python/resources/responses/methods/create): disabled truncation отклоняет превышение input; HTTP 400 без структурированной причины недостаточен для классификации.
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): у моделей до GPT-5.6 нет отдельной надбавки за cache write. Для GPT-4o Mini не переносим write multiplier 1.25 из Day 05.

Фактический отказ прежнего пустого count request сохранён без изменений в [provider-count-smoke.md](provider-count-smoke.md). Новый контракт независимых измерений ещё не проверен live: current-only, non-empty history-only, full и oversized full проверяются ранним smoke после review. До успешного smoke реализация не продолжается; без реального generation rejection acceptance overflow не закрывается.

## Goals / Non-Goals

**Goals:** измерять одну попытку по exact snapshot; не смешивать provider preflight с расходом generation; сохранять durable атомарность; изолировать конфигурации после restart без schema migration; дать ограниченное одноразовое выполнение настоящего overflow.

**Non-Goals:** все исключения proposal сохраняются. Дополнительно: нет обязательного normal-preview экрана, локального tokenizer, generic policy/observer framework, refactoring Day 05, возврата internal history, durable attempt receipts и exactly-once доставки HTTP. Overflow разрешение предотвращает повторную generation в одном runtime, но не является billing journal.

## Decisions

### 1. Isolation by API namespace and separate existing-schema storage

Composition root создаёт два `SimpleAgent` instance одного класса:

| Scope | Config | Manager/store | HTTP namespace |
|---|---|---|---|
| Day 06/07 | существующий AgentConfig без изменений | существующие manager и `.local/agent/conversations.sqlite3` | `/api/v1/agent/sessions` |
| Day 08 | immutable `day08-gpt4o-mini-v1` | отдельные manager и `.local/token-lab/day08-gpt4o-mini-v1/conversations.sqlite3` | `/api/v1/token-lab/sessions` |

Оба store используют один `SQLiteConversationStore` и ту же schema sessions/messages. Оба сохраняют прежние commit/restore/delete проверки. Path вычисляется от repo root, не cwd, не принимается от HTTP. Lifespan проверяет, что resolved пути различаются; ошибочная настройка одинакового файла блокирует startup вместо смешивания моделей. Ресурсы закрываются и при частичном startup failure. Нет глобального поиска ID в обоих stores или fallback lookup.

ID — UUID как прежде. Истина identity — пара namespace + UUID: GET/send/prepare/execute смотрят только в свой manager. Wrong-namespace ID даёт 404; идемпотентный DELETE чужого ID возвращает 204, не затрагивая чужой файл. Restart восстанавливает session только в том же namespace. Клиент не выбирает config через body.

Config version является частью storage namespace. Будущая смена Day 08 instructions/model требует осознанного нового config namespace; существующая база не открывается с другой конфигурацией. Version, model и fingerprint связаны regression test. SQLite не хранит новую колонку model.

Альтернативы: колонка namespace/model требует migration и расширяет schema; один manager с выбором модели по UI-флагу допускает misrouting после restart; новый Agent implementation дублирует full-history алгоритм. Отдельный файл минимален для учебного приложения и не меняет старые данные.

### 2. Immutable configuration and neutral attempt results

`AgentConfig` становится constructor-injected, с прежними defaults для Day 06/07. Day 08: `model=gpt-4o-mini`, прежние краткие русские instructions, `max_output_tokens=1200`, reasoning unset, `service_tier=default`, `truncation=disabled`, plain text, store false. Optional transport fields добавляются в payload только при заданном значении: Day 06/07 exact payload остаётся прежним, GPT-4o Mini никогда не получает reasoning object, даже effort none.

Небольшие frozen dataclasses:

- `TokenUsage`: nullable provider integer counters; bool/negative/non-integer не принимаются. Доступные корректные значения сохраняются; consistency отмечается отдельно.
- `LlmResult`: прежний outcome плюс usage, requested/resolved model и requested/actual service tier. Pricing здесь отсутствует.
- `TokenDiagnostics`: nullable `current_message_tokens`, `saved_history_tokens`, `preflight_input_tokens`; отдельные measurement status/source (provider_preflight, empty_history или not_measured), config version, history_turn_count_before, context window, reserved output, count error и число count calls. Пустая history — единственный явный structural zero без provider call; unavailable измерение остаётся null.
- `AgentTurnResult`: LLM outcome, diagnostics текущей попытки, commit/outcome metadata. Не хранится в session history.
- `EstimatedCost`: available/unavailable, decimal USD string, reason, model/tier/rates/date/source.

OpenAI-specific objects нормализуются внутри adapter. `SimpleAgent` не импортирует SDK, Pydantic HTTP DTO или pricing modules. Старый route проецирует новый результат в прежний `AgentTurnResponse` без добавления wire fields; Day 08 route возвращает diagnostics DTO. Invalid-completed validation не должна отбрасывать уже полученный usage. Incomplete/refused/failed responses нормализуют usage до ветвления по status.

### 3. Provider TokenCounter and one exact snapshot

Async `TokenCounter.count(messages, config, *, include_instructions)` возвращает provider integer count либо нейтральную безопасную count failure. Явный флаг задаёт область измерения, не меняя immutable generation configuration. Реализация `OpenAIInputTokenCounter` использует SDK, без tiktoken. `SimpleAgent` получает optional counter: None у Day 06/07; подключён у Day 08. Общий маленький context payload helper гарантирует совпадение full count с generation по model/instructions/input/text/truncation. Count получает только поддерживаемые поля; generation-only max_output_tokens/store/service_tier не передаются через `**generation_payload`.

Под session busy guard создаётся один immutable PreparedContext: saved history tuple, current user message, config и history identity. Все измерения относятся к этому snapshot, без изменения roles/text/order или обращения к Android bubbles.

| Measurement | Provider request | Смысл |
|---|---|---|
| `current_message_tokens` | fixed model, input=[current user], instructions omitted | Standalone count нового сообщения вместе с message formatting |
| `saved_history_tokens` | fixed model, input=saved history, instructions omitted; без current | Standalone count conversation messages; при пустой history значение 0 с source empty_history без API call |
| `preflight_input_tokens` | exact full context: fixed instructions + saved history + current | Полный provider preflight count для context utilization, проверки лимита и overflow targeting |

Standalone запросы сохраняют те же поддерживаемые text/truncation settings; reasoning object отсутствует. Count API не получает пустой request. Instructions не переносятся в synthetic message; dummy/sentinel input, local tokenizer и heuristic fallback запрещены.

Три числа **неаддитивны**: current/history измерены как самостоятельные structured requests, full содержит instructions и полное оформление запроса. Суммы/разности для выделения системной части не вычисляются, равенство суммы full и монотонность между измерениями не проверяются. Каждый provider result валидируется независимо: неотрицательный integer, не bool; missing/malformed даёт count failure. Snapshot diagnostics остаётся привязан к попытке до commit. Нет counting cache, deduplication/optimization framework или startup counts; metadata lifecycle не требует provider.

Normal lifecycle: claim -> snapshot -> current-only count -> history-only count (либо structural zero) -> full count -> budget diagnostics -> максимум одна generation -> usage -> validate -> durable pair commit -> return -> release. Первый turn при успешном preflight делает **2 count calls**, последующие с непустой history — **3**, последовательно, без retries. При ошибке любого count цепочка прекращается: уже полученные diagnostics и structural zero сохраняются, неполученные значения null, generation/commit отсутствуют.

Только `preflight_input_tokens` является источником context utilization и preflight guard. Значение >128000 даёт `preflight_context_exceeded`, origin preflight; это не provider generation overflow. Значение <=128000 при сумме с reserved output 1200 >128000 даёт warning, не меняет input/output budget. Основная fraction — preflight_input_tokens/128000 и после generation остаётся подписанной preflight; actual input показывается отдельно и не подменяет этот источник. Необязательная reserve fraction — (preflight_input_tokens+1200)/128000, явно «с резервом ответа», не actual usage. 126800 — бюджет при полном резерве, не другой model limit; reasoning повторно не добавляется.

Count timeout 15 секунд на call, общий normal-preflight deadline 45 секунд; generation сохраняет deadline 75 секунд. Итог укладывается в существующий Android call timeout 190 секунд. Zero SDK/application retries и finally release распространяются на обе стадии. Огромная диагностика не должна блокировать event loop другой session длительной синхронной подготовкой.

### 4. Separate Day 08 API and diagnostic error contract

| Endpoint относительно `/api/v1/token-lab/sessions` | Request | Result |
|---|---|---|
| POST empty path | `{}` | 201 identity/count после durable create |
| GET `/{id}` | без body | 200 identity/count, без OpenAI |
| DELETE `/{id}` | без body | 204 после durable delete |
| POST `/{id}/messages` | только message, 1–20000 chars | 200 outcome + attempt ID + preflight/usage/cost + committed count |
| POST `/{id}/overflow/prepare` | `{}` | prepared либо явная preparation failure; generation calls=0 |
| POST `/{id}/overflow/execute` | preparation_id, confirm=true | outcome одного probe с теми же diagnostics и неизменным count |

HTTP validation/session errors сохраняют безопасный envelope и X-Request-ID; ошибка provider/preflight является outcome завершённого обработчика, чтобы Android не потерял diagnostics в generic transport exception. Day 08 DTO явно различает `error_origin=preflight|provider|application`, `generation_attempted`, `committed`, raw response status при наличии и безопасный error code. В prepare/execute нельзя прислать arbitrary history, повторения, tokenizer, limit, model или config. Counter results не становятся monetary usage.

Context классификация использует allowlist structured provider error codes/types для context length (например, подтверждённый `context_length_exceeded`), проверенную live capture без приватного тела. Нельзя классифицировать по одному HTTP 400 или произвольному substring текста. 429 -> rate limit, 413 -> body size, timeout -> timeout, прочие -> безопасная upstream/invalid request ошибка. Raw exceptions, instructions, history и полный prepared payload в logs не выводятся. SDK retries и OkHttp retry остаются выключенными.

### 5. Controlled deterministic overflow, no generic large-message endpoint

Обычный message limit 20000 одинаково остаётся в старом API и нормальном Day 08 composer. Большой payload создаётся только server-side prepare path; Android передаёт действие, а не скрытую history. UI/README показывают рецепт: «один новый тестовый user message: фиксированный заголовок, N повторов ASCII-блока, просьба коротко ответить». Canonical unit v1 — строка `0123456789 abcdefghijklmnopqrstuvwxyz` с LF. Заголовок объясняет, что это тест заполнения контекста, заключительная инструкция — «Ответь кратко: принято». Программа считает весь request; токены одного блока не умножаются с объявлением точного full count.

Prepare берёт реальную history под тем же guard и строит immutable candidate. Начальный N=8192; targeting использует только exact full provider count (instructions + real history + oversized current). Максимум четыре candidate full count calls, target 140000, accepted preflight_input_tokens 132000–160000. Для следующего кандидата N_next=ceil(N*140000/measured_full_count); это лишь выбор следующего размера, не token estimate для diagnostics. Каждый кандидат полностью считается provider заново; повтор N, недостижимые bounds или отсутствие результата за четыре пробы останавливают prepare без generation. Если исходная history делает bounds недостижимыми, предлагается новый диалог без удаления текущего.

Standalone current/history для overflow не вызываются: UI достаточно exact full count и размеров payload. Их значения null со статусом not_measured; только пустая saved history может иметь structural 0. Подготовка требует 1–4 full count calls и 0 generation/commit. Execute использует уже подготовленные diagnostics без нового counting. Partial diagnostics сохраняют измерения по candidate identity: count предыдущего кандидата не маркируется как count нового payload и не разрешает execute.

Полный serialized generation JSON (history included) ограничен 2 MiB UTF-8 до отправки count/generation. Это application resource cap, не context limit. Подготовка имеет общий deadline 90 секунд. Response содержит exact full preflight diagnostics и статусы standalone measurements, current text chars/UTF-8 bytes, full payload bytes, unit/repeat count, sample начала/конца нового текста, SHA-256 точного canonical payload, model/config version и timestamp. Внутренняя history не экспортируется. Сокращённый sample в UI не сокращает реальный payload.

Успешная подготовка сохраняется только в RAM: random opaque ID, namespace/session, history tuple/fingerprint/count, config fingerprint, payload bytes/digest, diagnostics, expiry 10 минут. Один active preparation на session; новая явная подготовка инвалидирует предыдущую. Не более 16 одновременно хранимых preparations в backend; истёкшие очищаются, при исчерпании cap новая подготовка отклоняется. Это ограниченный temporary control state, не долговременное хранилище.

Prepare освобождает busy до показа предупреждения. Execute требует confirm=true и bound preparation ID. Под guard повторно проверяются session/config/history/digest/expiry; token атомарно изымается из active map до generation await. Повтор того же ID никогда не генерирует; timeout не возвращает token. Successful normal commit/reset инвалидируют подготовку; restart теряет все tokens и не возобновляет запросы. Stale или неизвестное разрешение требует новой явной подготовки и подтверждения, без автоматического prepare/execute.

Probe пользуется теми же prepare-context/LLM invocation/normalization helpers одного `SimpleAgent`, но отдельным узким методом выполнения диагностической попытки **без права commit**. Не создаётся второй Agent algorithm или generic commit-policy framework. Даже неожиданный completed от provider возвращается как `unexpected_provider_acceptance`, без reply/history mutation, с сохранением actual usage/cost. Это failed experiment, а не повод сохранить огромный user message. Для обычного run_turn прежнее правило completed -> atomic pair не меняется.

Только structured context rejection от generation завершает acceptance overflow. Если count сам отклоняет oversized input, prepare честно fails: нельзя подставить estimate и включить execute. Если generation даёт 413/429/timeout, acceptance остаётся непроверенным. Нет меньшей модели, soft-limit демонстрации или скрытого retry в качестве подмены.

Альтернатива arbitrary oversized text upload расширила бы публичную поверхность без учебной пользы. Детерминированный видимый recipe даёт воспроизводимость без fake saved turns и передачи мегабайт через Android.

### 6. Model-specific minimal pricing, no Day 05 refactor

Отдельная pure Day 08 function принимает нейтральный usage/model/actual tier и frozen rate record. Allowlist resolved models: `gpt-4o-mini`, `gpt-4o-mini-2024-07-18`; никаких prefix guesses. Requested tier фиксирован default, actual обязан быть подтверждён default. Source/date — официальная model page и 2026-09-09. Несовпадение будущего resolved ID даёт unavailable до отдельной проверки tariffs, не switch модели.

При I,C,O известных: `((I-C)*0.15 + C*0.075 + O*0.60)/1000000`. Reasoning уже входит в O. Для GPT-4o Mini write имеет тот же rate 0.15: если W присутствует, эквивалентная явная формула `((I-C-W)*Ri + C*Rc + W*Ri + O*Ro)/1e6`, с проверкой C+W<=I. Если W отсутствует, оно остаётся null: это отсутствие необязательной детализации, а не отсутствие необходимого billing operand для данного тарифа. Нет выдуманного write multiplier.

Проверяются неотрицательные integer counters, C<=I, при известных W — C+W<=I, при известном R — R<=O, при известном total — total=I+O. Неполный обязательный usage, неизвестный model/tier или inconsistency дают unavailable reason. Null optional total/reasoning не блокирует расчёт. Amount — Decimal string; display до 6–8 десятичных знаков с раскрытием точного значения, без округления маленького платного хода в «$0.00».

Стоимость относится к generation attempt, включая incomplete/refused при доступном usage, не только к commit. До generation денежная карточка unavailable. Rate record возвращается как attribution, не как invoice. Не гарантируем «отклонённый запрос бесплатен» или нулевой расход при timeout. Counting API calls не добавляются в cumulative generation input/cost; проект не утверждает их денежную стоимость без отдельного источника.

Day 05 файлы, wrappers, registry, thresholds и historical tests/results не меняются. Небольшое повторение decimal arithmetic предпочтительнее переноса benchmark types в Agent.

### 7. Android state and stateless component reuse

`TokenLabViewModel` и `TokenLabRepository` создаются в AppContainer; отдельный key `day_08_token_lab`. `SharedPreferencesCurrentSessionStore` переиспользуется с preferencesName `day_08_current_session`; ID сохраняется до первого send/prepare, очистка — после durable delete. Metadata restore не требует provider count и не изображает токены нулевыми: числа следующей попытки придут с backend. Нет history API, передачи bubbles или local pricing.

Из `ChatScreen` минимально выделяются stateless bubble/transcript/composer элементы с callbacks и slots. `ChatViewModel` Day 06/07 не получает ни overflow, ни token fields. Day 08 state различает normal send, preparing, prepared, executing, resetting, restoring и known/unknown errors. Normal send не требует preview; user draft после ошибки не пропадает. Diagnostics всегда подписаны как последняя попытка, не live draft count.

Основной diagnostics block показывает standalone current/history counts, exact full preflight input, actual input/output, preflight input/128000 и estimated cost. Подпись current/history — «Отдельный provider count, включая оформление сообщений». Постоянное краткое пояснение: «Эти измерения не складываются: новое сообщение и история посчитаны отдельно, полный input включает инструкции и оформление всего запроса». Карточки системной части нет. При overflow standalone counts помечены «не измерялось»; известная пустая history отображается как 0 с пояснением отсутствия сохранённых сообщений. Secondary details — model, источник count, pricing date/rates, cache/reasoning. Узкий экран прокручивает содержимое; крупный payload показывается через recipe/sample, не гигантскую Text bubble. Overflow action вынесен отдельно от composer, с явным warning/confirmation action. Expiry/stale preparation отключает execute; cancel освобождает только runtime preparation.

Таблица последних 20 попыток хранится в ViewModel, имеет монотонный runtime attempt number, server attempt/request ID и outcome. Повтор того же результата не добавляется второй раз. Prepare без generation не считается потраченным generation input; normal preflight failure/execute failure может иметь строку с unavailable counters. Process death/reset очищает observations; навигация и Activity recreation сохраняют их. Cumulative fields в минимальной реализации не добавляются: таблица достаточна для сравнения, а cold start не восстанавливает historical billing.

Known context error позволяет обычное продолжение той же session. Потерянный normal-send HTTP response сохраняет прежний uncertain-commit recovery: явный reset, без replay. Потерянный execute response не доказывает overflow и не допускает повтор token; normal send разрешается после отдельного metadata refresh подтверждённой свободной session. Это безопасно потому, что probe не имеет commit path; GET count не трактуется как receipt или подтверждение отсутствия расходов.

### 8. Four real turns and one separate overflow probe

Сценарий README/video при apply:

1. U1: «Мой кодовый цвет — янтарный. Ответь кратко». После A1 показать standalone current, history=0, небольшой full preflight, actual I/O и cost.
2. U2: «Какой мой кодовый цвет? Ответь кратко». После A2 показать включение U1/A1 в history и разницу current/full input.
3. По явному действию загрузить в composer deterministic long fixture v1: 200 строк вида «Запись NNN: учебный текст о стоимости повторной передачи истории.» и просьбу коротко подтвердить получение. Прежде чем отправлять, текст виден/редактируем; итоговая длина проверяется <=20000. U3/A3 — реальный turn, не seeded history.
4. U4: «Назови мой кодовый цвет одним словом». После A4 показать короткий current и большой history/full input, сравнить реальные строки таблицы. Не фиксировать заранее значения token counts или USD.
5. В этой же session явно prepare deterministic oversized user message; показать preflight_input_tokens в диапазоне 132000–160000 и реальный limit 128000. Отдельно нажать execute ровно один раз.
6. Зафиксировать generation provider context-limit error, прежний count 4, сохранённые preflight и отсутствие actual usage при его недоступности. Reopen backend/SQLite по тому же ID должен сохранить четыре пары.
7. U5: повторить короткий вопрос о цвете; успешный ответ/count 5 подтверждает, что rejected payload не отравил историю.

Итого: четыре сравниваемых успешных turn, один recovery turn, один overflow generation attempt плюс ограниченные count calls. Автоматических платных повторов нет. Incomplete или иная live ошибка записывается как фактический исход; эксперимент не объявляется успешным по mock tests. Отдельный verbose assistant turn необязателен; его эффект объясняется через фактическую сохранённую A3 либо теорию.

При постоянных размерах сообщений u и ответов a, условных постоянных накладных расходах S: `I_n ≈ S+u+(n-1)(u+a)`; `sum(I_n) ≈ N(S+u)+(u+a)N(N-1)/2`. Это theoretical calculation, не measured project data; S/u/a в формуле — условные величины модели, а не standalone provider measurements из UI. README объясняет, что current/history/full считаются отдельно и не складываются, а системная часть разностью не выводится. Current context примерно линейный, cumulative processed input может быть квадратичным; cached input также входит в API I, но не означает повтор всех физических вычислений. Verbose assistant output тарифицируется сейчас и входит в будущие inputs. Caching/разные O меняют per-turn USD, поэтому строго монотонный рост цены каждого хода не обещается; cumulative cost новых известных платных calls растёт. README кратко фиксирует эти различия и только проверенные результаты, подробные условия остаются здесь.

## Risks / Trade-offs

- [Count endpoint не принимает current-only, non-empty history-only, full или oversized full] -> обязательный ранний smoke всех четырёх contracts после review, generation=0. При любом отказе или non-integer остановить apply, сохранить фактический blocker; не вводить fallback и не продолжать live-dependent реализацию.
- [TPM/body-size limit наступит раньше context rejection] -> один bounded probe около 140K, явно отличать 413/429; проверять доступ/лимиты перед live, не прогревать сотнями calls и не переключать модель.
- [Count и create могут разрешить alias иначе либо неожиданно принять input] -> фиксированные config/payload, обе метрики отдельно, unexpected acceptance не commit'ит probe и не засчитывает overflow.
- [Дополнительная latency/network dependence preflight] -> только Day 08, bounded timeouts/count calls; metadata/Day 06/07 работают без них.
- [Preparation устаревает] -> immutable fingerprint, одноразовое разрешение, TTL, invalidation на commit/reset/restart, проверки под guard.
- [При timeout неизвестен расход] -> unavailable/unknown, без retries и нулевой фиктивной стоимости; durable history гарантируется локальными commit правилами, не доставкой HTTP.
- [Общие DTO/components могут сломать Day 02–07] -> сохранить старую wire projection и exact payload tests; минимальное выделение UI и regression navigation/Chat tests.

## Migration Plan

1. После review при apply сначала выполнить обновлённый smoke: current-only single user; history-only непустая user/assistant fixture; full с fixed instructions + той же history + current; deterministic oversized full по bounded recipe, integer 132000–160000. Fixtures явно тестовые, не выдаются за реальный диалог и не пишутся в SQLite. Все результаты — nonnegative integer, generation calls=0. Сохранить безопасные результаты отдельно от исторического failure в существующем smoke report; при любом провале остановиться для review. Только после успеха всех contracts реализовать neutral models/config injection без изменения старых payload/DTO.
2. Добавить отдельный store/manager/config namespace и routes, затем preflight/pricing/overflow control и Android screen.
3. Существующий SQLite файл не переносить и не мигрировать. Новые таблицы в отдельном Day 08 файле создаются тем же store; оба файла остаются локальными игнорируемыми данными.
4. Запустить offline backend/JVM/UI regression проверки, затем отдельный управляемый live сценарий с явным подтверждением overflow из UI. Обновить Day README фактическими наблюдениями; незавершённый live acceptance оставить открытым.
5. Rollback — отключить новые routes/card/composition, сохранив новый SQLite файл на диске; старые файлы данных и конфигурация не затронуты. Не удалять пользовательские данные ради rollback.

## Open Questions

Нерешённых архитектурных решений после этой редакции нет. Новый provider contract пока не подтверждён: review artifacts, затем успешный smoke всех четырёх измерений обязательны до продолжения apply. Исторический count failure остаётся фактом и не считается успехом новой схемы. Неуспех smoke не разрешает менять модель, вводить fallback/soft limit или закрывать live acceptance.
