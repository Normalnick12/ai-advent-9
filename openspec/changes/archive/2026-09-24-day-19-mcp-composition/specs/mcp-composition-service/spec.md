# Spec Delta

## Purpose

Предоставить на отдельном MCP endpoint Day 19 три независимо вызываемых инструмента получения версий Google Maven, детерминированной обработки полного результата и сохранения проверяемого JSON-отчёта без изменения контрактов предыдущих дней.

## ADDED Requirements

### Requirement: Isolated endpoint exposes exactly three tools
Day 19 SHALL публиковать ровно `get_google_maven_versions(group_id, artifact_id)`, `summarize_dependency_versions(lookup)` и `save_dependency_report(report)` на одном отдельном HTTPS MCP endpoint. Каждый tool SHALL иметь собственные input/output schemas и вызываться отдельно. Lookup и summarize SHALL обозначаться read-only, save — изменяющим состояние, non-destructive и идемпотентным для одинакового отчёта. Запуск Day 19 MUST NOT запускать scheduler, читать watch SQLite или менять discovery/contracts/endpoints Days 17–18.

#### Scenario: Discovery preserves the separate operations
- **WHEN** авторизованный MCP client запрашивает tools/list Day 19
- **THEN** он получает ровно три названных tool с schemas и соответствующими annotations
- **AND** выполнение одного tool не вызывает автоматически два остальных

#### Scenario: Existing days remain independent
- **WHEN** Day 19 запускается либо его configuration отсутствует у локального backend
- **THEN** Day 17 продолжает публиковать один lookup tool, Day 18 — два watch tools, а их прежние операции и данные не меняются

### Requirement: Lookup retains full Google Maven semantics
Lookup SHALL принимать только точные group_id/artifact_id с прежними coordinate constraints Days 17–18 и обращаться только к сформированному официальному Google Maven group-index URL. Он SHALL возвращать полный список версий в source order, сохраняя дубликаты и строки без сортировки/semver-интерпретации. Deadline SHALL составлять 15 секунд, upstream body limit — 2 MiB; redirects и небезопасный XML SHALL отклоняться. Невалидный input MUST NOT вызывать upstream request. Сокращённый список MUST NOT возвращаться как полный результат.

#### Scenario: Source order and duplicates survive lookup
- **WHEN** fixture содержит versions `2.0,1.0,2.0,3.0-rc01`
- **THEN** tool возвращает все четыре строки в том же порядке, включая повтор, после одного обращения к точному group-index URL

#### Scenario: Coordinates cannot select another origin or path
- **WHEN** координаты содержат URL/path syntax, whitespace, percent encoding, пустой group segment, неверный тип или превышают 256 символов
- **THEN** tool отклоняет input до сетевого обращения

### Requirement: Typed lookup results distinguish negatives from failures
`LookupResult` SHALL содержать ровно обязательные `status`, `group_id`, `artifact_id`, `versions`, `source_url`, `checked_at`, `lookup_id`. Status SHALL быть found/group_not_found/artifact_not_found/no_versions; только found SHALL иметь непустой versions, остальные normal statuses — []. Source URL SHALL точно соответствовать group_id; checked_at SHALL быть фактическим UTC временем lookup в форме `YYYY-MM-DDTHH:MM:SS.sssZ`, lookup_id — canonical lowercase UUID string. Строки версий SHALL быть непустыми без whitespace. Нормальные отрицательные результаты MUST NOT трактоваться как network/XML errors. Timeout/network/HTTP кроме обработанного 404/XML/body-limit failure SHALL возвращаться как tool execution error с безопасной категорией и lookup_id, без normal LookupResult.

#### Scenario: Negative lookup differs from an upstream error
- **WHEN** один lookup получает group-index 404, другой валидный XML без artifact, третий timeout
- **THEN** первые два возвращают соответственно group_not_found и artifact_not_found с [], а третий возвращает execution error без подстановки пустого успешного snapshot

#### Scenario: Explicit empty versions are retained
- **WHEN** найденный artifact имеет явно пустой versions attribute
- **THEN** LookupResult имеет no_versions и [], а не artifact_not_found

### Requirement: Summarize consumes the exact complete lookup
Summarize SHALL принимать ровно `{lookup: LookupResult}` с полным объектом и проверять schema/invariants без coercion, trim или нормализации значений. Он SHALL возвращать `DependencyReport` с ровно обязательными `schema_version=1`, `status`, `group_id`, `artifact_id`, `source_url`, `checked_at`, `lookup_id`, `version_count`, `last_three`, `input_sha256`. Identity/source/status поля SHALL копироваться неизменно; version_count SHALL равняться len(versions), last_three — versions[-3:] в source order, input_sha256 — lowercase SHA-256 канонических bytes всего lookup. Summarize MUST NOT выполнять network/LLM lookup, читать или сохранять report/watch. Неизвестные поля и неверные types SHALL отклоняться, bool MUST NOT приниматься как integer.

#### Scenario: Deterministic summary preserves the tail
- **WHEN** summarize получает валидный lookup с versions `["2.0","1.0","2.0","3.0-rc01"]`
- **THEN** report имеет version_count=4 и last_three `["1.0","2.0","3.0-rc01"]`, сохраняет исходную identity и hash полного lookup
- **AND** повтор того же input возвращает тот же report без нового upstream request или записи

#### Scenario: Negative report preserves the meaning of zero
- **WHEN** summarize получает любой normal negative LookupResult
- **THEN** report сохраняет этот status, имеет count=0 и tail=[], где zero означает длину возвращённого списка и не утверждает отсутствие публикаций вне результата lookup

#### Scenario: Invalid nested lookup is rejected
- **WHEN** lookup содержит found с [], URL от другого group, неканоническое время/UUID, missing/extra field или неверный тип
- **THEN** summarize возвращает явную validation error без исправления input и без каких-либо внешних действий

### Requirement: Canonical JSON has an exact versioned representation
Каноническое представление C_v1 SHALL быть UTF-8 JSON без BOM: object keys лексикографически отсортированы, separators — comma/colon без пробелов, ASCII escaping включён, non-finite numbers запрещены, в конце ровно один LF. Допустимые значения контрактов SHALL ограничиваться strings, strict integers, arrays и objects; строковые значения и array order MUST NOT нормализоваться. SHA-256 SHALL вычисляться от этих bytes, включая завершающий LF. Report SHALL иметь schema_version strict integer 1. Независимая проверка SHALL располагать golden bytes/hash fixtures, включая escaped strings.

#### Scenario: Key order does not alter canonical bytes
- **WHEN** два JSON objects отличаются только порядком object keys и внешними пробелами
- **THEN** C_v1 и SHA-256 совпадают
- **AND** изменение строки, порядка array или дубликата приводит к другим bytes; bool вместо integer отвергается schema

### Requirement: Save accepts only a report and returns a verifiable receipt
Save SHALL принимать ровно `{report: DependencyReport}`, отклонять missing/extra fields и проверять типы/форматы/внутренние инварианты без пересчёта отчёта. Для found count SHALL быть >0, для остальных statuses count=0/tail=[], а tail length SHALL быть min(count,3). Save MUST NOT повторять lookup, recompute count/tail/input_sha256, создавать произвольный text content или исправлять report. Он SHALL сохранять C_v1(report) и возвращать `SaveReceipt` с ровно `status="saved"`, `lookup_id`, `file_id`, `sha256`, `bytes`; file_id и sha256 SHALL быть одинаковым lowercase 64-hex SHA-256 записанных bytes, bytes — их strict positive integer length. Saved SHALL подтверждаться только после публикации и успешного readback. Receipt MUST NOT представляться доказательством происхождения report от предыдущего tool.

#### Scenario: Receipt describes the accepted report
- **WHEN** save получает валидный report и запись/readback успешны
- **THEN** receipt содержит его lookup_id, точные hash/byte count и стабильный file_id
- **AND** сеть, scheduler и модель не вызываются

#### Scenario: Structurally valid forgery is not certified as source truth
- **WHEN** принятый report имеет согласованные types/invariants, но отличается от фактического предыдущего MCP output
- **THEN** save не заявляет проверку provenance; такой report остаётся предметом независимой проверки цепочки и не исправляется автоматически

### Requirement: File writes are confined persistent and repeatable
Reports SHALL храниться в выделенном конфигурацией постоянном каталоге VPS вне заменяемого release tree, по умолчанию `/var/lib/day19/reports/`. Имя SHALL формироваться только сервером как `<file_id>.json`. Tool arguments MUST NOT содержать path/filename/directory либо произвольный file content. Запись SHALL оставаться внутри root и не следовать symlinks за его пределы. Final file SHALL публиковаться атомарно после записи полных bytes; иной существующий content MUST NOT перезаписываться. Повтор одинакового report SHALL возвращать тот же файл/receipt без дубля. Storage errors SHALL быть явными и MUST NOT подтверждать saved; ошибка после публикации MUST NOT служить утверждением, что файл отсутствует.

#### Scenario: Path injection cannot select a target
- **WHEN** клиент добавляет path/filename/directory/content на любом уровне tool input либо target пытается перенаправить запись symlink
- **THEN** запрос/запись отклоняются, файл вне настроенного root не создаётся и не меняется

#### Scenario: Repeated save is harmless
- **WHEN** после успешного save последующий вызов сохраняет тот же report
- **THEN** существует один final file с правильными bytes, оба успешных receipts относятся к нему, неполный JSON не наблюдается как final result

#### Scenario: Storage failure cannot become a success
- **WHEN** проверка воспроизводит ошибку записи temporary file до публикации
- **THEN** возвращается безопасная storage error без ложного saved и без частичного final file

### Requirement: Authenticated calls produce correlatable safe evidence
Day 19 discovery/dispatch SHALL требовать валидную Bearer authorization, доверенный HTTPS и Host/Origin protection для настроенного endpoint. Service MUST NOT требовать OpenAI key. Safe server events SHALL идентифицировать фактические tool invocations, start/end/outcome, имя tool, lookup_id при наличии и hashes принятых/возвращённых объектов; lookup SHALL иметь коррелируемый upstream event. Credentials MUST NOT попадать в tool schemas/arguments/results, model prompt, logs или report. Отсутствие configuration MUST NOT включать anonymous write mode.

#### Scenario: Unauthorized request has no tool side effects
- **WHEN** discovery или call приходит без валидного token
- **THEN** service отказывает до dispatch, не обращается к Google Maven и не записывает report

#### Scenario: Calls can be checked for temporal dependency
- **WHEN** клиент выполняет lookup, затем summarize, затем save
- **THEN** server events позволяют связать каждое исполнение с его input/output и проверить завершение предыдущего шага до начала следующего без выдумывания provider call IDs
