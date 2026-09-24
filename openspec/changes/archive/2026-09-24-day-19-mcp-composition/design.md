# Design

## Context

Мотивация и product scope — в [proposal](proposal.md). Основания: [Day 17 MCP spec](../../../specs/android-dependency-mcp/spec.md), [Day 17 experiment](../../../specs/first-mcp-tool-experiment/spec.md), [Day 18 service](../../../specs/dependency-watch-service/spec.md), [Day 18 experiment](../../../specs/dependency-watch-experiment/spec.md). Day 17 live получил 129 элементов, модель назвала 133; Day 18 live получил три snapshots по 130 элементов с правильным persisted aggregate. Это исторические наблюдения, не ожидаемое число версий Day 19.

Day 17 создаёт MCP/app в серверном модуле и публикует ровно один tool. Day 18 имеет отдельный `lookup.py`, но его entrypoint запускает scheduler и публикует ровно create/summary. Оба используют официальный `mcp==2.2.0`; backend уже сохраняет native Responses MCP items и различает ошибки и unknown invocation. Design нужен для согласования нового сервера, backend evidence, независимого чтения файла и проверок двух переходов.

## Goals / Non-Goals

**Goals:** наблюдать три отдельно вызванных tools одного сервера в одной auto-операции; сохранять полный исходный lookup между первым и вторым шагами; отделять правильность локального tool от правильности переданных ему данных; доказать содержимое файла независимым чтением.

**Non-Goals:** доказательство криптографической подлинности данных от модели, универсальное понимание произвольного prose, гарантированное выполнение цепочки моделью, автоматический retry при неопределённом результате. Product exclusions перечислены в proposal.

## Decisions

### 1. Отдельный runtime и ограниченное переиспользование lookup

Создать `day-19-mcp-composition/` со standalone requirements, небольшими модулями lookup/contracts/report/storage/MCP и тестами. Предпочесть ограниченную адаптацию существующего предметного lookup из Day 18 в изолированный модуль Day 19: перенести проверенный алгоритм и только необходимые coordinate/time helpers, сохранив ссылку на исходник и parity fixtures. Это тот же подход reuse логики, которым Day 18 отделил lookup Day 17; новую логику Google Maven не проектировать. Не импортировать `server.py`, `run.py`, scheduler или storage предыдущих дней. Не переносить весь `watch_models.py` ради двух типов.

Сохранить точные координаты (strict strings, 1–256 символов, действующие regex), фиксированный Google Maven origin/group-index URL, 15-second lookup deadline, 2 MiB upstream body limit, запрет redirects/DTD/entities, прежние normal/error outcomes и source order. HTTP transport и clock инъецируются. Адаптер Day 19 дополняет внутренний результат координатами и URL, сериализует UTC milliseconds как `YYYY-MM-DDTHH:MM:SS.sssZ`, генерируемый lookup UUID — lowercase canonical.

Альтернативы: импорт entrypoint запускает ненужный runtime; прямой cross-day import связывает deployment с расположением соседних папок и generic module names; общий package требует рефакторинга завершённых Days. Shared extraction не нужна для минимального scope. Если при реализации общий код всё же затрагивается, это требует согласованного обновления design/task scope и регрессии Days 17–18 без изменения их контрактов.

### 2. Три явных контракта

Все поля ниже обязательны, неизвестные поля запрещены на верхнем и вложенных уровнях; автоматические приведения типов, включая bool в int, trim и нормализация строк не допускаются. `source_url` обязан точно соответствовать `group_id`. Версии — непустые строки без whitespace; их порядок, повторы и написание сохраняются. На входе downstream tools `lookup_id` и `checked_at` должны уже иметь формат Day 19; эквивалентное переформатирование моделью является ошибкой переноса.

| Объект | Поля |
|---|---|
| `LookupResult` | `status`: found/group_not_found/artifact_not_found/no_versions; `group_id`, `artifact_id`; `versions`: полный string array; `source_url`; `checked_at`: UTC string milliseconds; `lookup_id`: canonical UUID string |
| `DependencyReport` | `schema_version`: strict integer 1; те же `status`, `group_id`, `artifact_id`, `source_url`, `checked_at`, `lookup_id`; `version_count`: strict integer >=0; `last_three`: string array длиной 0–3; `input_sha256`: lowercase 64-hex |
| `SaveReceipt` | `status`: saved; `lookup_id`; `file_id`: lowercase 64-hex; `sha256`: lowercase 64-hex, равный file_id; `bytes`: strict positive integer |

`get_google_maven_versions(group_id, artifact_id)` возвращает LookupResult. Только found имеет непустой versions; все остальные normal statuses имеют []. Lookup failure — безопасная tool execution error с category и lookup_id, а не LookupResult с пустым массивом.

`summarize_dependency_versions(lookup)` принимает весь LookupResult. Он копирует identity/status/source поля без изменения, считает `len(versions)` и `versions[-3:]`, добавляет schema_version и hash канонического входа. Нет network/LLM/storage доступа, сортировки, deduplication или semver. Для всех normal negatives count=0 и tail=[], но status сохраняет причину: это размер возвращённого списка, не утверждение об отсутствии публикаций во всех repositories.

`save_dependency_report(report)` принимает весь DependencyReport. Он проверяет schema, format и внутренние инварианты: tail length = min(count,3), found означает count>0, остальные statuses требуют count=0/tail=[]. Он не может пересчитать count или input_sha256 без исходного массива и не заявляет, что удостоверил lookup provenance. Нет нового lookup, генерации отчёта, чтения SQLite или автоматического исправления. Единственный сохраняемый content — канонический JSON принятого report.

Tool annotations: lookup — read-only/open-world; summarize — read-only/closed-world; save — state-changing, non-destructive, closed-world, idempotent для одинакового report. Аннотации не заменяют проверки. Text и structured result wrappers одного tool должны описывать один и тот же объект.

### 3. Канонические байты и ограниченная запись

Определить проектный формат C_v1(obj), без заявления совместимости с RFC JCS: JSON с лексикографически отсортированными object keys, без пробелов между полями (`separators=(",", ":")`), `ensure_ascii=True`, `allow_nan=False`, затем один LF; полученная строка кодируется UTF-8 без BOM. Объекты схемы содержат только строки, целые числа и массивы/объекты, без floats/null. Строки не подвергаются Unicode/time/UUID normalization; порядок arrays сохраняется. Это соответствует `json.dumps(..., sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"` на валидном объекте. Зафиксировать golden bytes и hashes тестами.

`input_sha256 = SHA256(C_v1(lookup))`; file bytes = C_v1(report); `file_id = sha256 = SHA256(file bytes)`, hex lowercase. Время сохранения и случайные IDs не входят в report/receipt; server events могут иметь свои timestamps. Повтор одного lookup даёт одинаковый report; повтор report даёт те же bytes/name. Новый upstream lookup получает новый lookup_id/checked_at и потому обычно другой файл.

VPS root: `/var/lib/day19/reports/`; локальные тесты задают temporary root через конфигурацию, не tool arguments. Basename полностью вычисляется сервером: `<file_id>.json`. В tool schema отсутствуют path/filename/directory/content. Валидированные координаты не используются как путь. Root принадлежит сервисному пользователю; root и target не должны перенаправлять запись через symlink. Ограничения размера HTTP body/объектов задаются явно, согласуются с полным payload на pre-live; превышение означает ошибку, не обрезание данных.

Сначала записать полный temporary file внутри root, flush/fsync, затем атомарно опубликовать без перезаписи другого содержимого. При существующем target сверить все bytes и вернуть тот же receipt только при совпадении. Прочитать опубликованные bytes до saved. Обязательный acceptance Day 19 не включает power-loss/crash-recovery матрицу или отдельное доказательство directory durability. File permission — только сервисному пользователю (UMask 0077); root вне release tree. Ошибка permissions/disk/full write/readback/collision возвращает безопасную категорию, не saved. При ошибке после публикации факт файла может быть неизвестен клиенту; не обещать его отсутствия. До публикации не должно оставаться частичного final JSON. Незавершённый temp не считается результатом.

Альтернативы: UUID filename плодит дубли при повторе; fixed filename перезаписывает evidence; filename из coordinates/prompt расширяет поверхность записи; raw text content позволяет сохранять prose вместо отчёта. Content hash даёт простую идемпотентность. Он не служит подписью, ACL или доказательством происхождения.

### 4. Orchestration и минимальная точка запуска

| Вариант | Кто выбирает порядок и аргументы | Назначение |
|---|---|---|
| Фиксированная цепочка MCP client | Программный код выполняет три `call_tool` и копирует JSON | Offline baseline для contracts, tools и storage |
| Один native Responses request | Модель выбирает три tools и переносит полные результаты | Основной Day 19 live |

Рекомендован второй вариант для учебной цели; первый надёжнее для фиксированной прикладной задачи, но не доказывает выбор инструментов моделью. Один pipeline tool с тремя внутренними функциями исключён. MCP server исполняет отдельные операции; автоматического server-side workflow нет. Модель выбирает имя/arguments; Responses выполняет remote MCP и возвращает результат в её контекст. Backend только запускает операцию, сохраняет evidence и проверяет его; он не подставляет следующий payload вместо модели.

Предлагаемая operation: `POST /api/v1/mcp-composition/run`, вход `{prompt: nonblank string}` с существующим пределом 12000 символов. Локальный CLI launcher делает один POST и показывает model text отдельно от verifier facts. Это одно пользовательское действие; Android экран/navigation не меняются. Нет forced mode, action selectors или отдельной кнопки для каждого шага.

Изолированный service сохраняет alias `gpt-5.6`, `reasoning.effort=none`, `store=false`, `max_retries=0`, один `responses.create`, `tool_choice="auto"`; один server_label `dependency_composition`, server URL из `DAY19_MCP_SERVER_URL`, native `authorization` из `DAY19_MCP_TOKEN`, allowlist ровно трёх имён, `require_approval="never"` для явно запрошенной ограниченной записи. Finite deadline и max_output_tokens — Day 19-specific конфигурация, выбираемая и фиксируемая до live по gate; таймауты старых Days не менять. SDK возможности/совместимость параметров проверить по закреплённым runtime versions при реализации. Основание native MCP: [официальная документация Responses](https://developers.openai.com/api/docs/guides/tools-connectors-mcp).

Инструкции модели: получить результат, целиком передать его в summarize, целиком передать report в save; не вычислять hash/count самостоятельно, не повторять tools и при execution error остановиться. Эти инструкции не являются гарантией. Ноль, два, четыре calls или вызов save до summarize — наблюдаемый failure, без forced fallback. Наличие трёх tools в discovery не гарантирует три вызова.

Для проверяемой точности final text принять фиксированный формат успешного ответа: один JSON object без Markdown с ровно `group_id`, `artifact_id`, `status`, `version_count`, `last_three`, `file_id`. Это проектное решение для review: свободный русский prose не нужен для проверки композиции и потребовал бы ручного semantic judge. Backend хранит исходный output_text; verifier разбирает его без repair и сравнивает все факты с независимо ожидаемым report/file_id. Неверный формат имеет отдельную причину `final_format_mismatch`, неверный факт — `final_fact_mismatch`. Verdict определяется доступными фактами независимо от chain: например, extra call проваливает выбор, но не обязательно точность final. Доказанное ложное утверждение получает FAIL; при недостатке фактов успешный summary получает NOT_PROVEN. Для PASS нужно также независимое подтверждение ожидаемого файла. Текст ошибки сохраняется без заявления о проверке произвольного prose. LLM judge не используется.

### 5. Evidence и независимый verifier

Перед provider request резервировать operation_id и безопасный attempt record. Недоступное evidence storage — not_sent. Сохранять request config без token, requested/resolved model при наличии, provider status/error, response_id, исходные ordered output/MCP items и отдельно raw final_text. Не выдумывать отсутствующие fields. Каждому call сохранять id, server_label, name, исходные arguments/output strings, status/error; typed projection не заменяет raw. На timeout invocation=unknown, без автоматического продолжения. CLI не переиспользует уже отправленный attempt directory.

Verifier — отдельный локальный модуль/CLI, получает immutable operation evidence, server event export и независимо прочитанный file artifact. Он не вызывает tools/OpenAI, не импортирует production summarize/save/renderer для получения ожидаемого результата и не пишет в report root. Дублирование короткой формулы и C_v1 в проверяющем коде оправдано независимостью; golden fixtures фиксируют bytes/hash. Повторный запуск verifier читает те же входы и не меняет original evidence; вывод — отдельный verdict artifact.

Разбор JSON отвергает duplicate keys, невалидные числа, неверные types и extra fields. Для MCP wrappers допускаются документированные и offline-проверенные structured/text/raw JSON representations. Если обе representations присутствуют, их значения обязаны совпадать. Wrapper снимается, но значения не приводятся к типам, строки не нормализуются. Object key order и внешнее JSON whitespace не влияют на equality; array order, все strings, типы и количество elements — влияют.

Обозначения: L — фактический output первого call; A2 — actual arguments summarize; R2 — actual output summarize; A3 — actual arguments save; S — actual receipt; E — report, независимо построенный из L. Проверки:

1. Проверить все calls без отбора удобной subsequence: ровно lookup, summarize, save на одном ожидаемом server. Координаты первого call равны `androidx.core:core-ktx` принятого live prompt; identity/source результата соответствуют actual arguments.
2. `A2 == {lookup: L}` и `A3 == {report: R2}` по полным JSON objects; сохранить отдельный verdict каждой границы. Не ограничиваться counts/tail/hash.
3. `R2 == E`; отдельно вычислить ожидаемый output summarize из его actual A2.lookup, чтобы отличить исправный tool на испорченном входе от ошибки самого tool.
4. Проверить S против actual A3.report: lookup_id, hash, byte count. Затем независимо прочитанные bytes сравнить и с C_v1(A3.report), и с C_v1(E). Первое устанавливает правильность записи полученного объекта, второе — правильность итогового артефакта всей цепочки.
5. Сопоставить lookup_id с реальным Google Maven log; безопасные server events содержат invocation_id, tool name, lookup_id при наличии, input/output hashes, start/end и outcome. Порядок Responses items дополнить серверными start/end на одном процессе/часах: summarize начинает работу после завершения lookup, save — после summarize. Provider call_id серверу не приписывать, если SDK его не сообщает; связывать по tool/lookup_id/hashes и отдельному invocation_id.
6. Сравнить raw final JSON с фактами E и ожидаемым file_id, независимо от текста receipt. Не заменить ответ модели собственным правильным ответом.

Independent file read выполняется после live отдельным read-only операторским collector на VPS: root известен заранее, допускается только 64-hex file_id, без model path interpolation. Collector не зовёт save/serialize, читает bytes с диска и сохраняет локальную копию либо lossless base64 export вместе с size/hash/read timestamp, endpoint/revision/operation association. Отказ чтения даёт NOT_PROVEN. Readback внутри save полезен, но не заменяет этот независимый источник. Это не четвёртый model tool и не новая generation. При отсутствии достоверного receipt возможны read-only диагностика по журналу и фиксация unknown; нельзя создать недостающий файл или повторить цепочку ради доказательства.

| Verdict | PASS требует |
|---|---|
| `tool_execution` | Все три tool завершены без execution errors, их outputs соответствуют actual inputs и контрактам |
| `selection_order` | Ровно три нужных calls, нужные координаты/сервер, подтверждённая последовательность без extra calls |
| `data_transfer` | Обе границы полных JSON objects точны; sub-verdicts lookup_to_summary и summary_to_save |
| `report_correctness` | R2 целиком равен E из исходного L |
| `file_persistence` | Независимо прочитанные bytes и S соответствуют C_v1(E), файл связан с этой попыткой |
| `final_text_accuracy` | Raw final JSON имеет нужный формат, факты из исходного lookup и подтверждённого ожидаемого файла; оценивается независимо от selection verdict |

Значения — PASS/FAIL/NOT_PROVEN с reason и ссылками на evidence. Известное расхождение — FAIL, недоступное необходимое evidence — NOT_PROVEN. `chain` — конъюнкция первых пяти: любой FAIL даёт FAIL, иначе любой NOT_PROVEN даёт NOT_PROVEN. Final text не входит в chain; отдельно `full_acceptance` основного positive live требует chain=PASS, final_text_accuracy=PASS и L.status=found. Provider completed не заменяет verdict; incomplete с полной доказанной цепочкой не отменяет её, но отсутствующий final не получает PASS. Normal negative lookup корректен по contracts, однако основной positive live для core-ktx отдельно требует found; неожиданный negative фиксируется как невыполненный positive scenario, без переименования его в network error.

### 6. Gates и acceptance

Порядок этапов: offline → deployment/readiness → pre-live → один live. Gates фиксируют техническую готовность; переход к следующему этапу в рамках уже порученной работы не требует нового разрешения, если его не требуют AGENTS.md или явное указание пользователя. Текущий запрос ограничен planning artifacts и не запускает эти этапы.

**Offline:** discovery ровно трёх tools, отдельные `client.call_tool` каждого шага, MockTransport Google Maven и temporary reports root. Проверить переданные argument objects, output wrappers, hash/bytes, один upstream request только на lookup, отсутствие scheduler/SQLite/OpenAI и network у остальных tools. Golden cases: несортированные версии/дубликаты/0–2 элемента, normal negatives; errors: coordinates/schema/type/status/source/time/hash, HTTP/XML/network/body-limit, базовые файловые проверки ограничения пути (включая symlink escape), атомарной публикации, последовательного повторного save и одной воспроизводимой ошибки записи до публикации без saved/частичного final file. Успешную запись подтвердить независимым чтением и сравнением bytes/hash/receipt; отдельная матрица permissions/disk-full/readback failures не обязательна. Mutation tests verifier: изменить средний элемент при том же count/tail, порядок/дубликат, coords/lookup_id/time, report, hash, receipt и file bytes; пропустить/переставить/добавить call. Включить случай schema-valid forged report: save может работать правильно, но chain verifier обязан обнаружить divergence. Проверить ошибочный final при правильном файле, malformed/partial provider output и secret sentinel. Запускать suites Days 17–18 при общем refactor; без него parity fixtures и узкие backend integration regressions подтверждают изоляцию.

**Deployment/readiness:** после offline развернуть Day 19 и подтвердить actual deployed manifest, versions/config, trusted HTTPS, auth/discovery, изолированный writable root и неизменность старых routes. Эта стадия не выполняет model generation.

**Pre-live:** после deployment/readiness отдельный direct lookup целевого artifact без модели даёт свежий полный payload для измерения; сохранить его как readiness, не включать в три calls live. Измерить UTF-8 bytes и tokens фактических L, `{lookup:L}`, ожидаемых R, `{report:R}`, schemas/prompt/final envelope. Оценивать не только input context, но и генерируемые моделью arguments плюс final output; зафиксировать tokenizer/version либо консервативный upper bound и неопределённость, выбранный max_output_tokens, запас и deadline. Не выдавать estimate за provider billing. Offline fixtures с таким размером должны пройти без truncation. Old Day 17 limit=1200 не переносить автоматически.

Если нет подтверждённого запаса под полный список, live блокируется. Сначала уточнить бюджет/конфигурацию без generation; если требуется ограничение/пагинация/handles вместо полного массива, явно пересмотреть proposal/specs/design/tasks и acceptance до live. Нельзя молча обрезать результат или выбрать другой artifact. Preflight snapshot не подставляется в live: tool снова получает данные, а actual live payload size сохраняется отдельно. Изменение Google Maven между preflight и live — допустимый риск; при превышении лимита сохраняется failure/incomplete, без repair.

**Live:** один явный запуск launcher, один POST, один Responses request, один сервер и allowlist трёх tools, auto. Пример prompt: «Получи версии androidx.core:core-ktx из Google Maven, вычисли количество и три последних элемента в порядке источника и сохрани JSON-отчёт на сервере». Final format задан общими instructions. Записать факт dispatch, request configuration/budget, ordered raw MCP items, все errors/IDs, server events, независимый file read и все verdicts. Новых пробных generations, forced continuation, automatic retries или manual correction внутри попытки нет. При zero/extra/wrong calls сохранить исходный failure. Не заменять live offline-цепочкой, scheduler history или заранее созданным файлом. Повторная попытка выходит за scope одного live и оформляется как новый явно запрошенный эксперимент с новым ID; она не является скрытым шагом текущего acceptance.

### 7. Deployment, документы и минимальные зависимости

На VPS отдельный process/user `day19`, loopback port (предлагается 8019), systemd state directory `day19`, releases `/opt/day19/releases/<revision>` и current symlink. Отдельный конфиг `DAY19_MCP_*` и `DAY19_REPORTS_DIR`; защищённый environment, без OpenAI key на VPS. Внешний HTTPS URL использует отдельный hostname с `/mcp`, совместимый с текущей backend URL validation; hostname выбирается при deployment и не захардкоживается в tools. Caddy добавляет route/host Day 19 с сохранением Day 18; не применять повторно Day 18 bootstrap. Использовать Bearer-auth до discovery/dispatch и существующий подход Host/Origin protection. Проверить локальный health и права root, не называя health доказательством OpenAI/Maven readiness.

Новый Day README создаётся при добавлении runtime directory, с тремя русскими разделами и честной отметкой «live не проведён» до попытки; тогда же root README получает упорядоченную ссылку. Настройка backend/launcher/deployment и проверок — в backend/scripts README; Android документацию не менять без изменения Android. Архивные evidence Days 17–18 сохраняются.

## Risks / Trade-offs

- [Полный список увеличивает стоимость и вероятность ошибки копирования] -> измерение фактического payload до live, конечные budget/deadline, полное сравнение; без скрытого truncation.
- [Модель пропустит, повторит или переставит tool] -> сохранить все calls, отдельный selection verdict; prompt/allowlist не считать гарантией.
- [Schema-valid подмена данных пройдёт save] -> независимый verifier сравнивает с исходным L; hash не удостоверяет origin. Server-side signed handles/cache добавляют состояние и не входят в scope.
- [Один и тот же bug в обработке и проверке] -> verifier не вызывает production processing/serialization helpers, golden expected bytes и mutation cases.
- [Lost response после сохранения] -> unknown invocation, независимое чтение/журнал при наличии identity; отсутствие response не означает отсутствие файла; автоматического retry нет.
- [Выявлен риск конкурентной записи или восстановления после сбоя] -> добавить адресную проверку конкретного риска и зафиксировать основание; конкурентные save, kill/restart, crash-recovery и расширенная fault-injection матрица не являются обязательным gate по умолчанию.
- [Отрицательный результат перепутан с технической ошибкой] -> status сохранён во всех объектах, техническая ошибка не имеет normal LookupResult; positive live verdict отдельный.
- [Дублированный lookup код может разойтись с Day 18] -> ограниченная адаптация с source reference/parity fixtures; никакого общего framework ради этого дня.
- [JSON final проще свободного prose] -> явно ограничить вывод: эксперимент оценивает точность перечисленных фактов, не качество произвольного рассказа.
- [Недоказанная последовательность по одному порядку items] -> серверные start/end/hash events; недостаток evidence даёт NOT_PROVEN, не выдуманные timings.

## Migration Plan

1. Review planning artifacts. Текущий запрос ограничен planning: код, VPS и runtime configuration не меняются. Дальнейшая работа выполняется в объёме пользовательского поручения и по AGENTS.md, без дополнительных разрешений на каждый технический этап.
2. Реализовать изолированный service, backend/launcher/verifier и пройти offline gate. Старые Days доступны без Day 19 environment. Main specs не синхронизируются в planning.
3. Deployment/readiness: после offline развернуть Day 19, сверить manifest, endpoint/auth и reports root. Не рестартовать Day 18 ради Day 19 и не переносить его SQLite.
4. Pre-live: после deployment/readiness измерить полный payload и подтвердить response budget/deadline без model generation; при недостаточном запасе остановить переход к live.
5. После pre-live выполнить один live: auto-попытку, независимое чтение и оценку. Записать фактические PASS/FAIL/NOT_PROVEN, не требовать успешного повторения для оформления наблюдения.
6. Обновить evidence/README по фактам. Finish/archive/commit/push — отдельный запрос пользователя, не действие этого proposal.

Rollback будущего deployment: отключить только Day 19 process/route/config, сохранить reports и evidence; старые endpoints и данные не мигрируются. Не удалять reports при замене release.

## Open Questions

- Точный public hostname и свободный loopback port подтверждаются на этапе deployment/readiness; контракт — отдельный HTTPS `/mcp` и отсутствие конфликта со старыми routes.
- Конкретные Day 19 max_output_tokens/deadline фиксируются по измерению полного payload и доступным лимитам выбранной модели до live; невозможность вместить полный список блокирует gate, а не меняет контракт автоматически.
