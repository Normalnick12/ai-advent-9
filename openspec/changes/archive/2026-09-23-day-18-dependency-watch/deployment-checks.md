# Deployment readiness — 2026-09-23

Временный hostname: `132-243-120-220.sslip.io`; VPS `132.243.120.220`, SSH user
`aiadvent`, Ubuntu 24.04.5. Hostname хранится только в deployment configuration.

## Подтверждённые факты

- A resolution на Windows и VPS возвращает только `132.243.120.220`; AAAA нет.
- Пользователь выполнил bootstrap с интерактивным sudo и подтвердил новый key-based
  SSH login. Повторного bootstrap не было. Два временных TLS errors при выпуске
  сертификата сменились успешной trusted HTTPS проверкой.
- Независимые проверки из Codex подтвердили enabled/active `day18-watch` и Caddy,
  release `/opt/day18/releases/5b11f8d9e5a87a25`, loopback listener `127.0.0.1:8018`,
  SSH 22, Caddy 80/443 и локальный Caddy admin 127.0.0.1:2019.
- Protected env: parent 0750 root:day18, file 0640 root:day18; data directory
  `/var/lib/day18` — 0700 day18:day18. Python 3.12.3, NTPSynchronized=yes.
- [VPS readiness JSON](vps-readiness.json), 17:17:07 UTC: trusted TLSv1.3,
  Let's Encrypt YE2, SAN выбранного hostname, expiry 2026-12-22; health=ok;
  missing/invalid Bearer=401; valid initialize и ровно два tools с корректными
  schemas; foreign Host=421. Прямой Google Maven lookup найден, 129 версий в этом
  единичном readiness lookup (не execution watch и не критерий live).
- Trusted TLS и health также независимо прошли с Windows. Public port 8018 не
  ответил на HTTP (ReadTimeout, как и control port 9); connect_ex вернул 0.
  Поэтому внешний TCP reject не заявляется. Loopback binding проверен. Recovery evidence подтвердил UFW active/default deny incoming,
  но обнаружил прежний ALLOW 1500/tcp (ispmanager) для IPv4/IPv6. Пользователь
  подтвердил, что панель не используется, и выполнил согласованное удаление.
  [Финальный UFW status](firewall-final.txt), предоставленный пользователем:
  Rule deleted / Rule deleted (v6); active, default deny incoming; разрешены
  только порты 22/80/443, без 1500 и 8018. Исторический firewall snapshot
  в vps-recovery.json оставлен без изменений; финальное состояние записано отдельно.
- Затем SSH из окружения Codex получил connection timeout до авторизации.
  Пользователь повторно проверил SSH из своего PowerShell: key-based login успешен.
  VPS probes выполнены через ручные команды пользователя без обхода сетевого ограничения.
  SSH не менялся; из UFW удалено только отдельно согласованное ненужное правило ISPmanager.
- Предварительная native Responses readiness не выполнялась: SSH timeout был до
  provider request. Затем endpoint принят OpenAI в основном live: один успешный
  create и одна summary operation, без пробных generations; см. [live report](live-report.md).

## Snapshot и recovery

- Base commit: `84832ec0a28180a473d4f2973346b89a15e66937`; implementation uncommitted.
- Archive SHA256: `5b11f8d9e5a87a25fdf7889326a305fd6ed91f768f220433597e211c1388f134`.
- Bootstrap SHA256: `94c04fd38ef358449df0cd346978506a97a1c4f57dc4d83949e82af29f1e831e`.
- Archive содержит 19 source/config/test файлов и snapshot-manifest.json, без
  venv, SQLite, caches и credentials. Archive SHA256 сверён на VPS; bootstrap
  сверяет все source hashes. Повторная сверка установленного manifest и pip freeze
  сохранена в recovery evidence. Все 19 deployed hashes также совпали с текущими
  локальными файлами.
- [Recovery probe](../../../../day-18-dependency-watch/deploy/recovery_probe.py)
  выполнен пользователем через SSH. `pre`: два последовательных конечных watch,
  30 секунд / max_runs=2, active-watch service restart и затем VPS reboot.
  Каждый create вызывается один раз, с durable write-ahead evidence; pre не повторяется.
  История и persisted aggregate сверяются до reboot. `post`: изменившийся boot ID,
  прежние execution records, следующий execution после boot, completed/max_runs,
  through_execution_id и normal interval configuration. Token не выводится.
- [Полный recovery JSON](vps-recovery.json) проверен локально: phase=passed,
  normal_configuration_restored=true. Restart watch
  `413d37ad-82b4-4313-8de7-bcd1a28e95ff`: PID 4534 -> 4544, немедленный summary
  сохраняет один execution; затем completed с successful=2/failed=0,
  through_execution_id=`fae2d868-52b9-42f8-afad-015db9b4873b`.
- Reboot watch `1b86e300-d38b-40fc-862c-75769d3162af`: boot ID изменился
  с `e0afcb65-7e52-4be1-a1ad-a4262567d1f1` на
  `3885b3f9-d1b5-47ad-bdfa-8a0a4dfd07e7`; оба service active после boot.
  Первый execution сохранён без изменений, следующий выполнен после boot:
  scheduled 17:44:42.934 UTC, started 17:44:43.117 UTC, completed 17:44:43.161 UTC.
  Итог completed, successful=2/failed=0, through_execution_id=
  `0641236f-6e21-449d-9f61-2a48550a9101`. У обоих next_run_at=null, skipped_slots=0.
- Сохранены ровно два create calls. Повторный pre после reboot был остановлен
  existing-evidence guard до создания новых watch или изменения configuration.
  Ни один из этих probes не вызывал OpenAI. interrupted=0 в обоих сценариях:
  deterministic interrupted recovery доказан отдельно offline.
- Backend запущен в управляемой сессии через scripts/dev.ps1; status подтвердил health.
  17:48:33 UTC, emulator-5554 через toybox nc к 10.0.2.2:8000 получил HTTP 200
  и status=ok. Это FastAPI reachability, не подтверждение native Responses/MCP path.
  Общий health показывает настройки прежнего backend; Day 18 max_retries=0 проверен
  отдельными offline tests и не определяется полем общего health.
- Задачи 8.1–8.3 завершены: deployment, техническая readiness и recovery probes.
  По отдельному разрешению пользователя основной live выполнен; результаты и
  границы доказательств — в [live report](live-report.md). Recovery probes сохранены
  отдельно от основного live. Физическое выключение ноутбука не проверялось.

## Ограничения и смена hostname

При ошибке DNS, trusted certificate или отказе OpenAI от endpoint остановиться
и сохранить конкретную причину. Не переходить на tunnel, self-signed certificate
или другой hostname без review.

Для будущей смены на `mcp.<our-domain>` изменить DNS и public hostname/URL в environment
Caddy, Day 18 service и локального backend, затем проверить trusted TLS и authorization.
Persistent `/var/lib/day18/watch.sqlite3`, UUID watches, executions и scheduler не
зависят от hostname и не требуют миграции. Bearer не входит в public configuration.
