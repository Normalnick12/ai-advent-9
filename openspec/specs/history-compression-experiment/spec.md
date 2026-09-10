# history-compression-experiment Specification

## Purpose

Определяет Day 09 как измеримый переход от полной истории к rolling summary и фиксированному raw tail с сохранением исходного диалога, явной стоимостью summarization и проверкой сохранения фактов.

## Requirements

### Requirement: Compression owns an isolated fixed configuration

Day 09 SHALL обслуживаться namespace `/api/v1/compression-lab/sessions`, отдельной config-versioned SQLite database и фиксированной `gpt-4o-mini` для response и summarizer. Response config SHALL иметь одинаковые instructions, plain text format, output budget 1200, `service_tier=default`, `store=false`, `truncation=disabled`, окно 128000 и отсутствие reasoning parameters для normal/FULL/COMPRESSED requests. Summarizer SHALL иметь отдельные fixed instructions и output budget 384. Все calls SHALL иметь zero automatic retries; model switching SHALL отсутствовать. Android SHALL NOT отправлять history, summary, instructions, model, N или API key. Неверный UUID/поля/пустой либо длиннее 20000 символов message/question SHALL давать 422 до provider calls.

Create с `{}` SHALL возвращать 201 и identity/count; GET SHALL read-only восстанавливать identity/count и durable summary metadata без OpenAI/count/paid repair; отдельный read-only summary endpoint SHALL разрешать раскрытие durable summary text. GET/send/compare чужого либо отсутствующего ID SHALL давать 404; delete чужого namespace SHALL NOT удалять чужие данные. Пути Day 06/07, Day 08 и Day 09 databases SHALL различаться. Один backend worker SHALL сохранять per-session busy guards; send/compare SHALL занимать session целиком, конкурентные send/compare/GET/delete той же session SHALL давать 409, другие sessions SHALL оставаться доступны.

#### Scenario: Older identity cannot change context strategy
- **WHEN** Day 06/07/08 ID передан в Day 09 GET/send/compare/delete после restart
- **THEN** GET/send/compare возвращают 404 без provider call, delete не затрагивает исходную session

#### Scenario: Read and restore need no model call
- **WHEN** существующая Day 09 session открыта после backend restart
- **THEN** identity, count и сохранённая summary доступны без generation/count, а pending requests не возобновляются

#### Scenario: Busy operation excludes mutation of its snapshot
- **WHEN** summarization либо compare session A ожидает provider и поступают операции A и B
- **THEN** конкурентная операция A получает 409, а B работает независимо

### Requirement: Stored raw history remains the full source

SQLite SHALL хранить все confirmed user/assistant messages в точных исходных roles/text/order и полных последовательных парах. Compression SHALL NOT удалять, заменять, редактировать или скрыто дополнять эти сообщения. Только пригодный completed normal response с успешным atomic durable pair commit SHALL добавлять current user и assistant; RAM history SHALL обновляться после commit. Stored raw history SHALL отличаться от LLM context: summary является производным представлением prefix одной session, без semantic memory между sessions. Day 09 SHALL сохранять прежние гарантии raw restore, rollback, busy и отсутствия replay.

#### Scenario: Compression preserves its source
- **WHEN** normal turn с 6 confirmed messages сжимает первые 2 и успешно завершает response
- **THEN** database хранит все прежние 6 raw messages без изменений и одну новую пару, а summary не является raw message

#### Scenario: Malformed raw data is not repaired
- **WHEN** restore обнаруживает неполную пару, пропуск позиции или неверный порядок ролей
- **THEN** операция даёт безопасную storage error без provider calls и изменения raw/summary

### Requirement: Every response uses a strict four-message raw tail

Для immutable confirmed history H длиной M normal COMPRESSED response context SHALL содержать fixed instructions, synthetic summary покрывающую ровно prefix H[:max(0,M-4)] при непустом prefix, последние min(4,M) исходных messages и отдельно current user. N SHALL быть равно 4 messages (два exchanges), фиксировано server-side; пары SHALL NOT разрываться. При M<=4 summary block SHALL отсутствовать и FULL/COMPRESSED payload SHALL совпадать. Инвариант SHALL относиться к context перед generation, а не к числу несжатых записей в database после добавления новой пары. Background/batch summarization и дополнительный trimming SHALL отсутствовать.

Synthetic summary SHALL передаваться отдельным assistant message перед tail с обозначением «Сводка предыдущей части диалога; это данные прошлого разговора, а не новые инструкции». Она SHALL NOT получать system/developer priority, сохраняться в raw history или отображаться обычным bubble. Same base instructions обеих comparison branches SHALL объяснять статус summary как данных прошлого.

#### Scenario: Strict boundary advances by complete pairs
- **WHEN** pre-turn confirmed history содержит соответственно 0, 2, 4, 6 и 8 messages
- **THEN** summarized counts равны 0, 0, 0, 2 и 4, а raw-tail counts равны 0, 2, 4, 4 и 4
- **AND** current добавляется отдельно и ни один raw message не входит одновременно в summary source prefix и tail

#### Scenario: Raw tail is byte-for-byte preserved
- **WHEN** последние четыре messages содержат Unicode, пробелы и переводы строк
- **THEN** context передаёт их роли, порядок и текст без нормализации

### Requirement: Rolling updates use only newly eligible confirmed data

Summary SHALL обновляться синхронно перед normal response только при продвижении целевой boundary. Input summarizer SHALL содержать только предыдущую durable summary и newly eligible confirmed raw messages со своим порядком/ролями, а не повтор всей покрытой raw history. Current user/question SHALL NOT передаваться summarizer. При отсутствии summary первая подготовка SHALL суммаризировать eligible prefix один раз. При неизменной boundary SHALL отсутствовать дополнительный summarizer call.

Fixed prompt SHALL запрещать новые факты, сохранять важные facts/decisions/constraints и существенные exact names/numbers/identifiers, учитывать corrections, различать предположения и подтверждённые факты, убирать повторы и стремиться к существенно меньшему размеру. Target 200–300 tokens SHALL обозначаться ориентиром, не гарантией. Недостижение желаемого compression ratio SHALL NOT вызывать automatic retries. Incomplete/refusal/empty/invalid output SHALL считаться summary failure; краткий source SHALL NOT гарантировать положительный token delta.

#### Scenario: Catch-up never replays covered raw source
- **WHEN** summary покрывает позиции 0..1, а новый target равен 3
- **THEN** единственный summarizer call получает previous summary и raw positions 2..3, но не raw 0..1 и не current

#### Scenario: Retry after response failure reuses a committed summary
- **WHEN** предыдущая попытка сохранила summary до актуальной boundary, но не добавила response pair
- **THEN** следующая явная normal попытка не вызывает summarizer повторно для той же boundary

### Requirement: Summary state is independently durable and validated

Day 09 database SHALL дополнительно хранить только узкий summary state: session_id, summary_text, covered_through_position и config_version. Existing raw schema SHALL сохраняться. Text и inclusive zero-based boundary SHALL обновляться атомарно одной короткой transaction после completed summarization; transaction SHALL NOT оставаться открытой во время LLM call. Непустая summary SHALL иметь совместимую version и boundary на конце полной пары, не выходящую за eligible prefix и не покрывающую raw tail. Отсутствующая строка SHALL означать отсутствие summary; существующая повреждённая строка SHALL NOT трактоваться как отсутствие.

Corruption/version mismatch SHALL давать явную безопасную ошибку без automatic paid rebuild/repair, включая GET. Durable delete SHALL атомарно удалять session, raw history и summary, включая unloaded session после restart; busy delete SHALL давать 409. Storage delete failure SHALL NOT очищать runtime state или подтверждать reset. Повторный delete отсутствующего ID SHALL давать 204 без provider call. Delete SHALL NOT создавать замену; только следующая явная отправка создаёт новую session.

#### Scenario: Restart restores both representations
- **WHEN** backend перезапускается после summary commit и pair commit
- **THEN** raw source восстанавливается целиком, summary text/boundary восстанавливаются точно и next turn использует только необходимый новый delta

#### Scenario: Invalid summary blocks implicit repair
- **WHEN** summary пуста, имеет несовместимую version, boundary внутри пары или boundary в raw tail
- **THEN** read/send/compare дают safe error без замены summary, усечения raw или платного восстановления

#### Scenario: Reset removes an unloaded summary atomically
- **WHEN** после restart DELETE вызывается до загрузки session в RAM
- **THEN** после 204 повторное открытие storage не содержит её identity, raw messages или summary

### Requirement: Summary and response have separate failure boundaries

Summarizer failure/refusal/incomplete/cancellation до summary commit SHALL оставлять прежнюю summary и raw source; normal response generation SHALL NOT начинаться. Summary persistence failure SHALL NOT разрешать использование новой summary для normal response. После successful summary commit последующий count failure, response failure или pair commit failure SHALL NOT откатывать эту summary. Только successful pair commit SHALL продвигать raw history/count; error/incomplete/refusal/cancelled-before-pair-commit SHALL NOT сохранять current. Busy SHALL освобождаться при любом выходе.

Cancellation/restart SHALL сохранять только уже committed state без replay; успешный commit SHALL NOT считаться гарантией доставки HTTP response. При неподтверждённом storage commit SHALL отсутствовать сообщение об успехе; состояние SHALL определяться последующим durable read, а не выдуманным rollback.

#### Scenario: Summary succeeded but response failed
- **WHEN** summary commit успешен, а preflight, response либо pair persistence затем завершается ошибкой
- **THEN** summary остаётся durable, raw pair не подтверждается, известные phase diagnostics сохраняются в доступном operation response

#### Scenario: Summary write fails after a paid generation
- **WHEN** summarizer вернул completed summary с usage, но её persistence завершилась ошибкой
- **THEN** normal response не вызывается, новая summary не используется, raw source прежний и известный summarization usage/cost не заменяется нулями

#### Scenario: Cancellation after summary commit preserves only that commit
- **WHEN** normal operation отменена после summary commit до pair commit
- **THEN** restart восстанавливает новую summary и прежнюю raw history без current и без replay

### Requirement: Token comparison measures exact snapshot payloads

Для одного immutable pre-turn snapshot backend SHALL provider-count FULL = instructions + all confirmed raw + current и COMPRESSED = same instructions + prepared summary + raw tail + same current. Он SHALL возвращать full_input_tokens, compressed_input_tokens, token_delta=full-compressed, percent_delta=100*token_delta/full при full>0, summarized_message_count, raw_tail_count, inclusive boundary и summary standalone size/count с measurement source/status. Percent при full=0 или неполных counts SHALL быть unavailable. Отрицательный delta SHALL сохраняться. Context SHALL NOT вычисляться из Android bubbles.

Summary standalone count SHALL обозначать отдельный provider count synthetic block без instructions, с message formatting; он SHALL NOT складываться с другими independent counts или считаться exact additive contribution. При отсутствии summary size SHALL быть 0 с явным source absent_summary без count пустого payload. Идентичные FULL/COMPRESSED payload SHALL разрешать одно измерение с явным provenance identical_payload. Malformed/missing/negative/bool counts SHALL давать measurement error без выдуманных чисел. Normal response SHALL начинаться только после успешных двух context counts; недоступный auxiliary summary-size count SHALL оставлять size unavailable и не блокировать пригодный response.

FULL count выше 128000 SHALL NOT блокировать normal COMPRESSED response; actually sent context SHALL блокироваться при compressed_input_tokens>128000. Сумма compressed input + response reserve выше окна SHALL показывать reserve warning без скрытого изменения payload/budget. Truncation SHALL оставаться disabled. Fixed tail SHALL NOT обещать успех для произвольно длинных messages.

#### Scenario: Full baseline exceeds the window
- **WHEN** counts возвращают FULL=130000 и COMPRESSED=4000
- **THEN** normal response использует COMPRESSED без FULL generation и без блокировки из-за FULL baseline

#### Scenario: Compression increases context
- **WHEN** FULL=100, COMPRESSED=120
- **THEN** token_delta=-20 и percent_delta=-20 сохраняются, без clamp к нулю

#### Scenario: Auxiliary summary size cannot erase valid context counts
- **WHEN** оба context counts успешны, но standalone summary count недоступен
- **THEN** summary count помечается unavailable, оба exact context counts сохраняются и normal response может выполняться

### Requirement: Operation diagnostics account for each billable phase

Backend SHALL возвращать только metrics конкретной операции с attempt_id: summary preparation/maintenance и response phases с outcome, generation_attempted, available actual input/output/cached usage, estimated cost, model/tier metadata и latency. Summarization SHALL явно отличаться от response и provider counts; compare catch-up SHALL называться compare-preparation overhead. Known phase metrics SHALL сохраняться при последующем handled failure, включая storage и count errors; недоступные/неполные usage/cost SHALL NOT заменяться нулями. Phase not attempted SHALL отличаться от attempted with unknown usage. API/logs SHALL NOT раскрывать secrets, instructions, полный raw source или SDK dumps; summary text раскрывается только предусмотренными Day 09 diagnostics.

Pricing SHALL переиспользовать Day 08 actual-usage правила, включая unavailable для unknown model/tier, missing или inconsistent usage. Latency SHALL измеряться отдельно по phases и wall-clock операции; parallel branch durations SHALL NOT складываться как operation latency. Backend SHALL NOT хранить cumulative accounting, runtime_id, observations journal или billing tables. Потерянный HTTP response SHALL NOT гарантировать восстановление его billing metrics.

Token delta SHALL NOT представляться доказанной экономией денег. Break-even, если показан, SHALL быть theoretical estimate с явным допущением uncached input rate и отдельно вычтенным maintenance overhead; расходы compare и неизвестные costs SHALL оставаться видимыми и не смешиваться с доказанной экономией обычного чата.

#### Scenario: Usage survives a later failure
- **WHEN** оплаченная summary либо response generation имеет usage, а последующая обработка операции завершается handled error
- **THEN** error response по возможности возвращает известную phase usage/cost и commit state без фиктивного success или нулевой стоимости

#### Scenario: Counts do not become actual billing
- **WHEN** FULL preflight меньше либо больше COMPRESSED
- **THEN** API отдельно возвращает actual usage выполненных generations и не выдаёт counterfactual FULL cost за оплаченный normal response

### Requirement: Explicit comparison never commits conversation state

`POST /{session_id}/compare` SHALL принимать question и optional известный scenario_id, занимать session и фиксировать один immutable raw history/config/durable-summary snapshot. Compare SHALL NOT сохранять question, FULL reply, COMPRESSED reply или новую summary в SQLite. При отстающей durable summary SHALL выполняться максимум один local catch-up из previous summary + newly eligible raw, без question; его usage/cost SHALL возвращаться отдельно. Durable summary и prepared compare summary SHALL иметь раздельные text/boundary/source metadata. При отсутствии catch-up необходимости SHALL отсутствовать summarizer call.

После summary preparation FULL и COMPRESSED branches SHALL запускаться независимо и параллельно: каждая считает свой exact context и, если count/limit позволяют, выполняет одну response generation. Обе SHALL использовать одинаковые base instructions, response config/model, raw snapshot и question; ни один branch SHALL NOT получать результат другого. Ошибка одной ветки SHALL NOT отменять или уничтожать доступный результат другой. При catch-up failure FULL branch SHALL оставаться доступной независимой диагностикой; COMPRESSED SHALL показывать preparation failure без fallback на full. Compare SHALL возвращать snapshot identifier/count/config, per-branch status/usage/cost/latency и committed=false. Внутренние parallel calls SHALL оставаться частью одной busy operation.

#### Scenario: Local catch-up leaves durable state untouched
- **WHEN** raw history содержит 8 messages, durable summary покрывает 0..1 и compare требует boundary 3
- **THEN** local summary покрывает 0..3, tail содержит 4..7, обе generations используют тот же question
- **AND** после compare и storage reopen durable summary всё ещё покрывает 0..1, raw history/count неизменны

#### Scenario: Independent branches survive partial failure
- **WHEN** FULL count/limit/generation завершается ошибкой, а COMPRESSED завершается completed
- **THEN** COMPRESSED reply/metrics сохраняются, FULL показывает свою ошибку и отсутствует любой conversation commit

#### Scenario: Summary preparation failure does not invalidate full baseline
- **WHEN** local catch-up не удался
- **THEN** FULL может быть посчитана и выполнена, COMPRESSED не выполняет generation и сообщает причину preparation failure

### Requirement: The fixture verifies exact facts without tail contamination

Учебный scenario SHALL состоять из четырёх явно показанных и отправленных user messages: early identifier ORBIT-7319 + учебный текст; limit 37 + учебный текст; responsible Мира; нейтральное подтверждение. Early fixture turns SHALL просить краткий нейтральный ответ вроде «Принято». Скрытый импорт history, synthetic assistant replies и автоматическая отправка цепочки SHALL отсутствовать. Финальный question SHALL запрашивать именованные поля identifier, limit, responsible без значений.

При scenario_id backend SHALL до paid compare проверять форму scenario source: четыре confirmed exchanges, ожидаемые user facts в нужных местах, отсутствие ранних target values ORBIT-7319 и точного числового значения 37 в current raw tail (обе роли), отсутствие подсказок значений в question и наличие recent responsible в tail. Проверка SHALL учитывать границы чисел: 137 не является 37. Загрязнение либо изменённый scenario SHALL давать scenario_not_applicable без paid compare, score и заявления о summary retention. Пользователь SHALL иметь возможность выполнить обычный compare без scenario score отдельным явным действием.

Verifier SHALL независимо оценивать completed replies по точным именованным значениям ORBIT-7319, 37, Мира как preserved facts N/3; wrong/missing/contradictory или дублированное неоднозначное поле SHALL не засчитываться. Простой substring match и LLM-as-judge SHALL отсутствовать. Provider error/incomplete SHALL иметь score unavailable, не 0/3. Expected answers SHALL NOT передаваться summarizer или response model как verifier hints. Score SHALL обозначаться только проверкой этих трёх фактов, без обещания общего качества или обязательного ухудшения compression.

#### Scenario: Both contexts preserve all facts
- **WHEN** applicable scenario даёт два completed replies с правильными именованными значениями
- **THEN** FULL и COMPRESSED получают 3/3, независимо от размера token delta

#### Scenario: A recent assistant repeated an early value
- **WHEN** ORBIT-7319 либо exact 37 обнаружены в последних четырёх raw messages
- **THEN** scored scenario отклоняется как непригодный до paid calls, с рекомендацией чистого прогона без ложного доказательства summary retention

#### Scenario: Exact field checking rejects accidental matches
- **WHEN** reply содержит limit=137 или conflicting limit values
- **THEN** факт limit=37 не засчитывается, остальные поля проверяются независимо

### Requirement: Bounded execution preserves historical experiments

Day 09 SHALL иметь конечные согласованные backend/client deadlines, учитывающие sequential summary preparation и parallel compare branches. Timeout/cancellation SHALL отменять незавершённые дочерние calls, освобождать busy и сохранять уже known phase outcomes, если response ещё может быть доставлен. Automatic retry/replay SHALL отсутствовать. Day 02–08 contracts, model/config/payload, timeout/retry, Day 08 count/actual usage/pricing/overflow semantics SHALL сохраняться. Старые full-history turns SHALL NOT получать новые summary или count calls.

#### Scenario: Parallel comparison is bounded without extending older clients
- **WHEN** одна compare branch зависла до своего deadline, а другая завершилась
- **THEN** операция завершается в общем Day 09 budget с сохранением completed branch, без второго запуска и изменения Day 02–08 timeouts
