# context-strategies-experiment Specification

## Purpose

Определяет независимые эксперименты Sliding Window, structured Facts и Branching на общем сценарии сбора ТЗ, с проверяемыми границами context, durable state и честными side-effect-free evaluation metrics без summary/compression.

## Requirements

### Requirement: Runs have immutable strategy and configuration identity

Day 10 SHALL создавать независимые runs `window | facts | branches` с immutable run_id, strategy, config_version и scenario_version. Все reads/writes SHALL разрешаться только в соответствующем strategy/config namespace, включая restart; global fallback lookup, strategy migration и подмена отсутствующего run новым SHALL отсутствовать. Create SHALL durable сохранять пустую identity до ответа без provider calls. Несовместимая конфигурация, повреждённый state и отсутствующий run SHALL различаться явными ошибками без автоматического repair. Day 06–09 storage SHALL оставаться отдельным и не мигрироваться.

#### Scenario: Wrong strategy cannot open a saved run
- **WHEN** ID Facts используется через Window route до или после restart
- **THEN** backend отклоняет обращение без возврата чужого state, создания run или provider call

#### Scenario: Configuration mismatch is explicit
- **WHEN** запрос или сохранённый run имеет несовместимую config/scenario version
- **THEN** backend возвращает явную incompatibility error без migration и fallback

### Requirement: Configuration v3 preserves historical v1 and v2 evidence

Целевая immutable identity SHALL быть `day10-gpt4o-mini-n6-v3` для Window/Facts/Branching. Facts extraction schema SHALL быть `facts-v2`, с semantic set/cleared вместо LLM-selected op. Scenario meeting-rooms-v1, evaluation schema meeting-spec-v1, gpt-4o-mini, N=6, durable FactState format, Sliding/Branching/evaluation semantics, quality/retention/accounting и exact fixtures SHALL сохраняться. Response/evaluation settings SHALL оставаться прежними кроме общей config metadata.

V3 store SHALL находиться в `.local/context-strategies/day10-gpt4o-mini-n6-v3/experiments.sqlite3`. V1/v2 namespaces/databases/runs/results SHALL сохраняться historical evidence без migration/delete/import/repair. Lookup/cache/reset SHALL соблюдать version identity в обоих направлениях без global fallback или silent recreation. Fresh v3 runs SHALL создаваться только перед explicit Send.

#### Scenario: Historical failed runs cannot become v3 state
- **WHEN** v3 запускается при Facts v1 на 3/8 и Facts v2 на 7/8 или получает их IDs
- **THEN** оба historical stores/runs остаются неизменными, чужой state не открывается и provider/recovery operations отсутствуют

#### Scenario: V3 reset preserves previous configurations
- **WHEN** v3 run сбрасывается либо store повторно открывается
- **THEN** v1/v2 bytes/results сохраняются, cross-version reads/writes не используют fallback

### Requirement: Confirmed turns preserve exact raw input and atomic pairs

Обычный Send SHALL принимать точный current user text и explicit target stream; Android SHALL NOT передавать history, facts, model, instructions или expected answers. Только completed пригодный response SHALL атомарно сохранять user/assistant pair, confirmed scenario step и revision; runtime success SHALL публиковаться после durable commit. Failure/refusal/incomplete/cancellation до commit SHALL сохранять прежнюю conversation. SDK/application automatic retries и hidden replay SHALL отсутствовать. Guard SHALL блокировать несовместимые операции записи; busy SHALL NOT переживать restart. Transaction SHALL NOT удерживаться во время provider await.

#### Scenario: Failed response does not leave half a turn
- **WHEN** обычный response не завершён либо запись пары не подтверждена
- **THEN** после reopen нет новой user/assistant пары или продвижения scenario step, а успешный turn не объявляется

#### Scenario: Unknown transport outcome is reconciled
- **WHEN** HTTP ответ на Send потерян после возможного commit
- **THEN** read-only чтение run возвращает confirmed steps/revision, позволяя отличить committed step от отсутствующего без повторной генерации

### Requirement: Sliding uses exactly the last six confirmed messages

Window response context SHALL содержать fixed instructions, последние min(6, confirmed message count) raw messages в исходном порядке и current user сверх N. N SHALL оставаться равным 6 messages, то есть трём complete exchanges. Полный raw audit transcript SHALL сохраняться отдельно от выбора active context. Старые messages SHALL NOT попадать в generation, extraction, summary, token-count audit requests или fallback. Sliding maintenance generation SHALL равняться нулю. N SHALL NOT представляться фиксированным token budget.

#### Scenario: Window boundary and roles are exact
- **WHEN** подтверждены четыре пары U1/A1 ... U4/A4 и приходит U5
- **THEN** provider input содержит ровно U2,A2,U3,A3,U4,A4,U5 после fixed instructions, без U1/A1

#### Scenario: Short history and audit restore
- **WHEN** run с 0, 2, 4 или 6 confirmed messages восстанавливается и принимает user message
- **THEN** передаётся вся доступная history до N плюс current user; сохранённые audit messages сверх N не используются даже при неизвестном модели ответе

### Requirement: Facts are scoped typed conversation data

Facts run SHALL хранить structured records с identity `(scope,key)`, scope `shared | A | B`, kind `goal | constraint | preference | decision | agreement | other`, typed scalar value, state `set | cleared` и provenance/evidence пользовательского источника. A/B facts SHALL сосуществовать без взаимного затирания; Facts conversation SHALL оставаться линейной. Cleared SHALL обозначать явную отмену, не ноль или пустую строку; отменённые записи SHALL сохранять возможность отличить отмену от отсутствия сведения. Facts SHALL относиться только к текущему run, без semantic memory между sessions. Prose summaries SHALL отсутствовать.

#### Scenario: Two alternative values coexist
- **WHEN** пользователь явно задаёт A.payment=on_site и B.payment=link, не отменяя A
- **THEN** state содержит оба scoped значения; B не заменяет A и не создаёт branch history

#### Scenario: A requirement is cleared
- **WHEN** пользователь отменяет ранее включённые email reminders
- **THEN** соответствующая запись помечается cleared с подтверждённым user provenance и не считается active fact

### Requirement: V3 extractor returns semantic facts from exact current user

Каждый ordinary Facts v3 Send SHALL выполнять одну extraction fixed gpt-4o-mini strict Structured Output facts-v2. Input SHALL быть ровно один user message JSON `{current_user: exact current text}`. Current assertions scenario self-contained; previous FactState SHALL использовать только backend reducer, не LLM. Raw history, assistant replies, evaluation outputs и expected answers SHALL NOT передаваться extractor.

Output SHALL иметь root changes array и strict required change fields scope/key/kind/state/value/evidence, additionalProperties=false на root/change. Scope shared/A/B и kind enum прежние; state SHALL быть set|cleared; value strict string|integer|boolean|null. Set SHALL иметь non-null value, cleared SHALL иметь null и подтверждаться exact current key=cleared. Op/add/replace SHALL отсутствовать в output schema. Scope/key/value/evidence SHALL происходить из одной current assertion; no duplicate identities. Exact prompt SHALL соответствовать design и не поручать LLM решение о существовании identity.

#### Scenario: Operation output is incompatible with v3
- **WHEN** extractor возвращает старый v2 объект с op=replace или op=add
- **THEN** facts-v2 schema validation отклоняет extra op как extraction_invalid_output; backend не конвертирует его в semantic change и не retry-ит

#### Scenario: Input excludes previous storage state
- **WHEN** Facts v3 извлекает данные Turn 8
- **THEN** provider input содержит только exact current_user и fixed instructions/schema, без previous facts, raw prefix, A replies или evaluation outputs

### Requirement: Semantic validation precedes every deterministic transition

Backend SHALL проверить весь semantic patch до reducer: JSON/schema, current identity/scope/key, exact full assertion-line evidence той же identity, strict type/value equality, state/value consistency и отсутствие duplicates. Assertion/evidence/type/value checks SHALL NOT ослабляться. Invalid semantic change SHALL отвергать весь patch до count/response без partial save, automatic retries или backend correction из canonical expected table. Public extraction_unsupported_change и internal assertion_not_found/evidence_mismatch/type_mismatch/value_mismatch/duplicate_identity SHALL сохранять смысл. Invalid state/value SHALL возвращать extraction_invalid_state / invalid_state, HTTP 422.

#### Scenario: Wrong extracted value is not repaired
- **WHEN** current содержит payment=link, но semantic change содержит B.payment=cash
- **THEN** validator возвращает value_mismatch до reducer, не заменяет cash на link и не сохраняет соседние valid changes

#### Scenario: Borrowed evidence and duplicate identity reject the entire patch
- **WHEN** evidence относится к другому current key либо patch повторяет identity, даже с одинаковым value
- **THEN** весь candidate отклоняется; schema conformance не считается semantic correctness

### Requirement: Backend derives scoped state transitions deterministically

После успешной semantic validation backend SHALL применять changes к candidate copy реального previous FactState. Для set: absent/cleared identity -> ADD/set; active с другим strict typed value -> REPLACE/update; active с тем же type/value -> NO-OP. Для cleared: active -> CLEAR/tombstone; already cleared -> NO-OP; never existing -> reject entire patch extraction_clear_missing / clear_missing, HTTP 422. Наличие A identity SHALL NOT влиять на B identity. Storage operations SHALL NOT требоваться от LLM или сохраняться как новая часть FactState/public results.

ADD/REPLACE/CLEAR SHALL брать value/kind/evidence из validated change и current user provenance от backend. NO-OP SHALL сохранять всю прежнюю запись, включая kind/evidence/user_id; отличие kind при одинаковом typed value не делает REPLACE. Ordinary successful no-op/empty-patch Send SHALL всё равно сохранять conversation pair/step/revision по прежнему lifecycle. Omissions SHALL оставаться реальными omissions: reducer не достраивает отсутствующие changes из current fixture или expected values.

#### Scenario: New branch B fact is added independently of A
- **WHEN** previous содержит A.payment, B.payment отсутствует и validated B.payment имеет state=set/value=link
- **THEN** reducer добавляет B.payment, не меняет A.payment и не требует LLM add/replace

#### Scenario: Existing value updates or remains unchanged
- **WHEN** validated set адресует active identity
- **THEN** different strict typed value заменяет её с current provenance, identical type/value сохраняет прежнюю запись целиком

#### Scenario: Clear transitions remain strict
- **WHEN** приходит validated cleared semantic change
- **THEN** active identity становится tombstone, already-cleared остаётся прежней, never-existing вызывает clear_missing и отмену всего candidate без response

#### Scenario: Candidate transitions are not a partial durable save
- **WHEN** после допустимого candidate ADD обнаружен never-existing clear либо subsequent response/storage failure
- **THEN** ни earlier ADD, ни новая пара, step или revision не публикуются и не становятся durable

### Requirement: Candidate facts commit with their conversation pair

Facts SHALL извлекать semantic changes, валидировать весь patch и детерминированно применять его к candidate FactState, строить response context из candidate facts + последних шести confirmed raw messages + current user, а после completed response сохранять user, assistant, resulting facts, scenario step и revision одной durable transaction. До commit candidate SHALL NOT публиковаться как confirmed. Response failure SHALL откатывать candidate вместе с несохранённой парой; storage failure SHALL сохранять прежний согласованный state. Известный extraction usage SHALL учитываться даже при последующем response/storage failure.

#### Scenario: Successful extraction followed by failed response
- **WHEN** extraction корректно меняет deadline на 6, но response получает timeout
- **THEN** после restart deadline и history остаются прежними; extraction usage присутствует в receipt попытки, response не выдаётся за completed

#### Scenario: Atomic persistence survives reopen
- **WHEN** запись resulting facts или пары падает до подтверждённого COMMIT
- **THEN** reopen не обнаруживает новую пару без её facts или новые facts без соответствующей пары

### Requirement: Facts context never elevates user data to instructions

Response context Facts SHALL содержать явно маркированный structured facts block ниже system/developer priority, затем exact fixed raw tail и current user. Значения facts SHALL NOT интерполироваться в system/developer instructions. Block SHALL сохранять scopes, corrections и cleared state; provenance/evidence SHALL NOT использоваться как дополнительная raw-history memory. Производный block SHALL NOT становиться synthetic confirmed message. Audit history SHALL NOT подмешиваться при ошибках или пропущенных facts.

#### Scenario: Facts include a user-supplied instruction-like value
- **WHEN** значение факта похоже на управляющую инструкцию
- **THEN** оно остаётся данными внутри маркированного блока обычного приоритета, без изменения fixed instructions

### Requirement: Branching has one frozen prefix and exactly two children

Branching SHALL иметь root с complete pairs, один explicit checkpoint на pair boundary и ровно A/B local histories. В controlled scenario checkpoint SHALL создаваться только после confirmed Turn 6; root после checkpoint SHALL быть frozen. Prefix SHALL храниться физически один раз. Context A SHALL быть prefix до checkpoint + local A + current A user; context B SHALL быть prefix + local B + current B user. Третьи/nested branches, arbitrary parent, merge и rebase SHALL отклоняться. Checkpoint SHALL создавать A/B атомарно без provider calls; повторное обращение к существующему checkpoint SHALL NOT создавать новый checkpoint или другие children.

#### Scenario: Checkpoint creates durable siblings
- **WHEN** после шести confirmed root turns пользователь создаёт checkpoint и backend перезапускается
- **THEN** доступны тот же prefix из 12 messages, один checkpoint и ровно A/B с пустыми local histories без копий prefix

#### Scenario: Branch source and write target are isolated
- **WHEN** Turn 7 отправлен в A, а Turn 8 — в B
- **THEN** A source не содержит Turn 8 или его assistant; B source не содержит Turn 7 или его assistant; каждая новая пара записана только в target branch

#### Scenario: Invalid topology or root continuation is rejected
- **WHEN** после checkpoint запрошен root Send, третий child, nested branch или новая boundary
- **THEN** запрос отклоняется без записи и provider calls

### Requirement: Branch control and reset have no provider cost

Branch selection SHALL быть UI preference с explicit branch target в каждом Send; switching SHALL NOT менять histories, facts или вызывать provider. Topology SHALL переживать restart независимо от UI cursor. Один run guard SHALL исключать competing writes, checkpoint/reset во время активной операции; independent A/B evaluations одного immutable snapshot SHALL допускаться без conversation writes. Reset SHALL удалять весь run с prefix/checkpoint/обеими branches/evaluation outputs, без отдельного branch delete. Состояние других strategy runs SHALL оставаться прежним.

#### Scenario: Busy reset and branch switching
- **WHEN** run выполняет Send или evaluation, а пользователь пытается reset/checkpoint/другую несовместимую запись
- **THEN** backend возвращает busy; UI switch сам по себе не вызывает модель и не перенаправляет результат выполняющегося запроса в другую ветку

#### Scenario: Reset removes the whole experiment
- **WHEN** reset подтверждён и backend перезапущен
- **THEN** старый run и обе ветки недоступны, другие runs сохранены и replay отсутствует

### Requirement: The controlled scenario consists of eight exact user messages

Scenario `meeting-rooms-v1` SHALL состоять ровно из восьми committed user turns ниже. Каждый блок SHALL отправляться как его полный UTF-8 текст с LF между строками, без внешних code fences и без завершающего LF. Последняя строка ACK входит в каждый fixture. Fixtures и их raw contents SHALL быть одинаковыми для всех strategies; shared scope применяется к turns 1–6. Они SHALL проходить обычный Agent flow, без synthetic import или fake assistant. В controlled run шаги SHALL подтверждаться по порядку и только после completed pair; изменённый/добавленный user text SHALL делать benchmark неприменимым, а не автоматически исправляться.

Turn 1:
```text
Собираем ТЗ продукта. Область требований: shared.
goal=бронирование переговорных
platform=Android
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 2:
```text
Область требований: shared. Первоначальные параметры пилота:
deadline_weeks=8
pilot_users=37
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 3:
```text
Область требований: shared. Нужен offline просмотр ранее загруженного расписания; банковские карты не храним.
offline_schedule=true
stores_card_data=false
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 4:
```text
Область требований: shared. Предпочитаем спокойный интерфейс и пока включаем email-напоминания.
style=спокойный
email_reminders=true
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 5:
```text
Область требований: shared. Исправляю срок с 8 на 6 недель; принимаем вход по magic link.
deadline_weeks=6
auth=magic_link
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 6:
```text
Область требований: shared. Договорились, что ТЗ согласует Мира. Ранее включённые email-напоминания отменяю.
approver=Мира
email_reminders=cleared
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 7:
```text
Область требований: A. Это отдельная альтернатива продукта с общими требованиями shared.
payment=on_site
confirmation=immediate
Оплата на месте, бронирование подтверждается сразу.
Ответь только: Принято. Не повторяй требования из диалога.
```

Turn 8:
```text
Область требований: B. Это отдельная альтернатива продукта с общими требованиями shared. Альтернативу A не отменяем и не изменяем.
payment=link
confirmation=admin
Оплата по ссылке, бронирование подтверждает администратор.
Ответь только: Принято. Не повторяй требования из диалога.
```

Window/Facts SHALL получать эти восемь messages линейно. Branching SHALL получать 1–6 в root, explicit checkpoint, 7 в A и 8 в B. ACK SHALL быть настоящим ответом модели, не backend substitution; raw assistant restatements SHALL сохраняться и учитываться при проверке доступного context.

#### Scenario: All strategies receive the same scenario information
- **WHEN** три controlled runs завершили сценарий
- **THEN** в каждом ровно восемь confirmed user texts, побайтно равных fixtures, с соответствующими настоящими assistant responses; отличается только target routing Branching

#### Scenario: Edited fixture invalidates the benchmark
- **WHEN** отправлен изменённый fixture, неверный step order или свободное сообщение
- **THEN** backend не подставляет canonical text или ожидаемую history и не показывает controlled N/11 как применимое к этому run

### Requirement: Explicit final evaluations use immutable strategy snapshots

После восьми confirmed scenario turns пользователь SHALL явно авторизовать evaluation A и evaluation B отдельными действиями. Они SHALL использовать один immutable final snapshot на одну run revision/config/scenario: Window/Facts имеют одинаковый base context и отличаются только requested variant; Branching использует соответствующие prefix+local sources того же root/checkpoint snapshot. Evaluations SHALL быть независимыми и допускать одновременное выполнение A/B, если пользователь явно запустил обе. Completion одного SHALL NOT дополнять input другого. Каждая evaluation SHALL выполнять не более одного response generation, без extraction/summary и без retries.

Evaluation user question SHALL быть: `Сформируй ТЗ варианта A по доступным данным shared и этого варианта. Верни объект заданной схемы; неизвестные значения заполни null. Не переноси требования другой альтернативы.` Для B SHALL изменяться только символ варианта после слова «варианта» в первом предложении. Ни schema, ни question SHALL не содержать expected values.

#### Scenario: A and B do not contaminate each other
- **WHEN** A завершается перед B, B перед A либо обе выполняются параллельно
- **THEN** для каждого варианта assembled provider payload соответствует одному и тому же зафиксированному source snapshot и не содержит question/reply другой evaluation

#### Scenario: Evaluations leave all strategy state unchanged
- **WHEN** любая evaluation завершается, падает или отменяется
- **THEN** conversation pairs, facts, checkpoint, branch local counts, scenario progress и strategy revision остаются прежними

#### Scenario: Evaluation readiness is checked before provider calls
- **WHEN** запрошена evaluation неполного, несовместимого или изменённого controlled run
- **THEN** backend возвращает not-applicable/not-ready error без generation/extraction/count и без изменения history

### Requirement: Evaluation outputs persist separately from conversation sources

Completed/failed evaluation outcomes и retention observations SHALL сохраняться как отдельный experiment output с snapshot identity, requested variant и source revision для dashboard/restore. Questions/replies SHALL NOT попадать в raw conversation, FactState, extractor или будущий provider input. Чтение outputs/dashboard SHALL быть read-only и не требовать OpenAI. Output persistence failure SHALL быть явно обозначена, без объявления durable result; conversation SHALL оставаться неизменной. Повторная evaluation SHALL требовать нового явного действия; read после transport uncertainty SHALL не выполнять generation. Reset SHALL удалять outputs вместе с run.

#### Scenario: Dashboard survives restart without replay
- **WHEN** completed evaluation output сохранён и процессы перезапущены
- **THEN** UI получает те же results/quality/retention по read-only запросу; ни ответ A, ни ответ B не включается в conversation context

### Requirement: Final specification quality checks eleven typed fields

Final evaluation SHALL использовать fixed `gpt-4o-mini` и одинаковую strict Structured Output schema из ровно одиннадцати nullable полей: goal, platform, deadline_weeks, pilot_users, offline_schedule, stores_card_data, style, auth, approver, payment, confirmation. Schema SHALL задавать только names/types, без expected-value enums, defaults или ответов в descriptions. Verifier SHALL проверять exact typed values и requested scope. Expected shared values SHALL быть `бронирование переговорных`, `Android`, integer 6, integer 37, boolean true, boolean false, `спокойный`, `magic_link`, `Мира` соответственно; A SHALL требовать `on_site`/`immediate`, B — `link`/`admin`. Expected values SHALL существовать только в verifier, не передаваться provider как reference answers. Email reminders SHALL не входить в denominator 11.

Quality SHALL отображаться отдельно `ТЗ A N/11`, `ТЗ B M/11` и означать correct required fields, не общее качество модели. Typed decoding SHALL не зависеть от whitespace/key order/prose punctuation. Duplicate keys/conflicts SHALL не разрешаться last-wins parser. Missing/invalid types/schema/refusal/incomplete SHALL давать score unavailable; valid null SHALL считаться отсутствующим значением и не засчитываться как 0 или false. Valid schema с неверными значениями SHALL иметь соответствующий score, включая допустимый 0/11. Wrong variant values SHALL не засчитываться.

#### Scenario: Numeric and nullable values are distinct
- **WHEN** valid evaluation содержит pilot_users=137, deadline_weeks=null или payment другой альтернативы
- **THEN** эти поля не засчитываются; integer 37 сравнивается целиком, null не приводится к нулю

#### Scenario: Invalid output is not a zero-quality document
- **WHEN** response refused/incomplete или JSON имеет duplicate keys, отсутствующие fields либо неверные types
- **THEN** evaluation показывает unavailable score и причину, а не 0/11; state не commit-ится

### Requirement: Retention measures available context before final generation

Перед каждым final generation backend SHALL вычислять `available relevant critical facts / 11` по фактически assembled active sources, включая доступные assistant restatements, scopes, corrections и cleared values. Window SHALL проверять только last 6 confirmed messages; Facts — resulting structured state + last 6; Branch A/B — prefix+соответствующий local source. Expected set SHALL использоваться только verifier и не расширять model context. Исторический факт отправки fixture SHALL сам по себе не доказывать доступность значения. Последующее исправление одного scoped key SHALL отменять прежнее значение; unresolved conflicts SHALL не засчитываться как однозначно available. Retention SHALL фиксироваться на pre-generation snapshot и не выводиться из final quality или более позднего state.

Deterministic retention SHALL применять задокументированную closed grammar к named raw assertions и structured state, не LLM-as-judge. Если assistant restatement или free-form content нельзя однозначно проверить этой grammar, retention SHALL быть unavailable с diagnostic reason вместо ложного точного score. Exact recognized restatements SHALL учитываться, а не автоматически объявляться contamination.

#### Scenario: Audit facts outside the window are not available
- **WHEN** critical fact находится только в out-of-window raw audit messages
- **THEN** retention Window его не засчитывает, даже если полный audit доступен verifier для expected-scenario validation

#### Scenario: Correction and an assistant restatement affect retention
- **WHEN** selected sources содержат deadline_weeks=8, последующее user correction=6 или распознаваемое assistant повторение актуального значения
- **THEN** verifier учитывает chronology/provenance и реальную доступность актуального значения; он не считает любую встречу 8 и 6 автоматически равнозначной

### Requirement: Branch leakage is checked independently of answer quality

Для Branching backend SHALL детерминированно проверять `opposite-branch message IDs ∩ selected context source IDs = ∅`, отдельно от retention и quality. Dashboard SHALL показывать «Изоляция веток: выполнено / нарушено». Opposite-branch source SHALL NOT отправляться provider; обнаруженное нарушение перед generation SHALL останавливать этот запрос и показывать нарушенный invariant. Ошибка модели в variant value без чужого source SHALL считаться quality error, не доказанным storage leakage.

#### Scenario: Foreign source is detected before generation
- **WHEN** в assembled source A обнаружен ID message ветки B
- **THEN** evaluation A не вызывает provider и сообщает нарушенную изоляцию; B history не изменяется

### Requirement: Token totals separate response maintenance and unknown usage

Day 10 SHALL использовать actual provider usage для response input/output всех ordinary и final evaluation calls и maintenance input/output всех attempted Facts extraction calls. Window/Branching maintenance SHALL равняться 0; checkpoint/switch SHALL не иметь provider token cost. Branch calls SHALL входить в response category ровно один раз. Runtime receipts SHALL deduplicate attempts по attempt ID и фазе; repeated read SHALL не прибавлять расход. Failed attempts SHALL сохранять известный usage и явную unknown coverage. Preflight SHALL не выдаваться за actual generation usage. Total/cached/reasoning counters SHALL не суммироваться повторно с уже включающими их counters.

Dashboard SHALL показывать total known tokens и полноту known input/output coverage. Unknown SHALL NOT превращаться в zero; missing total и частично известные components SHALL не приводить к двойному счёту или выдуманному полному total. Persistent billing journal/USD dashboard SHALL отсутствовать. После утраты runtime observations полный расход restored run SHALL быть явно недоступен/неполон без reconstruction/replay. Evaluation outputs SHALL не служить источником восстановленного полного billing total.

#### Scenario: Extraction cost remains after response failure
- **WHEN** extraction вернула usage, а subsequent response usage неизвестен
- **THEN** total включает известный extraction расход и сообщает неизвестную response coverage, не объявляя эту попытку бесплатной

#### Scenario: Final evaluations are responses without memory maintenance
- **WHEN** все 8 ordinary turns и обе evaluations выполнены без failures/retries
- **THEN** Window/Branching имеют по 10 response generations, Facts — 10 response и 8 extraction generations; evaluation не добавляет extraction или conversation pairs

### Requirement: Convenience and live evidence do not invent benchmark scores

Comparison SHALL разделять восемь обычных Sends и две evaluation actions от strategy-management actions. Window/Facts SHALL иметь ноль обязательных memory-management actions; Branching SHALL показывать один checkpoint и фактическое число branch switches. Optional inspector/disclosure, navigation и recovery SHALL не выдаваться за обязательное memory management. Subjective numeric UX score SHALL отсутствовать. Live results SHALL записываться отдельно от offline/fake tests без заранее выбранного победителя или вымышленных actual tokens. Если local action observations потеряны, unknown count SHALL не подменяться нулём.

#### Scenario: Optional inspection does not penalize Facts
- **WHEN** пользователь открывает facts inspector несколько раз
- **THEN** mandatory management count Facts остаётся 0; optional diagnostics при отображении имеют отдельную категорию

#### Scenario: A single live run has bounded conclusions
- **WHEN** один controlled run каждой strategy завершён
- **THEN** отчёт показывает actual quality/retention/tokens/actions этого запуска и объясняет применимость стратегий, не объявляя универсальную победу

### Requirement: Final live comparison uses only fresh v3 runs

Final controlled comparison SHALL использовать чистые Window v3, Facts v3 и Branching v3 runs meeting-rooms-v1. Facts v1/v2 failures и historical Window success SHALL сохраняться отдельно без исправления и не импортироваться в final v3 dashboard/usage/actions. Live v3 SHALL выполняться только после implementation и отдельного explicit manual authorization; update/apply SHALL NOT запускать provider calls, v2 retries или migration. Fake tests SHALL доказывать schema/reducer/atomicity contracts, не обещать реальную correctness semantic extraction или победителя.

#### Scenario: Historical results cannot fill missing v3 metrics
- **WHEN** есть v1/v2 outputs, но соответствующий v3 run/evaluation ещё не выполнен
- **THEN** v3 comparison показывает unavailable без импорта старых результатов и без автоматического provider call
