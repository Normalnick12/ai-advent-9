## Purpose

Позволяет Android-разработчику объяснить один выбранный Kotlin-файл с помощью локальной модели, сохраняя явную границу Workspace, ограниченный контекст и различие между наблюдениями, предположениями и недостатком сведений.

## ADDED Requirements

### Requirement: Standalone one-shot CLI accepts explicit inputs

Утилита SHALL работать независимо от backend и Android и принимать `--workspace`, `--file`, `--question`, `--model`, `--base-url`. Workspace и относительный file обязательны. Model SHALL определяться из флага либо LAA_MODEL без зашитого имени модели; URL — из флага, LAA_BASE_URL либо http://127.0.0.1:11434. Флаги имеют приоритет. Без question утилита SHALL один раз читать вопрос из интерактивного терминала; без TTY/при EOF, пустом вводе или отсутствующей модели SHALL завершаться с ошибкой до HTTP. Чат, история и загрузка backend environment SHALL отсутствовать. Успех SHALL давать exit 0, ошибки ввода — 2, ошибки выполнения — 1, пользовательская отмена — 130.

#### Scenario: Explicit question
- **WHEN** переданы допустимые Workspace, file, question и model
- **THEN** утилита выполняет одно объяснение без интерактивного вопроса и завершается
- **AND** ей не нужны FastAPI, OPENAI_API_KEY или Android

#### Scenario: One terminal question
- **WHEN** question отсутствует и доступен TTY
- **THEN** утилита запрашивает один вопрос и после результата или ошибки завершается без следующего хода

#### Scenario: Missing or invalid configuration
- **WHEN** модель отсутствует, вопрос пустой либо question не передан при non-TTY/EOF
- **THEN** отображается безопасная диагностическая ошибка и generation не выполняется

### Requirement: File access is confined to the explicit workspace

Утилита SHALL читать только один существующий обычный `.kt`-файл внутри канонического локального Workspace. Она SHALL отклонять абсолютные/drive-relative/UNC/device file paths, traversal через `..`, alternate data streams, неоднозначные Windows-компоненты, symlinks/junctions в относительном пути и конечный путь вне root. Проверка принадлежности SHALL учитывать реальные пути, а не строковый prefix. Неопределимая безопасность пути SHALL приводить к отказу. Файл SHALL декодироваться как UTF-8 с необязательным BOM; пустой файл и ошибка кодировки SHALL блокировать HTTP. Утилита SHALL NOT сканировать Workspace или читать зависимости, другие файлы либо сеть через файловый путь. Граница эксплуатации — локальный checkout без конкурентной враждебной подмены путей; CLI SHALL NOT объявляться OS sandbox.

#### Scenario: Ordinary nested Kotlin file
- **WHEN** выбран обычный вложенный файл с пробелами или кириллицей в имени
- **THEN** читается только он, а относительный путь определяется от Workspace, не от текущего каталога

#### Scenario: Escaping or linked file
- **WHEN** file указывает наружу через traversal, абсолютный путь, symlink/junction или соседний каталог с похожим префиксом
- **THEN** содержимое цели не читается и HTTP не выполняется

#### Scenario: Unusable source
- **WHEN** путь не существует, является каталогом/необычным файлом, имеет другое расширение, невалидный UTF-8 или пустой текст
- **THEN** утилита сообщает категорию ошибки без вывода содержимого и не вызывает модель

### Requirement: Input size and model token budgets are explicit and independent

Утилита SHALL ограничивать фактически прочитанные исходные данные 16 KiB (допускается один дополнительный byte для обнаружения превышения), вопрос 2000 Unicode code points, полное сериализованное HTTP request body 24 KiB UTF-8 и generation response body 256 KiB. Для metadata /api/show действует отдельный лимит 2 MiB. Превышение SHALL давать ошибку; автоматическое сокращение, summarization или повтор SHALL отсутствовать. Номера строк SHALL относиться к тексту после удаления UTF-8 BOM и нормализации переводов строк в LF с сохранением пустых строк.

Каждый запрос SHALL явно задавать num_ctx и num_predict, по умолчанию 8192 и 2048; `--num-ctx` и `--num-predict` SHALL принимать положительные целые с num_predict < num_ctx. Эти token budgets SHALL NOT вычисляться из byte limits или выдаваться за доказательство полного вмещения prompt. Документация SHALL обозначать риск серверной обрезки и зависимость от tokenizer/template/thinking.

#### Scenario: Input exceeds a limit
- **WHEN** исходник, вопрос или полное тело запроса превышает свой предел
- **THEN** запрос не отправляется и источник не обрезается ради продолжения

#### Scenario: Default generation settings
- **WHEN** запущено объяснение без override token budgets
- **THEN** HTTP содержит num_ctx=8192 и num_predict=2048, а byte limits проверяются независимо

#### Scenario: Invalid budget or oversized response
- **WHEN** бюджет неположительный/нецелый, num_predict >= num_ctx либо ответ превышает 256 KiB
- **THEN** операция завершается соответствующей ошибкой без повторной генерации; невалидный бюджет отклоняется до dispatch

### Requirement: Exactly one inference request stays on controlled local Ollama

Утилита SHALL использовать только HTTP loopback URL, по умолчанию 127.0.0.1:11434; localhost SHALL нормализоваться в literal loopback до соединения. Remote addresses, userinfo, query/fragment, нестандартный URL path и cloud model selection SHALL отклоняться. Утилита SHALL NOT наследовать proxy settings, следовать redirects, обращаться к облачной LLM, запускать model download или fallback. Для допустимого ввода SHALL выполняться не более одного POST /api/chat с stream=false и явными token budgets, с конечными connect/read/write timeouts и без retries.

Контролируемый сервер Ollama SHALL быть настроен local-only с установленной локальной моделью; перед live это SHALL проверяться отдельно. Один loopback URL SHALL NOT объявляться доказательством отсутствия server-side cloud forwarding. Приложение SHALL NOT автоматически менять серверную конфигурацию.

#### Scenario: Local dispatch ignores proxy environment
- **WHEN** указан допустимый loopback URL и в окружении задан внешний HTTP proxy
- **THEN** единственный inference request идёт прямо на loopback без proxy

#### Scenario: Remote target or redirect
- **WHEN** передан remote URL либо локальный сервер отвечает redirect
- **THEN** remote URL отклоняется до запроса, а redirect завершает исходную операцию ошибкой без follow-up HTTP

#### Scenario: Upstream unavailable
- **WHEN** сервер недоступен, истёк timeout, модель отсутствует или API вернул ошибку
- **THEN** выводится безопасная категория ошибки, exit ненулевой и автоматических повторов/скачиваний нет

### Requirement: Completion is checked before accepting an explanation

Перед inference утилита SHALL проверить capabilities выбранной модели одним metadata запросом `/api/show`, не передавая исходник/вопрос. При capability thinking generation SHALL содержать think=false, иначе поле think SHALL отсутствовать. Ошибка/невалидные capabilities или remote model metadata SHALL блокировать generation. Metadata response SHALL ограничиваться 2 MiB; loopback/proxy/redirect/timeouts SHALL применяться и к metadata. Это не дополнительная генерация; reasoning settings UI SHALL отсутствовать.

Успешный ответ SHALL требовать successful HTTP, отсутствия API error, done=true, done_reason=stop, непустого message.content и допустимого explanation payload. Length-limited, unfinished, missing/unknown completion reason, malformed JSON и thinking-only output SHALL NOT считаться успехом. Partial output SHALL NOT отображаться как нормальное объяснение. Ошибка SHALL NOT запускать repair или новый запрос; неизвестная причина SHALL NOT произвольно называться переполнением контекста.

#### Scenario: Thinking support is discovered without inference
- **WHEN** show возвращает capabilities с thinking либо без неё
- **THEN** следующий единственный chat содержит think=false либо не содержит think соответственно
- **AND** ошибка show или remote metadata не приводит к chat

#### Scenario: Output budget exhausted
- **WHEN** Ollama возвращает done_reason=length, даже с внешне допустимым JSON
- **THEN** утилита сообщает незавершённую генерацию и не принимает объяснение

#### Scenario: Missing final answer
- **WHEN** done=false, terminal reason отсутствует/неизвестен либо доступен только thinking без content
- **THEN** утилита сообщает непригодный или неподдержанный результат и завершает операцию без повтора

### Requirement: Explanation separates observations and uncertainty with bounded line references

Ответ SHALL содержать только facts, assumptions и limitations. Facts SHALL быть списком объектов text и lines; assumptions/limitations — списками непустых строк. Каждый fact SHALL содержать непустой текст и непустой список уникальных целых номеров строк 1..N выбранного файла; bool, строка вместо числа и ссылки вне диапазона SHALL отклоняться обычным кодом. Facts=[] SHALL допускаться при непустом limitations; полностью пустое объяснение SHALL отклоняться. Недопустимые значения SHALL NOT исправляться автоматически.

Инструкция модели SHALL просить описать роль класса, видимые зависимости и взаимодействия, отделить возможную интерпретацию и обозначить отсутствующий контекст. Исходник/комментарии SHALL передаваться как данные, не инструкции. CLI SHALL показывать три отдельных русскоязычных раздела и ссылки фактов; допустимость ссылок SHALL NOT объявляться доказательством смысловой корректности.

#### Scenario: Valid explanation
- **WHEN** completed response содержит facts с допустимыми строками и отдельные assumptions/limitations
- **THEN** CLI показывает все три раздела, сохраняет исходную классификацию и завершается успешно

#### Scenario: Invalid line reference
- **WHEN** fact не содержит lines либо указывает 0, N+1, bool, строку или дубликат
- **THEN** объяснение не принимается; утилита не подставляет другие строки и не просит модель исправить ответ

#### Scenario: Missing dependency implementation
- **WHEN** синтетический класс вызывает зависимость, реализация которой не предоставлена
- **THEN** инструкция требует объяснить видимый вызов и указать невозможность установить внутреннее поведение зависимости
- **AND** выполнение этого смыслового требования оценивается reviewer по исходнику, отдельно от schema/line checks

### Requirement: Content stays transient and diagnostics remain non-content

Приложение SHALL NOT сохранять исходники, вопросы, prompt, ответы, историю или raw API errors в файлы/логи/отчёты. Оно SHALL выводить ответ только в терминал, безопасную диагностику без traceback по умолчанию и без исполнения terminal control sequences из недоверенного текста. Метрики SHALL ограничиваться model/settings, статусом, временем и предоставленными Ollama счётчиками; отсутствующие значения SHALL отображаться как unavailable. Absolute workspace path и содержимое SHALL NOT попадать в метрики.

Документация SHALL отделять код и синтетические fixtures от пользовательских данных: checkout вне Git-репозитория либо домашний synthetic scratch в игнорируемой .local; runtime SHALL ничего не копировать. Приложение SHALL NOT заявлять управление shell history или логами отдельного Ollama-сервера.

#### Scenario: Success and API failure do not write content
- **WHEN** запрос успешно завершён либо сервер вернул ошибку с отражённым prompt
- **THEN** приложение не создаёт content artifacts, а диагностика ошибки не содержит отражённый текст

#### Scenario: Missing or partial usage metadata
- **WHEN** сервер не предоставил token count или duration
- **THEN** CLI показывает unavailable, не вычисляет токены из bytes и не подставляет ноль

### Requirement: Acceptance uses synthetic offline cases and one observed Windows run

Проверка SHALL использовать только синтетический Kotlin и compact offline tests с подставным HTTP transport, включая файловые ограничения, интерактивный ввод, фактический payload, ошибки/обрывы, строки и отсутствие content persistence. Platform-specific skips SHALL явно сообщаться и не считаться проверенным поведением.

После offline SHALL выполняться один live attempt на Windows через Ollama 0.40.2 и qwen3.5:9b-q4_K_M с 8192/2048, без автоматического повтора. Reviewer SHALL отдельно оценить роль, зависимости/взаимодействия, поддержку facts строками и честность uncertainty. Время, reported tokens и ограничения SHALL фиксироваться без transcript в документации; failure SHALL фиксироваться как failure, не успешное объяснение. Неизмеренная macOS performance SHALL оставаться непроверенной. Day README SHALL содержать краткий результат и минимальные инструкции standalone CLI, корневой README — относительную ссылку. Видео, commit и push SHALL не быть условием этой проверки.

#### Scenario: Offline then one live observation
- **WHEN** focused offline checks завершены и подтверждены local-only server и установленная модель
- **THEN** выполняется один synthetic live request и отдельно записываются технический исход, метрики и ручной verdict

#### Scenario: Live run fails or reveals unsupported claims
- **WHEN** единственный live attempt оборван, отклонён либо reviewer обнаружил неверные утверждения
- **THEN** документация отражает этот результат и ограничения без повторного подбора удачного ответа и без объявления acceptance успешной
