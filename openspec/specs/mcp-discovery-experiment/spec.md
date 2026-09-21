# mcp-discovery-experiment Specification

## Purpose

Определяет Day 16 как самостоятельный Python experiment, демонстрирующий реальное MCP connection, protocol negotiation и получение читаемого tool catalog DeepWiki без выполнения инструментов и интеграции с агентом.

## Requirements

### Requirement: Standalone discovery preserves existing application boundaries

Day 16 SHALL запускаться как standalone Python CLI в `day-16-mcp-discovery/`, без работающего backend, Android, credentials и состояния предыдущих Days. Эксперимент SHALL NOT читать или изменять Memory, Profile, Task State, Invariants, Lifecycle, LlmClient или Day 15 Playground и SHALL NOT изменять их контракты.

#### Scenario: Run independently of previous days
- **WHEN** пользователь запускает установленный CLI при выключенных backend и Android и без API keys
- **THEN** эксперимент требует только доступ к выбранному remote MCP server и не обращается к компонентам или базам предыдущих Days

### Requirement: Connect and negotiate with the single remote server

CLI SHALL подключаться к `https://mcp.deepwiki.com/mcp` через Streamable HTTP без authentication и выполнять совместимое protocol negotiation. Пользовательский flow SHALL быть `connect → protocol negotiation → tools/list → catalog`. Успех SHALL NOT зависеть от обязательного legacy initialize handshake или заранее заданной protocol revision.

#### Scenario: Successful compatible negotiation
- **WHEN** сервер доступен и protocol negotiation завершается успешно
- **THEN** CLI выводит endpoint, подтверждение успешного MCP connection и фактический negotiated `protocol_version` до результата discovery
- **AND** success не требует конкретного negotiation path: современный discovery или legacy initialize допустимы

#### Scenario: Server identity is optional
- **WHEN** сервер предоставляет имя и версию либо не предоставляет часть этих сведений
- **THEN** CLI выводит полученные сведения и явно обозначает отсутствующие поля, не подменяя их предположениями или версией клиентской библиотеки

### Requirement: Discover and display the current complete tool catalog

CLI SHALL выполнять реальный `tools/list` и выводить количество полученных tools, name, description и полную input schema каждого определения в читаемом виде. Отсутствующее description SHALL обозначаться явно. Каталог SHALL формироваться из ответов текущего запуска, без hardcoded names/count, fixture substitution или сохранённого каталога. При наличии следующих страниц CLI SHALL учитывать их в итоговом каталоге.

#### Scenario: External catalog changes
- **WHEN** сервер возвращает корректный каталог с другим количеством или другими именами tools
- **THEN** CLI выводит фактически полученные definitions и count, не отклоняя их из-за несовпадения с прежним каталогом

#### Scenario: Readable nested schemas
- **WHEN** определение содержит Unicode description и вложенную input schema
- **THEN** CLI сохраняет текст description и все поля schema, включая вложенность и required, и выводит schema как JSON с отступами

#### Scenario: Complete multi-page catalog
- **WHEN** ответ tools/list указывает на следующую страницу
- **THEN** итоговый count и вывод включают definitions со всех полученных страниц
- **AND** ошибка получения продолжения не объявляется успешным получением полного каталога

#### Scenario: Empty catalog is reported honestly
- **WHEN** сервер возвращает корректный пустой каталог без продолжения
- **THEN** CLI показывает 0 tools и может штатно завершиться с code 0
- **AND** этот запуск не удовлетворяет live acceptance Day 16, требующему непустой каталог

### Requirement: Discovery never invokes tools or a model

Эксперимент SHALL ограничивать прикладные MCP-запросы получением каталога; protocol negotiation и lifecycle сообщения допустимы. CLI SHALL NOT выполнять `tools/call`, вызывать любой DeepWiki tool, передавать definitions модели или обращаться к LLM/OpenAI Responses API. Выбор tools, agent loop, multiple servers, orchestration и собственный MCP server SHALL NOT входить в эксперимент.

#### Scenario: Catalog contains callable tools
- **WHEN** discovery возвращает definitions доступных инструментов
- **THEN** CLI только отображает их и завершает работу без вызова инструментов или модели

### Requirement: Completion and failures are distinguishable

CLI SHALL освобождать ресурсы соединения при завершении и ошибке. Успешное discovery, вывод и штатное закрытие SHALL завершаться code 0 с сообщением о нормальном завершении. Ошибка подключения, negotiation, listing, вывода или закрытия SHALL давать понятную ошибку и ненулевой exit code без финального success. Ожидание network operation SHALL быть ограничено timeout; автоматическая подмена сервера или результатов SHALL NOT применяться.

#### Scenario: Clean completion
- **WHEN** negotiation, получение каталога, его вывод и закрытие ресурсов завершились успешно
- **THEN** процесс штатно завершается с code 0 и сообщает о завершении после закрытия соединения

#### Scenario: Remote failure or timeout
- **WHEN** connection/negotiation или получение любой страницы каталога завершается ошибкой либо timeout
- **THEN** CLI сообщает об ошибке в stderr, выходит с ненулевым кодом и не объявляет discovery успешным
- **AND** успешное сообщение connection, если оно уже было показано, не подменяет результат discovery

### Requirement: Offline checks and live acceptance provide different evidence

Deterministic offline tests SHALL проверять собственную логику форматирования, сбора каталога и error outcome в пределах реально выделенной реализации без network calls. Они SHALL NOT считаться доказательством remote connection, negotiation или реального каталога. Live acceptance SHALL отдельно подтвердить подключение к DeepWiki, успешное protocol negotiation, реальный tools/list, непустой каталог, читаемый вывод definitions и clean exit с code 0. Количество и конкретные names tools SHALL NOT быть фиксированными acceptance requirements.

#### Scenario: Offline suite passes
- **WHEN** проверки с controlled responses завершаются успешно
- **THEN** результат описывается только как проверка локальной логики; live остаётся неподтверждённым до реального запуска

#### Scenario: Successful live demonstration
- **WHEN** один реальный запуск к DeepWiki выполняет все шесть live acceptance условий
- **THEN** допускается утверждать, что данный standalone процесс подключился, согласовал протокол, получил и разобрал предоставленный каталог в этом запуске
- **AND** результат не трактуется как проверка invocation, выбора моделью, orchestration, качества MCP или сравнения MCP со Skills

### Requirement: Documentation records the actual experiment outcome

Day README SHALL кратко описывать суть, проверяемое поведение, реальные результаты и минимальные зависимости/команды standalone CLI. Непроведённый live SHALL быть явно отмечен. Root README SHALL содержать одну относительную ссылку на существующий Day README в порядке дней. Документация SHALL NOT требовать backend, Android или OPENAI_API_KEY для Day 16.

#### Scenario: Documentation before and after live
- **WHEN** реализация готова, но live ещё не выполнен, либо live дал наблюдаемый результат
- **THEN** README соответственно сообщает об отсутствии live проверки либо фиксирует только фактический итог без вымышленных numbers/tool names и обобщений о стабильности сервиса
- **AND** Day 16 доступен по относительной ссылке из раздела «Задания» root README
