## Purpose

Показать на исследовании публичного Android-проекта, как модель выбирает инструменты независимых MCP servers и связывает repository knowledge с проверкой публикаций зависимостей. Отделить наблюдаемый flow и точность передачи данных от истинности внешних источников и финального ответа модели.

## ADDED Requirements

### Requirement: One developer task exposes two independent remote servers

Day 20 SHALL предоставлять один локальный запуск инженерной задачи по `android/nowinandroid`: определить зависимости локального хранения данных и фоновой работы/синхронизации, проверить их Google Maven publications и получить отдельную сводку каждой зависимости. В одном native Responses request SHALL одновременно регистрироваться DeepWiki и существующий Dependency Composition MCP Day 19 с различными `server_label` и endpoint. SHALL использоваться `tool_choice="auto"`. Доступные возможности SHALL включать исследование repository и операции lookup/summary; серверный save SHALL быть исключён. Ни prompt, ни backend SHALL NOT задавать готовые Maven coordinates, Room/WorkManager как обязательный ответ, имена следующих tools или полный порядок вызовов. Backend MUST NOT выполнять или конструировать следующие tool calls вместо модели.

#### Scenario: Model chooses a cross-server path
- **WHEN** пользователь отправляет задачу о двух инженерных ролях зависимостей
- **THEN** модель одновременно получает подходящие tools обоих серверов и выбирает фактические calls/arguments по результатам исследования
- **AND** ранее известные кандидаты не подменяют полученные repository evidence

#### Scenario: Invalid configuration prevents dispatch
- **WHEN** конфигурация endpoint, credentials или конечных лимитов невалидна
- **THEN** операция завершается как `not_sent` без обращения к модели и без изменения доступности предыдущих Days

### Requirement: Successful flow joins repository evidence to two dependency branches

Подтверждённый успешный flow SHALL содержать реальные вызовы обоих servers и две различимые dependency-ветки для заданных инженерных ролей. Для каждой ветки SHALL существовать согласованные repository evidence, Maven lookup и summary. Координаты lookup SHALL проверяться относительно фактического DeepWiki output; полный input summary SHALL соответствовать output своего lookup, включая identity, полный массив versions и порядок элементов. Независимые ветки SHALL допускать разные interleavings. Дополнительные исследовательские calls SHALL оцениваться по назначению, без требования вызвать все DeepWiki tools или достичь фиксированного общего числа calls. Повторы и ошибки SHALL сохраняться и не скрываться выбором удобной успешной подпоследовательности.

#### Scenario: Independent branches have different valid schedules
- **WHEN** после исследования выполнено lookup A → lookup B → summary B → summary A либо lookup A → summary A → lookup B → summary B
- **THEN** обе последовательности допустимы, если зависимости и данные каждой ветки подтверждены

#### Scenario: Branches are confused or data is altered
- **WHEN** summary A получает объект lookup B либо изменённый список версий, timestamp или lookup identity
- **THEN** проверка перехода соответствующей ветки даёт `FAIL`, даже если её summary правильно обработал фактически переданный ошибочный input

#### Scenario: Research cannot be bound to coordinates
- **WHEN** trace содержит успешный lookup, но в сохранённом repository output нельзя однозначно подтвердить его координаты
- **THEN** переход repository → lookup получает `NOT_PROVEN`; совпадение с известными verifier координатами не заменяет evidence

### Requirement: Claims about ordering are limited to observable runtime evidence

Проверка SHALL оценивать частичный порядок repository evidence → lookup → summary отдельно для каждой ветки, используя доступные lifecycle events и связи arguments/outputs. Она MUST NOT считать индекс элемента в финальном output array доказательством завершения предыдущего call до начала следующего. Недостаток временного evidence SHALL давать `NOT_PROVEN`, наблюдаемое нарушение зависимости — `FAIL`. Отчёт SHALL обозначать порядок как наблюдаемый Responses runtime order, не как независимый аудит физических серверов или доказательство внутреннего мышления модели.

#### Scenario: Runtime trace proves a dependency edge
- **WHEN** сохранён завершённый output upstream call до начала downstream call, и downstream arguments согласованы с upstream output
- **THEN** наблюдаемая зависимость получает `PASS` без требования порядка между независимыми ветками

#### Scenario: Only the final response survived
- **WHEN** arguments и outputs сохранены, но lifecycle information недостаточно для порядка
- **THEN** данные проверяются отдельно, а временная зависимость остаётся `NOT_PROVEN`

### Requirement: The first attempt is retained without automatic retry or repair

Для попытки SHALL создаваться уникальный локальный каталог без перезаписи с конфигурацией запроса без секретов. Один запуск SHALL инициировать не более одного provider request с отключёнными SDK retries и конечными deadline/output budget. SHALL сохраняться доступные native discovery definitions, call ids, server labels, names, actual arguments, outputs, status/errors, lifecycle events, provider/response identity и исходный final text. Секреты MUST NOT попадать в prompt, отображение или evidence. Полученные данные MUST NOT исправляться, заменяться fixtures или стираться при ошибке. При timeout, storage error или stream interruption SHALL использоваться доступное evidence, а недоказуемые утверждения SHALL получать `NOT_PROVEN`; повтор или repair SHALL NOT запускаться автоматически. Recovery/replay, durable attempt/idempotency protocol и восстановление повреждённого log SHALL NOT требоваться.

#### Scenario: Connection ends during the run
- **WHEN** после нескольких полученных событий соединение обрывается
- **THEN** доступные сохранённые события используются для проверки, пробелы обозначаются как `NOT_PROVEN`, новый запрос и восстановление log не выполняются

#### Scenario: Model returns an incomplete or incorrect flow
- **WHEN** модель не использует второй server, путает dependencies или ошибается в финальном ответе
- **THEN** это сохраняется как результат первой попытки без regeneration и без повторного live ради улучшения результата

### Requirement: A small independent verifier separates flow from final facts

Verifier SHALL проверять сохранённые данные без model/MCP calls, без исправления evidence и без использования production summarizer для ожидаемых значений. Он SHALL выдавать раздельные `PASS`, `FAIL`, `NOT_PROVEN` для регистрации/import серверов, атрибуции calls, исполнения tools, переходов каждой ветки, частичного порядка, сводок и отдельно финальных фактов. Атрибуция SHALL учитывать пару `(server_label, tool_name)` и label → endpoint mapping. Сводки SHALL сравниваться с независимым расчётом count, последних элементов в порядке источника и canonical lookup hash; фиксированное ожидаемое количество версий SHALL NOT использоваться. Проверка SHALL сравнивать полный lookup object и порядок versions, используя фактический provider format и контракт Dependency MCP. Неинтерпретируемый output SHALL NOT получать PASS. Generic semantic/source parsing, обширная normalization и универсальная adversarial JSON validation SHALL NOT требоваться. Финальные факты SHALL оцениваться отдельно от orchestration; красивый текст MUST NOT превращать ошибочный или недоказанный flow в успех.

#### Scenario: Correct tools and incorrect final count
- **WHEN** calls и переходы корректны, но модель указывает неверное количество версий
- **THEN** проверки наблюдаемого flow сохраняют свои результаты, а точность финальных фактов получает `FAIL`

#### Scenario: Wrong server or concealed failure
- **WHEN** совпадает имя tool, но label не соответствует зарегистрированному server, либо output сообщает tool error при успешном transport status
- **THEN** соответствующие атрибуция или execution получают `FAIL`

#### Scenario: Complete response is missing a required branch
- **WHEN** полный terminal response получен, но lookup или summary одной из двух веток отсутствует
- **THEN** полнота наблюдаемого flow получает `FAIL`; при утрате части trace невозможность установить факт обозначается `NOT_PROVEN`

### Requirement: Repository and publication claims retain source limitations

Результат SHALL сохранять доступные repository source links, excerpts и revision вместе с их происхождением в DeepWiki output. AI-generated output SHALL NOT считаться независимым доказательством истины. Привязка координат к output SHALL отличаться от проверки исходников и актуальности repository revision. Если repository truth/revision нельзя независимо подтвердить по сохранённому evidence, отчёт SHALL указывать `NOT_PROVEN` как ограничение; данные неизвестной ревизии SHALL NOT называться текущим `main`. Отдельный source-review workflow или reviewer-assessment subsystem SHALL NOT требоваться. Членство наблюдавшейся объявленной версии SHALL проверяться относительно фактического списка Google Maven с явной оговоркой, что сведения о её использовании в repository могут оставаться неподтверждёнными. Отрицательный lookup SHALL отражаться без подмены координат. Публикация SHALL NOT интерпретироваться как совместимость, безопасность, latest/stable или рекомендация обновиться. Отчёт SHALL ограничивать вывод одной наблюдавшейся попыткой и не утверждать оптимальность выбора или внутреннюю причинность знания модели.

#### Scenario: DeepWiki has an identifiable older revision
- **WHEN** evidence связывается с конкретной старой ревизией
- **THEN** вывод относится к ней, а актуальность текущего `main` не заявляется

#### Scenario: Dependency is absent from Google Maven
- **WHEN** lookup возвращает group_not_found, artifact_not_found или no_versions
- **THEN** результат сохраняет отрицательный статус и его корректную сводку, не утверждая отсутствие артефакта во всех registry

### Requirement: The experiment uses existing infrastructure and a readable local result

Day 20 SHALL запускаться через существующий локальный backend и отдельный CLI, сохранять evidence и читаемый инженерный отчёт локально и сохранять контракты предыдущих Days. SHALL NOT требоваться новый Android экран, изменения общего agent runtime, новый MCP server, Context7, VPS deployment, SSH, systemd/Caddy, domain/port или server-side inspection. `report.md` и CLI SHALL быть главным human-facing результатом: показывать пользовательскую задачу, смысл исследования repository, выбранную DeepWiki capability, найденные dependencies, потребность в другом MCP server, фактические lookup/summary двух веток, инженерный итог и независимо подтверждённые trace факты с видимыми ограничениями. Verifier internals SHALL оставаться вспомогательными. Локальное сохранение приложением SHALL NOT представляться как model-selected MCP save. Секреты SHALL оставаться server-side.

#### Scenario: Existing endpoint is unavailable
- **WHEN** готовый Dependency MCP не отвечает или отклоняет credentials
- **THEN** недоступность фиксируется без автоматической попытки деплоя или администрирования VPS

#### Scenario: Video uses the retained first attempt
- **WHEN** пользователь демонстрирует результат эксперимента
- **THEN** читаемый отчёт и trace позволяют объяснить переключение между системами без повторного запроса и без чтения verifier JSON

### Requirement: Offline checks and live evidence are explicitly separate

Offline tests SHALL использовать fixtures/fakes и SHALL NOT выполнять реальный DeepWiki/Google Maven flow. До отдельного live SHALL проверяться сохранение evidence, оба допустимых порядка веток, ошибки переходов, честное обозначение неподтверждённых источников, неполное evidence и отсутствие retry. Эти проверки SHALL оставаться узкими, без исчерпывающей матрицы storage failures или generic validator tests. Live SHALL запускаться отдельно один раз; предварительные protocol/discovery checks SHALL явно отличаться от вызовов модели и не подменять её trace. Day README SHALL описывать только фактический результат или отсутствие проверки; корневой README SHALL содержать ссылку на новый день. Код, документация и первая попытка SHALL обеспечивать формат сдачи «видео + код» без утверждения, что видео записано, пока это не подтверждено пользователем.

#### Scenario: Tests pass before live
- **WHEN** offline проверки прошли, но модель ещё не запускалась
- **THEN** документация не заявляет live success или доказанный multi-server flow
