## Purpose

Обеспечить воспроизводимый выбор практически полезной локальной конфигурации существующего Android Architecture Assistant по смысловой корректности Kotlin/Compose, применению Markdown-правил, надёжности, задержке и памяти с отдельным подтверждением на целевом Mac.

## ADDED Requirements

### Requirement: Experimental compact contract preserves provenance

Отдельный opt-in compact-evidence-v1 SHALL существовать только в synthetic driver. Он SHALL содержать объяснения Kotlin с lines и documentary objects с отдельными rule/application text, Kotlin lines и exact Markdown citations. Python SHALL назначать номера вывода и knowledge status; модель SHALL NOT генерировать перекрёстные observation/rule IDs или status. Пустые documentary applications SHALL быть допустимы при отсутствии применимых правил. Default Day 27–29, RAG/SQLite/Workspace и транспорт SHALL оставаться неизменными.

#### Scenario: Contract identity and isolated format adaptation
- **WHEN** выбран compact-evidence-v1
- **THEN** применяются отдельные pinned schema/prompt hashes с parent frozen manifest; system instruction адаптируется из baseline только по формату, без explain-evidence-v1 или эталонных ответов
- **AND** совместное изменение schema/instructions явно отмечается отдельным контрактом, а не чистой абляцией одного параметра

#### Scenario: Strict local evidence validation
- **WHEN** ответ содержит неверный тип/диапазон/дубликат Kotlin-строки, неизвестный chunk, не буквальную/слишком длинную/повторную цитату, лишнее поле либо не завершён done/stop
- **THEN** ответ отклоняется без repair/retry; renderer не подбирает источники и берёт пути/разделы только из проверенных selected chunks

#### Scenario: Empty documentary applications
- **WHEN** применимых правил нет при любом runtime knowledge status
- **THEN** пустой documented_applications с непустыми limitations принимается, а наличие candidates не трактуется как подтверждение смысла

#### Scenario: Offline checkpoint precedes compact live
- **WHEN** offline-реализация и tests завершены
- **THEN** работа останавливается для user review без inference; потенциальные S4→S6 выполняются только после отдельного разрешения, с прежними техническими gates и отдельным журналом

### Requirement: Existing assistant and historical evidence are preserved

Оптимизация SHALL развивать существующую утилиту, сохраняя legacy invocation, прежние extended defaults, границы Workspace/Knowledge и механическую проверку источников. Новый профиль SHALL включаться явно. Исторические результаты Day 27–28 SHALL оставаться неизменными, Day 28 SHALL оставаться активным с открытыми проверками. Генератор SHALL NOT автоматически скачивать модели, менять конфигурацию сервера, выполнять команды из входов/ответов или подменять технический отказ другим retrieval/runtime.

#### Scenario: Existing invocation without optimization options
- **WHEN** пользователь запускает прежнюю команду без новых опций
- **THEN** прежние defaults, prompt/schema и правила проверки сохраняются; новая конфигурация не применяется молча

#### Scenario: New experiment does not repair history
- **WHEN** Day 29 получает успешный или неуспешный результат
- **THEN** он записывается отдельно и не превращает незавершённые A/B или Mac-проверки Day 28 в PASS

### Requirement: Exact local model identity and effective settings are recorded

Основное сравнение SHALL использовать точные tags `qwen3:4b-q4_K_M` и `qwen2.5-coder:7b-instruct-q4_K_M` с полными установленными digests. Для каждого профиля SHALL фиксироваться runtime/version/backend, quantization, capabilities/thinking, context/output limits, keep_alive и все поддерживаемые эффективные sampling-параметры, включая наследуемые значения и происхождение defaults. Неустановленный digest SHALL обозначаться unavailable и блокировать live-допуск, а не заменяться вымышленным значением. Изменение digest/settings SHALL создавать новый профиль; результаты SHALL NOT незаметно объединяться. Qwen3.5 9B SHALL использоваться только как исторический контроль на первом этапе.

#### Scenario: Candidate is not installed
- **WHEN** точный tag отсутствует в локальном списке моделей
- **THEN** профиль получает NOT READY с unavailable digest; inference и автоматическое скачивание не выполняются

#### Scenario: Offline checkpoint before installation approval
- **WHEN** offline-реализация проверена, но установка кандидатов ещё не подтверждена пользователем
- **THEN** работа останавливается для review с test counts и открытыми live-задачами; установка, admission и inference не выполняются

#### Scenario: Candidate defaults differ
- **WHEN** сравниваются модели с разными наследуемыми sampling defaults
- **THEN** поддерживаемые общие параметры фиксируются явно, неподдерживаемые отмечаются и различия видны в отчёте; опыт не называется изменением только весов при скрытой смене настроек

### Requirement: Technical admission precedes semantic evaluation

Каждая модель SHALL сначала пройти один ограниченный этап загрузки и компактный структурированный запрос. Допуск SHALL требовать подтверждённой готовности правильной модели/context, завершения done/stop и существующих schema/source checks. Timeout, load error, length, invalid schema или citations SHALL прекращать техническую ветку без полного набора и автоматических повторов. Ошибка SHALL сохраняться. Сходная нестабильность обеих моделей SHALL приводить к предложению отдельной ограниченной диагностики runtime, не к повторным warm-up исторического 9B.

#### Scenario: Admission fails
- **WHEN** первый технический сценарий не завершается в пределах объявленных ограничений либо нарушает структуру
- **THEN** остальные сценарии этой ветки получают NOT RUN с причиной, failed attempt остаётся в результатах, другая модель оценивается независимо

#### Scenario: Both candidates cannot load reliably
- **WHEN** обе ветки демонстрируют аналогичный runtime/load failure
- **THEN** live-эксперимент останавливается и выдаёт факты и ограниченное предложение диагностики; смена runtime/драйвера и новые попытки не выполняются автоматически

### Requirement: Compact Android semantic suite uses frozen equal inputs

До live SHALL быть зафиксированы примерно шесть сценариев на модель, expected facts/rules, forbidden claims, Kotlin/Markdown hashes, вопросы, prompt/schema и одинаковые выбранные chunks с источниками/порядком. Сравнение generation SHALL NOT повторно выбирать chunks в зависимости от модели или её ответа. Набор SHALL сохранять сценарии Day 27–28 по коду, документации, scope conflict, недостатку знаний и adversarial input и добавлять один компактный Compose-сценарий вместо менее полезного существующего вопроса.

#### Scenario: Same generation input for both models
- **WHEN** обе модели допущены к одному scenario ID
- **THEN** Kotlin, вопрос, Markdown spans, их порядок, schema и прикладные инструкции совпадают; различия model-specific templates/capabilities записаны явно
- **AND** основной quality baseline использует Q4_K_M и keep_alive=5m; резидентность проверяется независимо, опыт keep_alive=0 маркируется отдельно

#### Scenario: Compose architectural understanding
- **WHEN** оценивается Compose-сценарий
- **THEN** рубрика отдельно проверяет ViewModel как владельца UI state, StateFlow, lifecycle-aware сбор состояния через collectAsStateWithLifecycle, запуск/отмену/перезапуск LaunchedEffect и разделение Compose, ViewModel и Coordinator
- **AND** смешение lifecycle collection с lifecycle эффекта, обещание exactly-once навигации или выдуманная реализация Coordinator считаются смысловыми ошибками даже при валидном JSON

### Requirement: Quality gates determine practical candidate selection

Оценка SHALL разделять корректность/покрытие Kotlin facts, архитектурные правила, смысловую поддержку цитатами, применимость scope, необоснованные утверждения, ограничения знания и технический outcome. Reviewer и его роль SHALL быть указаны; автоматический или assistant review SHALL NOT подменять user review. Практический профиль SHALL NOT получать semantic PASS только за JSON/ссылки или скорость. При ключевой смысловой ошибке SHALL допускаться не более одной обоснованной адресной правки prompt на кандидата; неуспех после неё SHALL вести к следующему кандидату или честному ограничению.

#### Scenario: Correct quotation with incorrect application
- **WHEN** ответ цитирует batch-rule буквально, но приписывает interactive checkout атомарный rollback
- **THEN** техническая проверка и semantic failure отражаются отдельно; профиль не принимается как практически пригодный

#### Scenario: Small model remains inaccurate after one correction
- **WHEN** после единственной адресной правки сохраняется ключевая Android-ошибка
- **THEN** дальнейший перебор формулировок прекращается; результат фиксируется без PASS и без выбора удачного ответа из серии

### Requirement: Optimization changes one declared factor at a time

После выбора кандидата SHALL выполняться ограниченные сравнения с зафиксированным родительским профилем и одной изменяемой величиной: keep_alive, num_predict, num_ctx, temperature либо одна адресная prompt-правка при обнаруженной ошибке. Контекст SHALL уменьшаться только при подтверждённом вмещении полного model input и output reserve; байтовые лимиты SHALL NOT считаться доказательством token fit. Thinking SHALL учитывать реальные capabilities и оставаться фиксированным внутри пары. Quantization SHALL сравниваться только между вариантами одной модели отдельным обоснованным опытом. Полный перебор сочетаний SHALL NOT выполняться.

#### Scenario: Context fit cannot be established
- **WHEN** доступен только размер JSON в байтах, без достаточного подтверждения числа model input tokens
- **THEN** уменьшение context получает NOT TESTED с причиной; исходник/schema/chunks не обрезаются ради успешного прогона

#### Scenario: Comparing quantizations
- **WHEN** запланирован отдельный опыт Q4 против Q8
- **THEN** сохраняются одна базовая модель/revision и остальные параметры, фиксируются разные digests, память и смысловые результаты; сравнение Qwen3 4B с Coder 7B не называется эффектом quantization
- **AND** без оснований или бюджета Q4/Q8 остаётся NOT TESTED без выводов о влиянии quantization

### Requirement: Selected profile is verified through the real user flow

После сравнения generation выбранный кандидат SHALL проверяться через реальную последовательность query embedding → retrieval → generation с существующим embedding profile и локальной Knowledge. Замороженные chunks SHALL NOT подменять этот этап. Удержание generation SHALL NOT считаться подтверждённым без проверки фактической резидентности между запросами; embedding-вытеснение SHALL учитываться отдельно. При отсутствии пригодного кандидата end-to-end SHALL отмечаться NOT RUN, а не выполняться с произвольной запасной моделью.

#### Scenario: Embedding evicts a resident generator
- **WHEN** следующий query embedding вытесняет generation-модель
- **THEN** последующий запрос классифицируется с повторной загрузкой и её стоимостью, а не как warm только по keep_alive

#### Scenario: Retrieval provides insufficient support
- **WHEN** frozen-context объяснение было корректным, а реальный retrieval не принёс нужное правило
- **THEN** отчёт различает retrieval gap и generation failure; алгоритм поиска не подменяется и не переписывается автоматически

### Requirement: Measurements distinguish phases, limits and unavailable evidence

Для каждой попытки SHALL фиксироваться identity/profile/scenario, stage, outcome, success/failure/not-run reason, monotonic wall durations и доступные provider metrics. Загрузка, cold/warm latency, retrieval, generation и end-to-end SHALL измеряться раздельно с указанными границами. HTTP read timeout SHALL NOT называться общим deadline; общий deadline SHALL охватывать всю явно указанную операцию. Полное время non-stream ответа SHALL NOT называться TTFT. RAM/VRAM snapshots, sampled maxima и system/process measurements SHALL различаться; unavailable SHALL NOT превращаться в ноль. Все ошибки и незавершённые попытки SHALL оставаться в знаменателе соответствующего этапа и в отчёте.

#### Scenario: Deadline expires during load
- **WHEN** ограничение загрузки истекло без подтверждённой готовности
- **THEN** записывается failed/censored load duration, generation NOT STARTED и отсутствие provider counters; истёкшее ожидание не объявляется успешным load time

#### Scenario: Non-stream response and snapshot memory
- **WHEN** получен только полный ответ и несколько снимков памяти
- **THEN** TTFT отмечается unavailable, снимки не называются истинным peak, а пропущенные метрики сохраняются как unavailable

#### Scenario: Real client cancellation
- **WHEN** synthetic driver достигает общего deadline дочерней операции
- **THEN** он завершает и reap только своего child, фиксирует timeout и неизвестное состояние runner; Future timeout без прекращения операции не считается отменой
- **AND** cold admission и warm generation измеряются раздельно, Ollama и посторонние процессы не завершаются

#### Scenario: Minimal synthetic instrumentation
- **WHEN** запускается S1–S6 experiment
- **THEN** небольшой driver использует существующие компоненты, простой словарь settings и штатные snapshots без benchmark framework, provider registry, новой БД или сложного мониторинга

### Requirement: Bounded execution preserves privacy and failed attempts

До live SHALL фиксироваться конечный бюджет попыток/времени и stop conditions. Эксперимент SHALL NOT делать automatic retry, repair, скрытый fallback или удалять неудобные результаты. После timeout SHALL проверяться прекращение относящегося к попытке runner перед следующим опытом; неизвестное состояние SHALL останавливать сессию без уничтожения посторонних процессов. Persistent отчёты SHALL содержать только безопасные configuration/metrics/hashes/verdicts; Workspace code, пользовательские вопросы/ответы и reasoning SHALL NOT сохраняться. Синтетические fixtures SHALL быть явно отделены от пользовательских данных.

#### Scenario: Budget or cleanup boundary reached
- **WHEN** исчерпан объявленный бюджет либо нельзя подтвердить безопасное продолжение после отмены
- **THEN** опыт останавливается с полным учётом попыток и NOT RUN для оставшихся пунктов, не увеличивая лимит автоматически

### Requirement: Target-machine usefulness is verified independently

Windows и Mac M1 16 GB SHALL иметь отдельные результаты. Проверка Mac SHALL выполняться только при наличии устройства и разрешений, с реальной Android Studio, зафиксированной нагрузкой и доступными memory pressure/swap показателями. Эмулятор SHALL рассматриваться отдельно. Отсутствующая Mac-проверка SHALL оставаться PENDING / NOT TESTED и не блокировать честный Windows outcome. День SHALL документировать фактические результаты, включая отсутствие пригодной модели, с относительной ссылкой из корневого README на Day README.

#### Scenario: Mac is unavailable
- **WHEN** target device или разрешения отсутствуют
- **THEN** Windows-профиль описывается как предварительный кандидат для Mac, без заявления Mac performance PASS и без закрытия исторической Mac-задачи Day 28

#### Scenario: Model interferes with developer work
- **WHEN** семантически корректная модель вызывает устойчивый рост swap, memory pressure или неприемлемую потерю отзывчивости IDE
- **THEN** её практическая пригодность на этой машине не подтверждается несмотря на technical/semantic PASS
