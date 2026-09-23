# Design

## Context

Мотивация и границы продукта — в [proposal](proposal.md). Day 17 уже использует официальный MCP SDK `mcp==2.2.0`, Streamable HTTP, отдельный Responses provider и Android lab. Его `server.py` объединяет validation, async Google Maven lookup, MCP ToolError и создание server/app на import. Прямой импорт такого entrypoint неудобен для фонового execution. Day 17 evidence подтверждает реальный lookup, но также показывает, что model prose может исказить количество версий.

VPS: Ubuntu 24.04, 2 vCPU, 4 GB RAM, persistent disk; runtime пока не настроен. Существующий FastAPI backend и OpenAI key остаются локальными. Новый сервис должен продолжать зарегистрированную работу после завершения Responses request и остановки ноутбука. Design необходим: изменение затрагивает MCP, storage/recovery, backend, Android и deployment.

## Goals / Non-Goals

**Goals:** один владелец расписания, SQLite как authoritative state, проверяемые UTC slots, bounded work, программная сводка после каждого execution, независимость transport/request lifetime от watch lifetime, чёткие crash semantics.

**Non-Goals:** общий scheduler framework, гарантии exactly-once внешнего HTTP, multi-tenant OAuth platform, idempotent create, постоянно доступный remote conversational backend и periodic LLM generation. Полный список product exclusions — в proposal.

## Decisions

### 1. Изолированный service и небольшое переиспользование lookup

В `day-18-dependency-watch/` выделить lookup, storage, scheduler и MCP entrypoint в небольшие модули с отдельным environment. Адаптировать lookup Day 17: те же coordinate regex/length 256, фиксированный Google Maven group-index URL, 15-second total deadline, 2 MiB body limit, запрет redirects и external XML entities, прежние normal/error categories. HTTP transport и clock инъецируются для тестов; предметная ошибка не зависит от MCP SDK. MCP adapter преобразует ошибки своих операций в SDK tool errors, scheduler сохраняет outcome как execution.

Использовать уже проверенную ветку официального SDK и подтвердить используемые lifecycle/auth APIs по закреплённой версии при реализации; не переносить старые FastMCP примеры. Версии standalone dependencies не смешивать с backend requirements.

Альтернативы: import Day 17 entrypoint создаёт side effects и coupling; extraction общего package меняет завершённый день ради малого объёма reuse. Ограниченная адаптация lookup сохраняет механизм, не требует shared framework и оставляет Day 17 deployment/contracts прежними.

### 2. Два tools и bounded contract без create idempotency

`create_dependency_watch(group_id, artifact_id, max_runs, interval_seconds=21600)` возвращает receipt после commit: watch ID, coordinates, accepted interval/max_runs, created/next time, status и run count. `max_runs` обязателен в input schema, 1–100; пользовательский prompt должен задать конечное число проверок. Интервал — strict integer, обычно 3600–86400. Никаких end_at/timezone/cron expressions. UTC timestamps в API, целые UTC milliseconds в SQLite, monotonic clock только для ожидания и duration.

Нормальный service ограничен пятью active watches. Серверный `DAY18_ALLOW_SHORT_INTERVALS=false` по умолчанию; при включении минимальный interval=30, любой interval<3600 требует max_runs<=3, active accelerated watch максимум один. Лимиты и create проверяются в одной транзакции, чтобы concurrent requests не обходили quota. После acceptance вернуть normal configuration. Уже принятые schedules сохраняются при смене настройки: это validation новых заданий, не тихое изменение существующих.

Каждый принятый create получает новый UUID. Совпадающие coordinates/schedule не дедуплицируются; нет idempotency key, unique constraint по координатам или custom HTTP header. Create annotation `read_only_hint=False`, `idempotent_hint=False`; summary read-only. Duplicate Send guard уменьшает случайные повторы на клиенте, но не ограничивает число model-generated MCP calls. Все фактические вызовы сохраняются. Lost response означает unknown, не «watch не создан». Bounded runs и quota ограничивают последствия.

Альтернативы: один tool с action усложняет schema и allowlist; cancel нужен для endless, который исключён; header-based idempotency не является принятой архитектурной опорой.

### 3. Штатная Bearer authorization без произвольных headers

Backend читает `DAY18_MCP_SERVER_URL` и `DAY18_MCP_TOKEN` из environment. Native MCP definition каждого Responses request содержит `authorization: token`; приложение не добавляет строку `Bearer ` в значение этого поля и не использует custom `headers` для credential/idempotency. На VPS входящий стандартный `Authorization: Bearer ...` проверяется до MCP discovery/dispatch; missing/invalid token даёт HTTP 401. Сравнение секрета constant-time, auth failures не печатают входящее значение. Отсутствие token на VPS делает startup ошибочным, не открывает anonymous mode.

Официальная документация подтверждает `authorization` для remote MCP, передачу его в каждом запросе и отсутствие значения в Responses result: [OpenAI remote MCP authentication](https://developers.openai.com/api/docs/guides/tools-connectors-mcp). Сам факт настройки не заменяет readiness: при реализации проверить authenticated tools/list и native Responses path, а также отказ без token. Не строить OAuth discovery/refresh/login UI: это один заранее provisioned personal Bearer token, не claim универсального OAuth provider.

Token хранится только в локальном backend environment и защищённом VPS environment. Передача через HTTPS к OpenAI и от remote integration к VPS — транспорт авторизации, не model prompt. Не передавать token в Android DTO, tool arguments, prompt, URL, logs, Git и persisted evidence. Sanitized provider request fixture/evidence заменяет `authorization` на `[REDACTED]` до записи; error logging не сериализует credential-bearing payload. OpenAI key на VPS не нужен. Public `/health` возвращает только безопасный status.

### 4. Две таблицы и атомарные переходы

SQLite находится вне release tree. Две таблицы достаточно:

| Таблица | Поля и ограничения |
|---|---|
| watches | id UUID PK, coordinates, interval_seconds, max_runs, created_at, next_run_at nullable, status active/completed, skipped_slots |
| executions | id UUID PK, watch_id FK, scheduled_at, started_at, completed_at nullable, checked_at nullable, state running/succeeded/failed, lookup_outcome nullable, lookup_id nullable, source_url, versions_json nullable, error_category nullable, aggregate_json nullable; UNIQUE(watch_id, scheduled_at) |

Snapshot — часть execution. У negative normal result versions_json=[] с явным outcome; у технической ошибки/interruption versions_json=null. Completed_at обозначает фиксацию завершения execution, checked_at — фактическое завершение lookup, отсутствующее у interrupted. Run count выводится из terminal rows, не хранится как независимая истина. `PRAGMA foreign_keys=ON`, короткий busy timeout и обычные crash-safe настройки SQLite; не отключать journaling/synchronous durability. Не держать DB transaction во время network await.

Create: validate -> короткая write transaction с quota -> insert watch -> commit -> receipt. Claim: в transaction проверить active/due/отсутствие running и лимит runs -> выбрать последний due slot -> insert running. Finalize: transaction сохраняет outcome, вычисляет aggregate по terminal rows включая текущий, сохраняет aggregate_json и переводит watch в completed либо задаёт следующий будущий слот. Любая ошибка откатывает весь переход. Summary читает watch, последние aggregate и running row в одной read transaction; сохранённый aggregate не становится противоречивым при concurrent finalize.

Aggregate на каждом terminal execution даёт готовый historical summary record без третьей таблицы. Нулевой summary до первого run строится детерминированно из watch. История ограничена max_runs; автоматическое удаление истории/retention framework пока не добавляется. Эксплуатационная документация содержит контроль размера диска и безопасную резервную копию БД, не обещание восстановления при потере диска.

### 5. Один asyncio scheduler и явная recovery policy

Один Uvicorn worker без reload запускает scheduler в общем lifespan с MCP. Небольшой loop будит `run_due_jobs(now)` примерно раз в секунду; due time берётся из SQLite, а не из набора in-memory tasks. Lookup вызывается напрямую. Для нескольких watches допустима последовательная обработка с повторным чтением clock перед каждым claim; deadline и quota ограничивают задержку. Это best-effort schedule без SLA точности в секунду.

OS advisory lock на отдельном lock file в data directory удерживается весь lifespan; второй service owner завершается. SQLite unique slot — дополнительная защита, не distributed lock. Startup читает persisted running/active rows до запуска новых работ. Scheduler task supervised: неожиданное завершение делает app unhealthy и завершает процесс, после чего systemd применяет restart policy. Graceful shutdown прекращает новые claims и даёт текущему lookup завершиться в пределах deadline; если это невозможно, остаётся running row для recovery.

Сетка слотов: created_at + N * interval, N>=1. Claim при просрочке выбирает последний due slot, предыдущие невыполненные отмечаются skipped_slots, не executions. После finalize следующий слот — первый строго позже completion на той же сетке; слоты, пропущенные во время длинного lookup, также отражаются в skipped_slots без повторного счёта. Если UTC clock сдвинулся назад, next slot должен быть также строго позже уже claimed scheduled_at: старые slots никогда не воспроизводятся. Большой скачок вперёд использует ту же coalescing policy. VPS должен иметь штатную синхронизацию времени.

Незавершённый persisted running после restart проходит полноценную terminalization transaction, а не отдельное обновление execution state. В одной транзакции сохранить state=failed/error_category=interrupted и completed_at, учесть execution в terminal run count/max_runs, пересчитать deterministic aggregate по истории с этим execution, сохранить aggregate_json с through_execution_id этого execution, обновить watch status и следующий допустимый next_run_at либо completed/next_run_at=null. Lookup outcome неизвестен, новые версии/checked_at не выдумываются, слот не переисполняется. Startup завершает recovery commit до готовности summary handler и запуска scheduler loop: немедленный summary уже видит согласованные execution, aggregate и watch без ожидания следующего tick или пересчёта на чтении. При ошибке откатывается весь переход; startup не объявляется готовым. Повторный startup после commit не учитывает этот terminal execution второй раз. Если после его scheduled_at уже есть более поздние due slots, следующий due slot после interrupted оставляется для обычного coalescing; если лимит исчерпан, watch completed. Таким образом startup не теряет актуальную overdue работу, но не делает HTTP replay interrupted слота. Immediate retries при обычном upstream failure тоже отсутствуют.

Crash до commit claim оставляет due watch; crash после claim оставляет interrupted-кандидат; crash после finalize commit оставляет согласованный snapshot/summary/next-run. Exactly-once и at-least-once для каждого календарного слота не обещаются: claim мог быть сохранён до реального HTTP, а пропуски coalesce-ятся. Storage failure останавливает scheduling, без fallback в память или пересоздания БД.

Выбор asyncio обусловлен одним типом interval job и необходимостью транзакционно связать предметную историю с next_run_at. APScheduler поддерживает persistent jobs/misfire/coalescing, но добавляет собственное состояние и зависимости; systemd timers/cron для dynamic watches всё равно потребовали бы dispatcher. Systemd используется для процесса, не для каждого watch. [APScheduler guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html).

### 6. Aggregation по истории, без LLM на tick

Полный output contract задан service spec. `runs_total` — terminal executions; `successful` включает все normal lookup outcomes, `failed` — технические ошибки и interrupted, `interrupted` — отдельный под-счётчик failed. `comparable_snapshots` включает found/no_versions. `first_checked_at`/`last_checked_at` берутся по фактическим ненулевым checked_at завершённых lookup, включая технические failures с известным временем; это не timestamps publication. Baseline/counts до первого пригодного snapshot null.

Для сравнения используются множества версий, хотя исходные arrays сохраняются. `changes_detected` считает отличия соседних пригодных snapshots, включая удаления; baseline не является изменением. `newly_seen_versions` — union observed sets после baseline минус baseline, уникально, в порядке первого наблюдения и порядке источника внутри snapshot. Удаление и возвращение baseline-версии не делает её новой. Negative absent/error не становятся empty comparable snapshot; no_versions является корректным пустым snapshot. Gaps видны по failed/negative outcomes, без утверждения непрерывного наблюдения.

`latest_execution` относится к последнему terminal row, `running_execution` возвращается отдельно. `through_execution_id` и `generated_at` фиксируют версию сводки; для пустой истории through ID null. Watch status/next_run_at в summary актуальны на read transaction. Summary lookup не выполняет HTTP, не расширяет schedule и не запускает aggregation через модель.

Выбран вариант периодического сохранения готовой сводки после run. Push-доставка и периодическая генерация prose не нужны. Модель объясняет готовый aggregate только по пользовательскому запросу; typed UI остаётся источником чисел.

### 7. Отдельная backend operation и Android lab

Новый route `POST /api/v1/dependency-watch/run` принимает action create/summary, prompt и selected watch_id для summary. Валидация action/ID выполняется до provider call; URL/credential из Android не принимаются. Отдельные DTO/service не расширяют Day 17 MavenEvidence и не меняют общий LlmClient/Days 11–17.

Один non-streaming Responses request, существующий model alias `gpt-5.6`, store=false, max_retries=0 и конечный deadline по образцу Day 17. Для create разрешён/forced только create tool, для summary — только summary. `require_approval=never` ограничено явно выбранной пользователем операцией и серверной allowlist; это не обещание единственного MCP call. Natural-language arguments не исправляются backend-ом. Summary prompt содержит selected ID как пользовательский контекст, затем result/actual argument сверяются с ним; mismatch сохраняется как ошибка соответствия.

Нормализация сохраняет все доступные mcp_* items, safe request configuration, final text и отдельные parsed outcomes. Unknown при provider timeout не становится not_called. При ответе с несколькими create calls все IDs/results/errors остаются видимыми. Если provider не вернул result, серверные create logs дают фактическую доступную историю, но приложение не фабрикует отсутствующие MCP call IDs. Не добавлять автоматическую reconciliation/list operation.

Android: отдельные Repository/ViewModel/screen, создание через AppContainer, guard до launch coroutine, immutable operation snapshot. Create и summary — явные действия, без polling/generation при открытии. Сохранить небольшой локальный список подтверждённых receipts и выбранный watch ID (не server-wide list/dashboard); это позволяет не терять несколько returned IDs и пережить process death. Отдельный ввод известного watch ID допустим для ручного восстановления, без implicit create. Старый status явно last known; unknown attempt не стирает ранее подтверждённую identity и не используется как её новый success.

Inspector показывает каждый вызов, arguments/output/error, timestamps и IDs. Primary карточка рисует числа из validated aggregate; prose отдельно. Навигация Day 18 после Day 17 с сохранением прежних destinations; WorkManager/alarm/Android service для ticks не нужны.

### 8. VPS: venv + systemd + Caddy

Один непривилегированный пользователь сервиса, отдельный venv и release directory; SQLite/lock в `/var/lib/day18/`, environment в защищённом `/etc/day18/dependency-watch.env`. Права data directory 0700, файлов 0600 либо эквивалентный минимальный доступ сервису. Env вне release/Git, без вывода содержимого в терминальные логи. systemd unit запускается при boot, Restart=on-failure с паузой и лимитом частых отказов; stdout/stderr идут в journald с ограничением хранения. Ошибки старта/DB требуют устранения причины, бесконечный restart loop не считается recovery.

Caddy принимает 80/443 и автоматически обслуживает доверенный сертификат стабильного DNS hostname, проксируя `/mcp` и безопасный `/health` в loopback Uvicorn. Header Authorization должен доходить до auth layer без записи в logs. Не отключать MCP Host/origin protection; trusted proxy ограничен loopback. Поддомен собственного домена предпочтителен, но устойчивый управляемый provider hostname также допустим при возможности выпуска сертификата. Временный tunnel и self-signed certificate не основной path. [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

SSH key-only, direct root login выключен, firewall допускает SSH и TCP 80/443, application port наружу закрыт. Сначала сохранить работающий SSH access, затем применять firewall, учитывая IPv6. Настроить обновления безопасности и штатную clock synchronization. Не строить hardening platform. Docker Compose пока не нужен: один Python process и proxy проще сопровождать через systemd; будущие небольшие Week 4 services могут получить собственные units/venvs.

Честная гарантия: зарегистрированные watches автономны; новые Android agent requests требуют локальный backend. Если позже понадобится полностью remote Day 18 user path, отдельный agent backend станет отдельным change, а не скрытой миграцией всего проекта.

### 9. Проверки и evidence

Offline: fake clock с явным now, temporary SQLite (включая повторное открытие новым service instance), fake HTTP transport и failpoints на claim/finalize. Fixtures проверяют membership changes, reordering, removal/reappearance, negative gaps и failures. Проверить unique slot, quota races, capacity, auth, summary no-side-effects и token redaction. SDK integration tests проверяют реальные schema/discovery/error wrappers закреплённой версии без network. Backend — Responses fixtures; Android — focused JVM/UI плюс navigation regression через `scripts/dev.ps1`, без backend/OpenAI для UI tests.

Обязательный deterministic recovery test: сохранить watch с одним succeeded execution и следующим running execution, закрыть и вновь открыть SQLite, выполнить startup recovery при фиксированном clock, не запускать scheduler tick и сразу прочитать summary. Проверить interrupted=1, runs_total=2, successful=1, failed=1, through_execution_id равен ID восстановленного execution, persisted aggregate_json совпадает со сводкой, running_execution отсутствует. Параметризовать max_runs=3 (active, next_run_at равен следующему слоту после interrupted, включая уже due слот для обычного coalescing) и max_runs=2 (completed, next_run_at=null). Повторный reopen не меняет counts; failpoint до recovery commit не оставляет частично обновлённые execution/aggregate/watch. Тест не делает sleep, HTTP или LLM calls.

Readiness отдельно: deployed release manifest, DNS/TLS, auth denial/success, tools/list/schema, health/DB/worker, upstream connectivity, backend reachability с emulator. Изолированные service restart и VPS reboot probes подтверждают сохранность ID/history и boot enablement. Эти probes не подменяют основной agent live и не публикуются как model acceptance.

Основная попытка: create из Android, interval=30/max_runs=3; сохранить момент завершения Responses; остановить local backend и закрыть Android; VPS выполняет три checks; вернуть backend и запросить summary отдельной operation. Сопоставить DB export, JSON logs (watch/run/lookup IDs), MCP outputs и prose. Ожидаемый wall time около 1–3 минут, без обещания длительности OpenAI. Если create response завершился после первого tick, критерий «три runs после ответа» не выполнен: timestamps остаются фактическими, задержка не скрывается и schedule не переписывается. Новая попытка, если потребуется, отдельно согласуется и маркируется; нельзя повторять неизменный запрос ради удачного prose.

Mechanism, temporal independence, aggregate correctness и prose accuracy получают отдельные verdicts. Ошибка prose при полной цепочке сохраняется как failed accuracy без repair; evidence сбор и честный отчёт могут быть завершены без объявления полного acceptance passed. Недоказанная цепочка не считается successful live. Overnight с обычным интервалом — необязательное наблюдение после обязательных проверок, без ожидания суток для сдачи. Day README краткий и фактический; детальный отчёт хранится в change evidence, запуск/настройка — в README компонентов и scripts.

## Risks / Trade-offs

- [Повтор create или потерянный response] -> новые IDs допустимы, Android guard и отсутствие retry, все доступные calls в evidence, finite max_runs и capacity; idempotency не обещаем.
- [Token попал в capture request] -> redact до любой записи, тесты с synthetic sentinel token, отсутствие Android secret fields и credential logging.
- [Crash после claim] -> видимый interrupted failed run без HTTP replay; max_runs означает число terminal executions, не число успешных snapshots.
- [Long outage/clock adjustment] -> coalescing и unique slots, skipped count без выдуманной истории; не обещать непрерывность мониторинга.
- [Несколько процессов/умерший scheduler] -> OS owner lock, один worker и supervised lifecycle/health; не масштабировать Uvicorn workers.
- [DB/disk failure] -> fail closed, persistent directory и documented backup; reboot durability не равна disaster recovery.
- [Model prose/arguments ошибочны] -> typed facts отдельно, все actual calls, отдельный acceptance verdict; forced tool не гарантирует правильные arguments.
- [Short live не укладывается в temporal criterion] -> зафиксировать реальное время и непрошедший критерий, без скрытой новой попытки.

## Migration Plan

1. В apply реализовать изолированный Day 18 service/backend/Android и deployment templates; прежние Days доступны без Day 18 configuration. Добавить Day README и root link уже при добавлении day directory.
2. Выполнить focused offline checks, secret/diff review и strict OpenSpec validation. Planning само по себе не является разрешением на реализацию или VPS setup.
3. При выполнении deployment tasks подготовить VPS runtime, hostname/TLS, env/permissions, persistent directory и enabled units. Передать проверенный service snapshot; подтвердить manifest SHA256 server files на VPS. Если snapshot соответствует commit, записать commit SHA; иначе записать base commit плюс точный manifest/состояние изменений, не выдавать HEAD за deployed revision. Commit/push выполняются только по отдельному явному запросу пользователя; Render-specific pre-live Git workflow Day 17 не переносится.
4. Пройти readiness, service restart и VPS reboot probes с сохранением фактов; затем основной live и video verification. Вернуть ordinary interval configuration, сохранив принятую историю.
5. Обновить фактические результаты и task checkboxes. Архивирование/finish-day/commit/push — отдельный последующий workflow, не prerequisite implementation task.

Rollback: остановить/disable Day 18 unit и убрать его endpoint/configuration, сохранив data directory/backup; вернуть предыдущее приложение или отключить новый route/card. Не удалять SQLite при redeploy. Обновление initial DB schema версионировать; неизвестная более новая schema отклоняется, silent downgrade запрещён. Старые Days не требуют миграции.

## Open Questions

- Deployment choice (2026-09-23): `132-243-120-220.sslip.io`, VPS `132.243.120.220`, SSH user `aiadvent`; DNS A verified. Releases: `/opt/day18/releases/<revision>`, current symlink `/opt/day18/current`. Hostname задаётся только environment/configuration и позднее заменяется без миграции SQLite. При отказе DNS/trusted TLS/OpenAI endpoint — остановка для review, без автоматической замены hostname/tunnel/self-signed.
- Форму raw MCP result/error wrapper и фактическую передачу Bearer проверяем offline SDK fixtures и live readiness на закреплённых версиях; неподдержанный output сохраняется как invalid evidence, без fallback на custom headers или function bridge.
