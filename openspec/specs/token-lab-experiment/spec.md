# token-lab-experiment Specification

## Purpose

Определяет измеримый эксперимент Day 08 над полной историей агента: отдельную фиксированную модель, preflight и actual token usage, оценочную стоимость и настоящий context overflow без повреждения подтверждённого диалога.

## Requirements

### Requirement: One fixed model owns the isolated token laboratory

Все short, long и overflow запросы Day 08 SHALL использовать `gpt-4o-mini`, одинаковые фиксированные instructions, plain text output, output budget 1200, `service_tier=default`, `store=false`, `truncation=disabled` и zero automatic retries. Context window SHALL быть 128000 tokens; максимальный output модели 16384 SHALL отличаться от budget лаборатории. Unsupported reasoning parameters SHALL отсутствовать. Day 08 SHALL NOT принимать model/config/history от Android или выполнять model switching. API namespace `/api/v1/token-lab/sessions` SHALL обслуживать только собственные sessions, включая restore после restart. Day 06/07 SHALL сохранять прежнюю конфигурацию `gpt-5.6` и namespace.

#### Scenario: All stages retain the same model
- **WHEN** пользователь проходит short, long и overflow этапы Day 08
- **THEN** каждый generation request использует ту же конфигурацию `gpt-4o-mini` без reasoning fields, fallback или automatic truncation

#### Scenario: A session ID crosses laboratory boundaries
- **WHEN** ID Day 06/07 передан в GET, send или overflow endpoint Day 08 либо ID Day 08 передан в старый GET/send
- **THEN** запрос получает 404 `session_not_found` без provider calls и обращения к чужой history
- **AND** DELETE через неверный namespace не удаляет чужую session; это остаётся верно после restart

### Requirement: Durable sessions contain only confirmed full history

Day 08 SHALL создавать durable session по пустому JSON только при явной операции пользователя и восстанавливать metadata по собственному ID без экспорта history. Create/GET/delete SHALL NOT вызывать OpenAI или требовать API key. GET SHALL возвращать identity/count, busy — 409, отсутствующий ID — 404, некорректный UUID — 422. Успешный обычный turn SHALL добавлять ровно одну user/assistant пару одной транзакцией до HTTP success; RAM snapshot SHALL обновляться после persistent commit. Failed, preflight-rejected, incomplete, refused, cancelled-before-commit и overflow attempts SHALL NOT менять history/count. Storage failure SHALL NOT изображаться success или пустой session. Delete SHALL быть durable и изолированным, не создавать замену; restart SHALL NOT возвращать удалённую history. Busy/delete guards и точный restore полных пар SHALL сохраняться. SQLite schema SHALL NOT дополняться token/cost/attempt fields; oversized failed payload SHALL NOT сохраняться.

#### Scenario: Restore and continue
- **WHEN** после U1/A1 backend перезапущен и поступает U2 с тем же Day 08 ID
- **THEN** generation получает ровно U1/A1/U2 в исходном порядке и после успеха сохраняется одна дополнительная пара

#### Scenario: A failed attempt survives no storage reopen
- **WHEN** после подтверждённого хода preflight или provider возвращает ошибку и storage открывается заново
- **THEN** history/count идентичны состоянию до попытки и следующая допустимая отправка использует прежний контекст

#### Scenario: Commit or delete cannot be confirmed
- **WHEN** durable commit пары или delete завершается storage error
- **THEN** API не сообщает успех и не публикует неподтверждённое изменение RAM history

### Requirement: Normal send includes preflight without a separate preview step

Обычный `POST /{session_id}/messages` SHALL принимать только исходный `message` длиной 1–20000 символов с непробельным содержимым. Явный Send SHALL занимать session, фиксировать immutable history/config snapshot, выполнять provider preflight, максимум одну generation, получать actual usage и commit только пригодного completed ответа. Отдельный mandatory Preview SHALL отсутствовать. Counting calls SHALL учитываться отдельно от generation attempts. Все стадии SHALL освобождать busy при завершении или отмене. Параллельная операция той же session SHALL получать 409 без provider call. Другие sessions SHALL оставаться доступными.

#### Scenario: One explicit normal send
- **WHEN** свободная session получает допустимое новое сообщение
- **THEN** backend выполняет preflight и не более одного generation call с полной подтверждённой history и новым user message
- **AND** клиент не обязан предварительно вызывать preview и не отправляет history/config

#### Scenario: Preflight fails or input exceeds the window
- **WHEN** официальный count недоступен, malformed либо preflight_input_tokens превышает 128000
- **THEN** normal send возвращает безопасную preflight ошибку с доступными diagnostics, без generation и commit
- **AND** такой результат не считается реальным provider generation overflow

#### Scenario: Output reserve warns without changing input
- **WHEN** preflight_input_tokens не превышает 128000, но preflight_input_tokens плюс reserved output превышает окно
- **THEN** diagnostics показывают нехватку резерва, generation сохраняет исходные input/budget и полный контекст
- **AND** incomplete вследствие output budget не подменяется подтверждённым input context-limit rejection

### Requirement: Provider measurements are independent and use one immutable snapshot

Подсчёт SHALL использовать официальный Responses input-token counting endpoint без local tokenizer. `current_message_tokens` SHALL измерять самостоятельный request fixed Day 08 model с input=[current user], без instructions/history. `saved_history_tokens` SHALL измерять самостоятельный request той же model с непустой saved history в исходных roles/text/order, без instructions/current. При пустой history backend SHALL вернуть 0 с source empty_history без provider call: это отсутствие conversation messages, не count пустого Responses request. `preflight_input_tokens` SHALL измерять exact generation context с fixed instructions, полной saved history и current message, теми же совместимыми model/input/text/truncation settings, без generation-only kwargs. Все измерения SHALL использовать один immutable history/current/config snapshot; измеряемый текст SHALL NOT переписываться.

Diagnostics SHALL возвращать эти три независимых значения со source/status, context limit и reserved output. Current/history SHALL обозначать standalone structured provider counts с message formatting, а не additive contribution или только visible text. Значения SHALL NOT складываться в full input; системная часть SHALL NOT вычисляться разностью. Монотонность или равенство между независимыми counts SHALL NOT требоваться. Каждый provider count SHALL быть неотрицательным integer; missing/bool/negative/non-integer SHALL давать count failure с сохранением частичных measurements без estimate/zero substitution. Counting cache и optimization framework SHALL отсутствовать; create/GET/delete и Day 06/07 SHALL NOT выполнять count calls.

#### Scenario: Independent measurements describe the request before commit
- **WHEN** mock provider отдельно вернул current=12, saved_history=31 и preflight_input=40
- **THEN** diagnostics сохраняют 12, 31 и 40 без сложения, вычитания или проверки относительного порядка
- **AND** после commit числа остаются snapshot отправленной попытки, а системная часть не выводится из разности

#### Scenario: First normal turn has no history request
- **WHEN** допустимый первый normal Send проходит все counts
- **THEN** выполняются current-only и full count, saved_history_tokens=0 без provider call
- **AND** generation calls не более одного, source empty_history не выдаётся за ответ provider на пустой input

#### Scenario: Subsequent normal turn counts saved messages separately
- **WHEN** normal Send с непустой history проходит все counts
- **THEN** последовательно выполняются current-only, history-only и full count, затем не более одной generation
- **AND** первые два count request не содержат instructions; full сохраняет точные instructions generation

#### Scenario: Exact snapshot and context settings are preserved
- **WHEN** history/current содержат Unicode, переводы строк и пробелы
- **THEN** выбранные сообщения каждого измерения сохраняют roles/text/order snapshot, а full count и generation используют один полный context
- **AND** generation-only options не отправляются count endpoint; instructions не превращаются в synthetic message, dummy/sentinel input отсутствует

#### Scenario: Count failure preserves partial diagnostics
- **WHEN** current-only count получен, но следующий обязательный count отклонён или вернул malformed значение
- **THEN** уже известный current и structural empty-history zero при применимости сохраняются; неполученные значения unavailable
- **AND** дальнейшие count/generation calls и commit отсутствуют; local estimate, tiktoken и heuristic fallback не используются

### Requirement: Early provider smoke gates implementation

До продолжения реализации после review обновлённых artifacts SHALL быть проведён отдельный разрешённый provider-count smoke: current-only single user без instructions; history-only непустая user/assistant fixture без instructions; full с fixed instructions + той же history + current; deterministic oversized full. Первые три результата SHALL быть неотрицательными integers, oversized full SHALL подтвердить диапазон 132000–160000 при limit 128000. Generation/commit SHALL отсутствовать. Fixtures SHALL явно называться тестовыми, не measured conversation. Исторический failed smoke SHALL сохраняться как факт, не переписываться успехом. Отказ любого обязательного контракта SHALL остановить apply для review без fallback.

#### Scenario: New count contract is supported
- **WHEN** все четыре обязательных smoke measurements получили валидные результаты и oversized full вошёл в допустимый диапазон
- **THEN** записан безопасный factual report с generation calls=0, и count contract gate допускает продолжение apply
- **AND** это не закрывает real generation overflow acceptance

#### Scenario: A required count contract fails
- **WHEN** любой обязательный smoke count отклонён, недоступен или не вернул integer либо oversized bounds не достигнуты
- **THEN** фиксируется конкретная стадия и безопасная ошибка, apply останавливается без изменения модели или подмены результата
- **AND** input-token rejection не называется подтверждённым generation context overflow

### Requirement: Actual usage remains separate and nullable for every outcome

Результат попытки SHALL сохранять доступные provider `input_tokens`, `cached_input_tokens`, `cache_write_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens`, resolved model и requested/actual service tier. Отсутствие SHALL отличаться от нуля; некорректные counters SHALL NOT превращаться в достоверные измерения. Preflight SHALL NOT заполнять отсутствующий actual input. Usage non-completed response SHALL сохраняться независимо от отсутствия commit. API SHALL возвращать безопасный outcome, attempt/request identity, history count и diagnostics без raw SDK objects, history или instructions. Unknown transport outcome SHALL NOT выдавать receipt, гарантировать отсутствие provider spend или запускать replay.

#### Scenario: Incomplete has billable usage
- **WHEN** provider вернул incomplete с доступными counters
- **THEN** reply отсутствует и history не меняется, но actual counters и доступная cost возвращаются

#### Scenario: Context error has no usage
- **WHEN** generation отклонена provider и usage отсутствует
- **THEN** preflight остаётся видимым, actual usage/cost unavailable и не подменяются нулями или preflight

### Requirement: Turn cost uses actual usage and fixed model pricing

Стоимость SHALL называться «Оценочная стоимость хода» и рассчитываться после generation на backend по actual usage и versioned model/rates/date/source. Для Standard `gpt-4o-mini` и явно разрешённого resolved snapshot `gpt-4o-mini-2024-07-18` rates от 2026-09-09 SHALL составлять USD за 1M tokens: input 0.15, cached input 0.075, output 0.60. Cache writes этой модели SHALL учитываться по обычному input rate без отдельной надбавки; если W возвращён, SHALL проверяться C+W<=I. Отсутствующий W SHALL оставаться null и не препятствовать формуле (I-C)*Ri+C*Rc+O*Ro для этой модели без отдельной write тарификации. Input, cached input и output SHALL быть известны; неизвестные resolved model/actual tier, недоступные необходимые counters или их противоречия SHALL давать unavailable с причиной. Reasoning SHALL NOT начисляться поверх output. Расчёт SHALL использовать точную decimal арифметику, не округлять внутренний USD до центов и не влиять на пригодность completed turn. Historical Day 05 wrappers/rates/results SHALL оставаться прежними.

#### Scenario: Cache reads reduce estimated input cost
- **WHEN** fixture usage равен I=1000, C=200, O=100, W отсутствует и model/tier известны
- **THEN** estimated amount равен USD 0.000195, W остаётся null, reasoning не добавляет повторную плату

#### Scenario: Unknown or inconsistent pricing inputs
- **WHEN** actual tier неизвестен, resolved model вне allowlist, C>I или известные C+W>I
- **THEN** cost unavailable, доступные actual counters сохранены и пригодный completed ответ всё ещё может commit'иться

### Requirement: Oversized preparation is deterministic visible and bounded

Отдельная операция `POST /{session_id}/overflow/prepare` с пустым JSON SHALL подготовить один deterministic новый user message поверх реальной saved history, не создавая fake assistant messages. Она SHALL выполнять только provider counting, без generation/commit. Успешная подготовка SHALL подтвердить exact preflight_input_tokens в диапазоне 132000–160000 при model limit 128000, вернуть full diagnostics, размер текста/полного payload, описание алгоритма и повторяемого блока, число повторов, digest и одноразовый preparation ID. Размер/count probes SHALL иметь конечные application bounds, явно отличимые от model context limit. Provider failure, full count вне допустимого диапазона либо исчерпание bounds SHALL оставлять workflow неготовым к generation без synthetic count. Подготовка SHALL отпускать session до ожидания действия пользователя. Targeting SHALL зависеть только от exact full provider count с instructions + real saved history + oversized current. Prepare SHALL выполнять максимум четыре full count probes; standalone current/history calls SHALL отсутствовать, их значения SHALL быть not_measured/null (пустая history допускает structural 0). Measurements разных candidates SHALL NOT смешиваться; count предыдущего payload SHALL NOT разрешать execute нового payload.

#### Scenario: Prepared overflow is a new visible input
- **WHEN** пользователь явно выбирает подготовку overflow в session с четырьмя подтверждёнными ходами
- **THEN** показываются измеренный full preflight 132000–160000 и описание нового deterministic payload
- **AND** history/count остаются 4, generation count равен 0, session не удерживается busy во время чтения предупреждения

#### Scenario: Counting itself rejects oversized input
- **WHEN** count endpoint возвращает context/rate/body-size error вместо подтверждённого full count
- **THEN** подготовка явно не завершена, кнопка выполнения недоступна и реальный generation overflow не заявляется

### Requirement: Overflow execution requires explicit single-use authorization

`POST /{session_id}/overflow/execute` SHALL принимать только `preparation_id` и `confirm=true` после отдельного явного действия пользователя. Backend SHALL проверить namespace/session, срок действия, неизменность history/config/payload и одноразовость подготовки, занять session и атомарно потребить разрешение до сетевого await. Generation SHALL использовать exact ранее подсчитанный full payload с disabled truncation и zero retries, ровно один раз на валидное разрешение, без дополнительных count calls. Stale/expired/used/mismatched preparation SHALL дать безопасную ошибку без generation; normal successful turn/reset/restart SHALL инвалидировать прежнюю подготовку. Timeout, повтор HTTP или повторное нажатие SHALL NOT инициировать второй generation из того же разрешения. Ни один overflow probe SHALL commit'иться, включая неожиданное принятие provider; unexpected acceptance SHALL отображаться отдельно и не считаться доказанным overflow.

#### Scenario: User confirms a prepared overflow
- **WHEN** пользователь отдельно подтверждает актуальную измеренную подготовку
- **THEN** выполняется один настоящий Responses generation attempt с тем же полным snapshot
- **AND** в SQLite не появляется oversized сообщение, независимо от provider outcome

#### Scenario: Double click or stale history
- **WHEN** execute повторён либо после prepare успешно завершился обычный turn
- **THEN** использованное/устаревшее разрешение не вызывает generation и требует новой явной подготовки

### Requirement: Only a confirmed provider context error proves overflow

Только структурированная provider context-limit ошибка generation SHALL нормализоваться как `context_limit_exceeded` с `error_origin=provider`. Код HTTP 400 сам по себе, 413, 429, timeout, invalid parameters и count-endpoint rejection SHALL NOT считаться доказательством model overflow. API SHALL различать безопасные context, rate-limit, body-size, timeout и прочие upstream errors, не отдавая raw request/exception. Подтверждённый overflow SHALL возвращать reply=null, сохранённый preflight, доступный actual usage либо unavailable, прежние history/count и освобождённую session. Compression/trimming/replay SHALL отсутствовать.

#### Scenario: Genuine context rejection
- **WHEN** generation возвращает подтверждённый provider context-limit error
- **THEN** результат содержит `context_limit_exceeded`, `error_origin=provider`, прежний count и preflight
- **AND** следующий нормальный короткий turn в этой session разрешён и получает прежнюю history

#### Scenario: Rate limit or unexpected successful generation
- **WHEN** probe получает 429 либо provider неожиданно принимает oversized request
- **THEN** UI получает соответственно rate-limit outcome либо unexpected acceptance, доступный actual usage и неизменную history
- **AND** эксперимент overflow не объявляется успешным и fallback generation отсутствует

### Requirement: Short and long observations explain full-history growth honestly

Эксперимент и Day README SHALL описывать четыре реальных обычных хода: короткий факт, короткий вопрос о нём, явно подготовленный длинный текст с просьбой коротко ответить, снова короткий вопрос. Измерения SHALL браться из текущего backend response, без заранее заданных ожидаемых чисел и десятков обязательных платных calls. Теоретическое объяснение SHALL различать примерно линейный current context при постоянных размерах ходов, примерно квадратичный cumulative processed input full-history calls и влияние длинного assistant output на будущий input. Caching SHALL объяснять отсутствие гарантии монотонного per-turn USD роста; cumulative cost известных платных calls SHALL складываться без уменьшения. Теоретические примеры SHALL быть подписаны как расчёт, а не результат проекта. UI/README SHALL объяснять, что standalone current/history и full preflight неаддитивны: full включает instructions и полное request formatting; системная часть из разностей SHALL NOT вычисляться.

#### Scenario: A short message follows the long exchange
- **WHEN** после длинного user/короткого assistant обмена отправляется короткий вопрос
- **THEN** UI показывает измеренные current/history/full input и позволяет увидеть большой контекст при малом новом сообщении
- **AND** README содержит только реально проверенные наблюдения либо явное «проверка ещё не проведена»

### Requirement: Measurement history is runtime observation only

Таблица попыток SHALL содержать номер, actual input/output и estimated turn cost, включая unavailable у неуспеха. Historical metrics SHALL NOT записываться в SQLite, preferences или восстанавливаться из bubbles/messages. Необязательные cumulative metrics SHALL суммировать только backend-reported actual values за явно обозначенный runtime интервал, не учитывать preflight как generation usage и не выдавать частичную известную сумму за полную стоимость session. Повтор доставки одного результата SHALL NOT удваивать таблицу/суммы.

#### Scenario: Restart loses measurements but preserves conversation
- **WHEN** Android холодно стартует с сохранённым Day 08 ID
- **THEN** восстанавливаются ID/count, но таблица и monetary totals предыдущего запуска отсутствуют
- **AND** следующий preflight вычисляет историю из backend session, независимо от пустого transcript
