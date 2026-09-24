# mcp-composition-experiment Specification

## Purpose

Проверить в одной пользовательской auto-операции последовательный выбор трёх MCP tools моделью, точную передачу полного результата на обеих границах и сохранённый файл, сохраняя независимые вердикты механизма и финального ответа.

## Requirements

### Requirement: One user submission runs one native auto request
Одна явная Day 19 отправка SHALL выполнять один native Responses request с одним отдельным Day 19 server, allowlist ровно `get_google_maven_versions`, `summarize_dependency_versions`, `save_dependency_report` и `tool_choice="auto"`. Конфигурация SHALL сохранять model alias `gpt-5.6`, store=false, отключённые SDK retries и конечные предварительно выбранные budget/deadline. URL/token SHALL загружаться server-side; native authorization MUST NOT попадать в prompt или evidence. Require_approval SHALL быть never для явно запрошенной ограниченной записи. Backend MUST NOT принудительно выбирать отдельные шаги, подставлять arguments, запускать фиксированную цепочку вместо модели, выполнять regeneration/repair либо скрытый повтор. Минимальный запуск SHALL быть доступен через локальный backend и CLI без нового Android экрана.

#### Scenario: Auto request leaves selection and arguments to the model
- **WHEN** пользователь один раз запускает получение, обработку и сохранение core-ktx
- **THEN** отправлен один request с тремя разрешёнными tools одного server и auto, фактические имена/arguments определяются моделью

#### Scenario: Configuration or evidence storage prevents submission
- **WHEN** Day 19 URL/token/budget configuration невалидна либо attempt evidence нельзя сохранить
- **THEN** операция возвращает not_sent без provider request; старые Days доступны по прежним контрактам

### Requirement: Attempts retain raw evidence without repair
Операция SHALL резервировать operation/attempt identity до dispatch и сохранять redacted request configuration, prompt, requested/resolved model при наличии, provider status/error, response_id и все доступные исходные Responses output/MCP items в исходном порядке. Каждый call SHALL сохранять id, server_label, name, actual arguments, status при наличии, output и error. Raw final text SHALL сохраняться отдельно от typed facts и verdicts. Отсутствующие значения MUST NOT выдумываться. Исходное evidence MUST NOT исправляться или заменяться последним успешным call; все повторные/лишние calls SHALL оставаться видимыми. Timeout без результата SHALL означать unknown invocation, не отсутствие файла и не разрешение retry.

#### Scenario: More than three calls are observed
- **WHEN** модель повторяет lookup/save либо делает дополнительный call
- **THEN** все calls сохраняются, verdict учитывает всю последовательность и не выбирает удобную тройку

#### Scenario: Response is lost after possible write
- **WHEN** provider deadline истёк до получения полного ответа
- **THEN** attempt сохраняет неизвестный remote outcome, доступные факты и отсутствие automatic retry; сохранение файла не объявляется отменённым

### Requirement: Independent verifier checks full data boundaries and computation
Verifier SHALL работать только с сохранёнными фактическими arguments/outputs, server evidence и независимо прочитанным файлом, без новых tool/model calls или изменения этих данных. Он SHALL сравнивать весь input второго tool с output первого, весь input третьего с output второго и весь report с независимо рассчитанным ожидаемым report из исходного lookup. Object key order и внешние JSON spaces SHALL игнорироваться; string values/types, array order, дубликаты и полный состав fields SHALL сравниваться точно без coercion/normalization. Невалидный JSON, duplicate keys, missing/extra fields, противоречащие structured/text wrappers SHALL обнаруживаться. Проверка MUST NOT ограничиваться count/tail/hash, вызывать production summarize/save для ожидаемого результата или исправлять модель.

#### Scenario: Middle-element corruption is detected
- **WHEN** модель меняет среднюю версию при неизменных длине и последних трёх элементах
- **THEN** lookup_to_summary получает FAIL по полному сравнению, даже если summarize верно обработал свой actual input

#### Scenario: Correct transfer does not hide a processing bug
- **WHEN** оба input transitions точны, но summarize неверно вычислил count/tail/hash
- **THEN** transfer может иметь PASS, а tool_execution/report_correctness получают FAIL по независимому расчёту

#### Scenario: Second boundary is checked separately
- **WHEN** save arguments содержат schema-valid report, отличающийся от summarize output
- **THEN** summary_to_save получает FAIL независимо от успешности записи принятого объекта

### Requirement: Independent disk read proves the saved artifact
Проверка файла SHALL получать фактические bytes отдельным read-only чтением с VPS после попытки, независимо от save-tool readback/receipt. Collector SHALL использовать заранее известный root и validated 64-hex file_id без произвольного model path; он MUST NOT создавать файл, вызывать save или сериализовать ожидаемый report вместо чтения. Evidence SHALL сохранять полные bytes либо lossless encoding, их size/hash, время чтения и связь с operation/revision/lookup. Verifier SHALL сравнивать bytes и с каноническим actual save input, и с каноническим ожидаемым report из первого tool, проверять receipt и identity. Недоступный файл/read evidence SHALL получать FAIL при доказанном несоответствии или NOT_PROVEN при недостатке наблюдений, но не PASS по одному receipt.

#### Scenario: Receipt claims success but disk content differs
- **WHEN** receipt имеет saved, а independently read bytes отличаются от ожидаемого report
- **THEN** file_persistence получает FAIL, независимо от final text и существования файла

#### Scenario: Receipt exists but independent read is unavailable
- **WHEN** есть saved receipt, но чтение VPS не дало достоверных bytes
- **THEN** file_persistence остаётся NOT_PROVEN и цепочка не объявляется PASS

### Requirement: Verdicts separate mechanism transfer persistence and final text
Verifier SHALL возвращать PASS/FAIL/NOT_PROVEN с reason/evidence references раздельно для tool_execution, selection_order, data_transfer с двумя boundary sub-verdicts, report_correctness, file_persistence и final_text_accuracy. Исполнение tool SHALL оцениваться относительно его actual input, end-to-end результат — относительно исходного lookup и целевого запроса. Selection PASS SHALL требовать ровно трёх calls нужного server в порядке lookup → summarize → save, правильных координат и подтверждённой последовательности исполнения по server events. Chain PASS SHALL требовать PASS первых пяти verdicts; любой доказанный FAIL даёт chain FAIL, иначе недостающие доказательства дают NOT_PROVEN. Final text SHALL оцениваться отдельно и MUST NOT изменять доказанные результаты цепочки. Full acceptance основного positive live SHALL требовать chain PASS, final_text_accuracy PASS и исходный lookup status=found; provider completed сам по себе недостаточен.

#### Scenario: Correct file and incorrect final count are separated
- **WHEN** три tools, оба перехода, расчёт и файл правильны, но final text называет другое количество
- **THEN** chain=PASS, final_text_accuracy=FAIL и full_acceptance не пройден без перегенерации

#### Scenario: No tool was selected
- **WHEN** завершённый auto response без discovery failure не содержит calls
- **THEN** selection_order=FAIL с причиной not_called; отсутствующим исполнению/переносу/файлу PASS не присваивается и скрытого fallback нет

#### Scenario: Item order alone does not establish execution order
- **WHEN** имена calls расположены правильно, но нет необходимых server start/end evidence
- **THEN** последовательное исполнение не объявляется доказанным и selection_order остаётся NOT_PROVEN, если иное расхождение не даёт FAIL

### Requirement: Final response facts have a deterministic review format
Для успешной цепочки instructions SHALL запрашивать один final JSON object без Markdown с ровно group_id, artifact_id, status, version_count, last_three и file_id. Verifier SHALL сравнивать все поля с независимо ожидаемыми фактами первого lookup/report/file, сохраняя raw output_text. Неверный формат SHALL давать final_format_mismatch, неправильные факты — final_fact_mismatch; запрещено чинить JSON или заменять ответ. Final verdict SHALL определяться доступными фактами независимо от selection_order: доказанное ложное утверждение — FAIL, недостаточное evidence — NOT_PROVEN, полностью подтверждённые исходные факты и ожидаемый файл — PASS даже при лишнем call. Текст ошибки SHALL сохраняться без заявления об оценке произвольного prose. Проверка MUST NOT использовать дополнительную generation/LLM judge или заявлять оценку произвольного свободного prose.

#### Scenario: Model final JSON matches verified facts
- **WHEN** chain доказана и final JSON содержит ровно ожидаемые факты
- **THEN** final_text_accuracy=PASS даже при ином порядке object keys, без изменения raw text

#### Scenario: Free-form output violates the agreed format
- **WHEN** после правильной цепочки модель возвращает Markdown, дополнительные fields или непарсируемый текст
- **THEN** final_text_accuracy=FAIL с final_format_mismatch, chain verdict сохраняется и repair не выполняется

#### Scenario: Extra call does not automatically invalidate correct final facts
- **WHEN** модель выполнила лишний call, но final JSON точно описывает независимо подтверждённые исходные факты и правильный сохранённый файл
- **THEN** selection_order и chain получают FAIL, а final_text_accuracy может получить PASS по собственным проверкам без сокрытия лишнего call

### Requirement: Offline gate exercises three real MCP calls and verifier mutations
Offline gate SHALL использовать direct MCP client, подставной Google Maven response и temporary file root без реальных upstream/model/VPS calls. Он SHALL проверить discovery ровно трёх tools, полную цепочку из трёх отдельных MCP calls, точные actual arguments на обеих границах, deterministic report, receipt и прочитанные bytes. Gate SHALL включать normal negatives, существенные input/upstream errors, отсутствие network у summarize/save, ошибки wrappers и mutation tests независимого verifier. Обязательные файловые проверки SHALL покрывать ограничение пути, атомарную публикацию, последовательный идемпотентный повтор, одну воспроизводимую ошибку записи без ложного saved/частичного final file и независимое чтение bytes/hash/receipt. Дополнительные проверки конкурентности, crash-recovery и отдельных типов storage failure SHALL добавляться только по выявленному риску с зафиксированным основанием. При изменении общего кода SHALL выполняться регрессии затронутых Days 17–18; baseline MUST NOT выдаваться за model orchestration или live acceptance.

#### Scenario: Offline baseline passes without a model
- **WHEN** код последовательно вызывает три tools через MCP client и точно передаёт результаты fixtures
- **THEN** инструменты и verifier проходят offline gate, но утверждение о самостоятельном выборе tools моделью остаётся непроверенным

#### Scenario: Mutation suite rejects misleading success
- **WHEN** fixtures меняют версию в середине массива, identity, report, receipt/hash/file bytes, порядок/число calls или final count
- **THEN** соответствующие verdicts выявляют каждое искажение, включая случай правильного save для подменённого report

### Requirement: Pre-live gate measures full payload before choosing budgets
Этапы SHALL выполняться в порядке offline → deployment/readiness → pre-live → один live. Deployment/readiness SHALL следовать после offline checks и подтверждать фактически deployed Day 19 revision: isolated endpoint, auth/discovery, file-root permissions и manifest. Pre-live SHALL следовать после deployment/readiness. Gates MUST NOT вводить дополнительные обязательные запросы разрешения при уже порученной работе, если их не требуют AGENTS.md или явное указание пользователя. Отдельный preflight lookup целевого artifact без модели SHALL предоставить полный фактический payload для измерения UTF-8 size и token estimate input/context и генерируемых downstream arguments/final. Evidence SHALL фиксировать schemas/prompt/payload measurements, метод оценки/неопределённость, выбранный max_output_tokens/deadline и запас. Preflight MUST NOT подменять первый tool live. Недостаточный бюджет/неизвестные применимые лимиты SHALL блокировать live. Если нужен сокращённый список, pagination или handles, proposal/specs/design/tasks и acceptance SHALL быть явно пересмотрены до live; скрытое truncation запрещено.

#### Scenario: Full payload fits the documented budget
- **WHEN** actual preflight lookup и downstream envelopes измерены и offline-проверены с достаточным budget margin
- **THEN** gate сохраняет обоснование выбранных лимитов и подтверждает готовность к одной live-попытке без изменения списка

#### Scenario: Full payload cannot fit
- **WHEN** невозможно подтвердить запас для полного списка и three-tool response
- **THEN** live не запускается; список не сокращается, запрос не заменяется другим artifact и пробная generation не используется для обхода gate

### Requirement: One live attempt has explicit positive acceptance and bounded claims
Основной live SHALL выполняться после offline → deployment/readiness → pre-live в рамках порученного пользователем объёма работ: одна отправка для `androidx.core:core-ktx`, один auto request, один Day 19 endpoint, без forced steps/retries/repair. Evidence SHALL содержать фактическую revision/configuration, все MCP items/errors/IDs, lookup/server correlation, размеры actual payload, independent disk read и verdict artifact. Positive scenario SHALL требовать found, три отдельных последовательных calls, два точных перехода, правильный отчёт и файл; final accuracy SHALL оцениваться отдельно. Normal negative SHALL сохраняться как нормальный tool outcome и невыполненный positive scenario, не technical error. Невыполненная моделью цепочка SHALL оставаться результатом этой попытки. Файл preflight/offline или SQLite scheduler record MUST NOT засчитываться как live result. README SHALL отражать только факты и иметь root README link.

#### Scenario: Single positive chain is proven
- **WHEN** live содержит три правильных calls и полное согласованное evidence с found
- **THEN** chain и positive scenario получают PASS, final accuracy оценивается отдельно, а результат не обобщается на надёжность всех будущих запросов

#### Scenario: Model does not complete the chain
- **WHEN** модель пропускает, повторяет или переставляет шаг, меняет данные или завершает response раньше сохранения
- **THEN** исходная попытка сохраняется с соответствующим failure/not-proven evidence, без скрытого повтора или исправления; документирование эксперимента не выдаёт failure за успешный acceptance
