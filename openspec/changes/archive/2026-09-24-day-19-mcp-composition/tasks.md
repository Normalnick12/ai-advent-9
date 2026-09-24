# Tasks

Порядок исполнения: offline → deployment/readiness → pre-live → один live. Переходы между техническими gates не требуют дополнительных разрешений в рамках уже порученной работы, если их не требуют AGENTS.md или явные указания пользователя. Реализация и последовательное прохождение gates поручены пользователем; finish/archive/commit/push исключены.

## 1. Изолированный runtime и полный lookup

- [x] 1.1 На этапе реализации создать `day-19-mcp-composition/` с изолированными runtime/dev requirements и модулями lookup/contracts/report/storage/MCP; проверить syntax/import без создания scheduler, SQLite или запуска серверных entrypoints Days 17–18.
- [x] 1.2 Ограниченно адаптировать проверенную lookup-логику Day 18 с source reference, injectable transport/clock и прежними safety/error semantics; parity fixtures должны подтвердить source order/duplicates, все normal negatives, invalid coordinates, deadline/network/HTTP/XML/2 MiB failures и отсутствие redirects/retries.
- [x] 1.3 Создать краткий Day README с тремя русскими разделами и отметкой «live не проведён», добавить упорядоченную относительную ссылку в корневой README; проверить существование target, отсутствие дубликатов и ссылок на несуществующий Android экран.

## 2. Контракты, deterministic report и file storage

- [x] 2.1 Реализовать строгие LookupResult/DependencyReport/SaveReceipt и schemas трёх входов; тестами проверить exact fields, запрет extras/coercion/bool-as-int, status/list/count/tail invariants, source URL, canonical UTC milliseconds/UUID и 64-hex hashes, включая nested path/filename/directory/content.
- [x] 2.2 Реализовать C_v1 и summarize с len/last-three/input_sha256; golden bytes/hash tests должны покрывать escaping, object key order, array order/duplicates, 0–2 версии и negative statuses, повторяемость и отсутствие network/LLM/storage side effects.
- [x] 2.3 Реализовать save в configurable fixed root с server-generated hash filename, atomic publication/readback, exact receipt и идемпотентным повтором; temporary-directory tests должны проверить ограничение пути (включая symlink escape), атомарную публикацию, последовательный повтор с тем же файлом/receipt, одну воспроизводимую ошибку записи до публикации без saved/частичного final file и независимое чтение actual bytes/hash/receipt. Дополнительные concurrency/crash-recovery и отдельные storage-failure tests добавлять по выявленному риску с записанным основанием.

## 3. Три MCP tools и server evidence

- [x] 3.1 Опубликовать ровно lookup/summarize/save через отдельный Day 19 server и закреплённый SDK; MCP client tests должны подтвердить discovery/input/output schemas, annotations, actual structured/text wrappers и три отдельных call_tool, без pipeline tool или неявного chaining.
- [x] 3.2 Добавить Bearer-auth до discovery/dispatch, Host/Origin protection, safe health и отдельный runtime без scheduler; локальные HTTP tests должны подтвердить 401 без/с неверным token, успех с synthetic token и отсутствие side effects/секретов в ошибках.
- [x] 3.3 Добавить безопасные start/end/outcome server events с invocation_id/tool/lookup_id и input/output hashes плюс upstream lookup correlation; tests должны подтвердить возможность проверки последовательности, уникальность фактических invocations, отсутствие выдуманного provider call_id и redaction synthetic secret sentinel.

## 4. Одна backend auto-операция и неизменяемое evidence

- [x] 4.1 Добавить изолированные Day 19 DTO/service/route `POST /api/v1/mcp-composition/run` и environment settings; request fixtures должны подтвердить один native server, ровно три allowed_tools, auto, alias gpt-5.6, native authorization, store=false/max_retries=0 и configuration error без запроса/влияния на старые Days.
- [x] 4.2 Добавить инструкции явной передачи полных объектов и фиксированного final JSON; fixture-тестами проверить один responses.create, отсутствие forced steps/retry/repair/argument substitution, сохранение zero/extra/wrong calls, partial/refusal/error response и unknown при timeout.
- [x] 4.3 Добавить безопасную резервируемую attempt запись и сохранение исходных ordered Responses/MCP items, IDs, raw arguments/outputs/errors и final_text отдельно от typed/verdict data; тестами проверить not_sent при недоступном evidence storage, отсутствие секретов и отсутствие потери предшествующих/неуспешных calls.
- [x] 4.4 Добавить минимальный локальный CLI launcher с одним POST и защитой от повторного использования отправленного attempt; mock backend test должен подтвердить одну отправку, отсутствие automatic continuation и отдельный вывод raw final/evidence location без нового Android экрана.

## 5. Независимый verifier и offline gate

- [x] 5.1 Реализовать standalone verifier без вызовов production summarize/save/renderer, tools или модели: strict JSON/wrapper parsing, оба полных boundary comparisons, независимый expected report и оценка actual-input tool correctness; golden/mutation tests должны обнаруживать замену средней версии при прежнем count/tail, identity/time/source, порядок/дубликаты, противоречивые wrappers и schema-valid forged report.
- [x] 5.2 Добавить сравнение receipt и independently read bytes как с actual save input, так и с expected report, раздельные verdicts/reasons и chain/full-acceptance reduction; tests должны покрыть повреждённый/отсутствующий файл, false hash/size, zero/extra/reordered calls, недостаточные server events, normal negative, incomplete и unknown без ложного PASS.
- [x] 5.3 Добавить отдельную оценку final JSON без repair/LLM judge; fixtures должны подтвердить chain PASS с неверным final count, format mismatch, NOT_PROVEN при недостатке фактов и точный final при selection FAIL из-за лишнего call, не смешивая вердикты.
- [x] 5.4 Подготовить read-only VPS file/event collector с fixed root и validated 64-hex ID, экспортом actual bytes/size/hash/read time/revision association; offline temporary-file tests должны доказать lossless export, path validation, отсутствие save/serialization вместо чтения и отсутствие секретов. На этом шаге VPS не трогать.
- [x] 5.5 Выполнить целую offline цепочку через три отдельных MCP client calls с MockTransport и временным root, затем независимый verifier; проверить точные arguments/outputs, один upstream lookup, zero network у summarize/save, file bytes, существенные input errors и базовые файловые проверки из 2.3, без реальных Google Maven/OpenAI/VPS calls.
- [x] 5.6 Выполнить focused Day 19 service/backend/launcher/verifier suites и узкие проверки изоляции backend Days 17–18; если затронут общий код, выполнить все соответствующие lookup/MCP/backend regression suites Days 17–18. Сохранить команды/результаты, проверить синтаксис, scoped diff/секреты и strict OpenSpec validation; Android build/UI не запускать при неизменённом Android.

## 6. Deployment artifacts, deployment/readiness и pre-live

- [x] 6.1 Подготовить отдельные Day 19 runtime/systemd/Caddy templates и конфигурацию без секретов: собственный process/user, loopback port, HTTPS hostname с /mcp, persistent `/var/lib/day19/reports/`, release separation и rollback; проверить синтаксис/пути и сохранение прежних routes без выполнения deployment.
- [x] 6.2 Описать backend/CLI/verifier/collector configuration и команды, auth, evidence layout, pre-live sizing, storage limits и rollback в backend/scripts README; проверить ссылки, что Day README остаётся кратким, root link существует, credentials и команды скрытого repeat отсутствуют.
- [x] 6.3 Deployment/readiness: после успешного offline gate развернуть Day 19 snapshot на VPS; сверить actual manifest/dependency versions, authenticated discovery ровно трёх tools, TLS/Host protection и writable persistent root, подтвердить неизменность старых endpoints без запуска watch/reboot/миграции SQLite.
- [x] 6.4 Pre-live: после deployment/readiness (6.3) без model generation выполнить отдельный preflight lookup core-ktx, сохранить полный snapshot как readiness, измерить UTF-8 bytes и token estimate lookup/downstream arguments/report/schemas/prompt/final envelope; проверить offline перенос payload этого размера, зафиксировать метод оценки, uncertainty, model limits, max_output_tokens/deadline и запас. Gate блокируется при недостаточном бюджете; сокращение списка/handles требует явного изменения proposal/specs/design/tasks/acceptance до live.

## 7. Одна будущая live-попытка и review результата

- [x] 7.1 После успешного pre-live gate (6.4) выполнить один live: одну явную отправку через launcher для androidx.core:core-ktx; сохранить dispatch marker/configuration, один Responses request, все actual MCP items/errors/IDs, payload sizes и raw final text без forced steps/retry/repair. Завершённый неуспешный запрос фиксировать как попытку, не повторять для закрытия task.
- [x] 7.2 Выполнить отдельный read-only сбор server events и фактического файла этой попытки, затем verifier; сохранить bytes/export и verdict artifact для tools/order/обоих transitions/report/file/final text. PASS цепочки требует ровно трёх последовательных calls, двух точных переходов и правильного файла; positive full acceptance дополнительно требует found и точного final. Недостаток evidence оформить NOT_PROVEN, несовпадения — FAIL, без создания недостающего файла или скрытого повторного запуска.
- [x] 7.3 Подготовить краткий live-result с фактической revision, gates, verdicts и ограничениями одной попытки; обновить Day README по проверенным фактам и перепроверить root link/секреты. Проверить, что failure не назван успешным acceptance, offline/scheduler history не выданы за live, а исходные evidence не исправлены; finish/archive/commit/push выполнять только по отдельному запросу.

## Состояние выполнения на 2026-09-24

Выполнено 21/26 задач. Offline gate: 94 Day 19 + 85 backend/integration + 44 Day 18
+ 57 Day 17 tests; fixed three-call MCP baseline chain=PASS; strict validation PASS.
Результаты: [offline-gate.json](../../../../day-19-mcp-composition/evidence/offline-gate.json).

Задача 6.3 BLOCKED: read-only SSH к aiadvent@132.243.120.220 завершился
`Connection timed out during banner exchange` до аутентификации/выполнения команд.
VPS не изменён, старые endpoints ещё не проверены; pre-live/live не запускались.
Продолжение начинается с восстановления SSH и deployment/readiness, не с модели.
[Диагностика](../../../../day-19-mcp-composition/evidence/deployment-readiness.json).

### Повторная SSH-диагностика 2026-09-24, 13:20:58–13:21:18 UTC

По новому поручению выполнено ровно одно подключение: ConnectionAttempts=1,
ConnectTimeout=20, BatchMode=yes, IdentitiesOnly=yes, StrictHostKeyChecking=yes,
verbose logging; использован прежний подтверждённый ключ ssh-agent.
TCP установлен, локальный SSH banner отправлен, удалённый banner не получен.
Exit 255 через 20.022 s; host-key verification/authentication/whoami не начались.
Причина на сервере не доказана; нужен read-only осмотр SSH listener/service/logs
через консоль FirstVDS. Ключи, known_hosts, SSH/UFW и VPS не изменены.

Offline PASS не отменяется. Прогресс остаётся 21/26; 6.3 BLOCKED, 6.4 и 7.1–7.3
не начаты. Live attempts=0; live-вердикты NOT_PROVEN из-за отсутствия попытки,
а не результат запуска verifier. История первой блокировки сохранена.
[Новая диагностика](../../../../day-19-mcp-composition/evidence/deployment-readiness-20260924T132058Z.json).

### Продолжение 2026-09-24, 13:40 UTC: SSH PASS, sudo BLOCKED

Одна ограниченная SSH-проверка по IP с прежним agent key прошла за 1.169 s:
host key проверен, publickey authentication успешна, whoami=aiadvent, exit 0.
Read-only inventory подтвердил Day 18 active, PID 1763, release 5b11f8d9e5a87a25,
loopback 8018, свободный 8019 и прежний Caddy route. HTTPS readiness ещё не проверена.

Новый blocker 6.3: sudo -n -l требует интерактивный пароль. До deployment остановлено;
snapshot не передан, VPS/SSH/Day 18 не изменены. Runtime hashes не изменились,
offline 280 tests/PASS переиспользован без повторного прогона. Выполнено 21/26,
открыты 6.3, 6.4, 7.1–7.3. Pre-live/live не запускались, live attempts=0.

[Evidence](../../../../day-19-mcp-composition/evidence/deployment-readiness-20260924T134029Z.json).
Подготовлены [интерактивный deployment handoff](../../../../day-19-mcp-composition/DEPLOYMENT-HANDOFF.md)
и [видео-инструкция](../../../../day-19-mcp-composition/VIDEO.md). Это не завершение 7.3:
live-result появится только после фактической попытки. Finish/archive/commit/push не выполнялись.

### Подготовка snapshot без sudo — 2026-09-24

По отдельному поручению проверен install.py и выполнена только подготовка:
archive SHA-256/DNS PASS, staging создан, archive передан по SSH на IP,
remote SHA-256 PASS, распаковка и все 17 manifest hashes PASS.
Распакованный install.py совпадает с проверенным исходником (SHA-256 cc1f52adac66e19c26cfa042f3da551b33000ba1e6377465c822205134dce7b4).
Остановлено до installer; sudo/system configuration/services не менялись.
На VPS изменён только /home/aiadvent/day19-deploy/def6cc340e666afd.
Задача 6.3 остаётся открытой, прогресс 21/26; readiness/pre-live/live ещё не выполнены.
[Evidence подготовки](../../../../day-19-mcp-composition/evidence/preparation-20260924.json).

### Частичная установка и исправление Caddy — 2026-09-24, после 14:09 UTC

Оператор выполнил старый installer: Day 19 active на loopback 8019, release
`def6cc340e666afd`; validation Caddy упала до публикации route. Read-only inspection:
Day 18 PID 1763 прежний, HTTPS health 200, discovery двух tools; активный Caddyfile
равен прежнему backup. Причина — отсутствующая у installer переменная
DAY18_MCP_PUBLIC_HOST из systemd Environment Caddy, а не изменение Day 18.

Исправлен исходный installer: явное окружение Caddy, validation до создания ресурсов,
защищённое Caddy-only продолжение частичной установки. 19 focused tests PASS;
4 read-only caddy adapt сценария PASS, включая существующий глобальный блок.
Новый локальный snapshot `2da85c77bb4be5e0` проверен по всем 17 hashes/bytes;
старый архив не перезаписан. Runtime не изменён, 280 offline tests не повторялись.

6.3 остаётся открытой: новый installer не передан/не применён, публичный readiness
не выполнен; metadata reports ожидает read-only sudo stat от оператора. Агент sudo,
reload, рестарты и live не выполнял. По явному поручению остановка перед ручным
root-этапом; это не новое универсальное требование разрешения между gates.
Прогресс 21/26, pre-live/live NOT_STARTED, attempts=0, live verdicts NOT_PROVEN.
[Evidence](../../../../day-19-mcp-composition/evidence/caddy-recovery-20260924.json),
[безопасное продолжение](../../../../day-19-mcp-composition/DEPLOYMENT-HANDOFF.md).

### Подготовка исправленного snapshot — 2026-09-24, 14:39–14:41 UTC

Пользователь подтвердил directories day19:day19/700 для state и reports.
Новый snapshot `2da85c77bb4be5e0` передан в отдельный staging и распакован:
`/home/aiadvent/day19-deploy/2da85c77bb4be5e0/source`.
Local/remote SHA-256 совпали; все 17 files/manifest, отсутствие посторонних
файлов/symlinks и Python syntax проверены без выполнения installer. DNS PASS,
Day 18 HTTPS 200, прежние PIDs; current/Caddyfile/backup/старый архив сохранены.
Агент sudo/installer/Caddy continuation/live не запускал. Следующий шаг — ручной
Caddy-only resume из исправленного snapshot, команда приведена в handoff.
6.3 остаётся открытой; прогресс 21/26, pre-live/live NOT_STARTED, attempts=0.
[Evidence](../../../../day-19-mcp-composition/evidence/caddy-fix-staging-20260924.json).

### После ручного Caddy-only resume — 2026-09-24, 14:49 UTC

Оператор сообщил exit 0, mode=caddy-only, day18_restarted=false. Агент подтвердил
runtime `def6cc340e666afd`, installer `2da85c77bb4be5e0`, все deployed manifest
hashes и packages. Caddyfile равен resume candidate и сохраняет исходный Day 18
config; backup цел. PID Day 18=1763, Day 19=5865 прежние. TLS trusted, HTTPS health
200; missing/invalid auth=401; discovery ровно трёх tools; чужие Host=421/Origin=403.
Day 18 HTTPS health=200 и discovery прежних двух tools.

6.3 BLOCKED: `sudo -n -u day19 ... deploy/readiness.py` завершился exit 1,
`sudo: a password is required`. Readiness script не стартовал, фактическая
write/read проверка от day19 не выполнена. Права 700, подтверждённые оператором,
не засчитаны вместо неё. Нужен ручной запуск readiness в интерактивном терминале.

По stop-on-gate-failure pre-live lookup, sizing и live НЕ начаты. Live attempts=0,
все live verdicts NOT_PROVEN из-за отсутствия попытки; verifier не запускался.
Offline 280 PASS переиспользован. Прогресс 21/26, 6.3 остаётся открытой;
6.4 и 7.1–7.3 не выполнены. Finish/archive/commit/push не выполнялись.
[Evidence](../../../../day-19-mcp-composition/evidence/readiness-after-resume-20260924T144933Z.json).

### Readiness gate PASS — операторский результат 2026-09-24, 14:54 UTC

Полный stdout readiness.py от day19 сохранён побайтно; JSON выделен отдельно,
строка закрытия SSH осталась в raw attachment. Exit 0 подтверждён пользователем.
Manifest/packages/schemas совпадают с независимым осмотром 14:49 UTC; TLS/auth/Host/Origin
PASS, reports uid=994/mode=0700/writable=true. Вместе с сохранностью Day 18 это
закрывает 6.3. Runtime def6cc340e666afd, installer 2da85c77bb4be5e0. Прогресс 22/26.
[Gate evidence](../../../../day-19-mcp-composition/evidence/readiness-gate-20260924.json).

### Pre-live gate PASS — 2026-09-24

Один readiness lookup core-ktx получил 130 версий; полный lookup 2079 canonical
UTF-8 bytes, downstream arguments 2090/426 bytes. Offline three-call control с этим
полным списком chain PASS. Бюджет: generated upper bound 3892, required with margin
11880, max_output_tokens=16384; context estimate=67162, deadline=600s, launcher=660s.
Лимиты/alias/none/MCP сверены по актуальной официальной странице gpt-5.6-sol.
Backend запущен через dev.ps1 с secrets только в окружении процесса, health/route PASS.
Оба gates 6.3/6.4 PASS, прогресс 23/26; до этой записи model requests=0.
[Pre-live evidence](../../../../day-19-mcp-composition/evidence/prelive-gate-20260924.json).

### Единственная live-попытка отправлена и получена — 2026-09-24

Operation 085e5b0a-863f-4a62-abd9-f62359a2393d: один launcher POST, один Responses
request, auto и исходный pre-live config. Native response/attempt/operation/dispatch
сохранены без изменения. Provider completed; три MCP calls наблюдаются. Это закрывает
7.1 как выполнение попытки, не доказывает ещё chain/file acceptance. Повторов нет.
Прогресс 24/26; 7.2 независимая проверка и 7.3 итог остаются открытыми.

### Post-live независимая проверка — BLOCKED, 2026-09-24

Native trace сохранена целиком. Model resolved gpt-5.6-sol, provider completed;
input/output tokens=3849/1419. Lookup fresh (не preflight), 130 версий. Проверены
actual arguments/outputs: lookup_to_summary PASS, summary_to_save PASS,
report_correctness PASS, tool_execution PASS относительно actual inputs/receipt.
Final JSON фактически совпадает с ожидаемыми report/receipt facts.

Непривилегированный collector вернул [] server events; причина не доказана.
По stop-on-blocker чтение файла не запускалось. Вердикты selection_order,
file_persistence, final_text_accuracy, chain/full_acceptance NOT_PROVEN;
receipt о 415 bytes не засчитан как independent file read. Модель не повторялась.
Нужен операторский read-only export events+file по handoff, затем новый verifier
artifact на той же operation. Исходные response и verdict-initial неизменны.

7.2 остаётся открытой из-за недостающего независимого evidence; 7.3 — до итогового
review, README/VIDEO сейчас отражают только промежуточные доказанные факты.
Прогресс 24/26. Finish/archive/commit/push не выполнялись.
[Вердикты](../../../../day-19-mcp-composition/evidence/live-20260924/verdict-initial.json),
[блокировка](../../../../day-19-mcp-composition/evidence/live-20260924/collection.json).

### Окончательная независимая проверка той же попытки — 2026-09-24

Операторский term.txt сохранён побайтно отдельным evidence; SHA-256:
47a47906a68c59d9bcebe5ca8bd7624af45543174eb5bf10a50f7491f1ed8c40.
Семь server events и независимо прочитанные 415 bytes связаны с прежней operation
085e5b0a-863f-4a62-abd9-f62359a2393d, lookup 27d5554f-eb85-489b-b336-60bc32cb1578,
runtime def6cc340e666afd и тем же endpoint. Report/file SHA-256:
5bac0dfe3e5a4ef6086402ea2b201d9e3a5e8f320cb6221219647c8557f2c2c6.

Существующий verify.py запущен локально на исходной operation и новых events/file-read:
tool_execution, selection_order, обе границы data_transfer, report_correctness,
file_persistence, final_text_accuracy, chain и full_acceptance — PASS.
Все прежние artifact hashes сверены; response, initial verdict/result и исходник
verifier не изменены. Модель, MCP tools, live и VPS повторно не вызывались.

7.2/7.3 закрыты по фактам; прогресс 26/26. README, VIDEO и handoff отражают итог одной
попытки без обобщения на устойчивость модели. Finish-day/archive/commit/push не выполнялись.
[Final result](../../../../day-19-mcp-composition/evidence/live-20260924/operator-verification-20260924T151255Z/result-final.json).
