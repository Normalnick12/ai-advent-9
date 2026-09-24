# Day 19: продолжение после частичной установки

**Актуальный статус: независимая проверка завершена, PASS.** Gates 6.3/6.4,
единственный live и проверка его результата выполнены. Operation остаётся
`085e5b0a-863f-4a62-abd9-f62359a2393d`; новых model/MCP/VPS вызовов при финальной
локальной проверке не было.

Оператор предоставил полный export в term.txt: 7 событий одной последовательности
lookup → summarize → save и фактические 415 bytes файла. Operation/lookup ID,
endpoint/revision, byte count и SHA-256 совпали. Исходный export сохранён побайтно;
существующий verifier, его исходник и прежняя трасса не изменялись.

[Окончательные вердикты](evidence/live-20260924/operator-verification-20260924T151255Z/verdict-final.json):
tools/order/обе границы/report/file/final_text — PASS, chain/full_acceptance — PASS.
[Итог и ссылки на evidence](evidence/live-20260924/operator-verification-20260924T151255Z/result-final.json).
[Provenance и контроль прежних hashes](evidence/live-20260924/operator-verification-20260924T151255Z/provenance.json).

Исходные response, collection.json, result-initial и verdict-initial не перезаписаны.
Ранее export без привилегий вернул [], поэтому предварительная оценка была NOT_PROVEN;
новый операторский источник позволил завершить проверку той же попытки.

**Новых команд deployment, collector, tools или launcher сейчас не требуется.**
Задачи 26/26 выполнены. По отдельному поручению `$finish-day` change
[архивирован](../openspec/changes/archive/2026-09-24-day-19-mcp-composition/proposal.md),
две основные спецификации синхронизированы. Сценарий записи сохранён в VIDEO.md.

Дальше хранится история подготовки. Все команды staging/installer уже выполнены,
повторять их не следует.

## История частичной установки — 2026-09-24

Старый installer `def6cc340e666afd` оператор запустил вручную. Он создал release,
user/state/env/unit, запустил Day 19 на loopback 8019 и остановился на `caddy validate`.
**Не запускать его повторно и не повторять initial install из нового архива.**

Read-only inspection в 14:09 UTC подтвердил:

- Day 18 active, прежний PID 1763 и release `5b11f8d9e5a87a25`;
  loopback/HTTPS health 200, authenticated discovery содержит прежние два tools.
- Day 19 active, PID 5865, current → `/opt/day19/releases/def6cc340e666afd`;
  loopback health 200. Это ещё не готовность публичного endpoint.
- Caddy active, PID 935. `/etc/caddy/Caddyfile` побайтно равен
  `/etc/day19/Caddyfile.before-day19`: SHA-256
  `e0244509dea917255dce224a46ec59fcfcb6232cf7e05e19c24b87ab72390b6d`.
  Day 19 route не применён; прежний failed candidate сохранён.
- Конфигурация Caddy и backup/candidate прочитаны без sudo. `/var/lib/day19` имеет
  day19:day19, 0700; metadata дочернего reports недоступна пользователю aiadvent.
- Pre-live и live не проводились. Полный offline gate 280 tests/PASS переиспользован.

[Полная диагностика, проверки и hashes](evidence/caddy-recovery-20260924.json).
[Предыдущая подготовка](evidence/preparation-20260924.json) сохранена как история.

## Причина и исправление

Исходный сайт Day 18 начинается с `{$DAY18_MCP_PUBLIC_HOST} {`.
Переменная задана в `Environment=` systemd-сервиса Caddy, но отсутствует у installer.
Caddy подставляет переменные до разбора: пустой адрес оставляет `{`, поэтому блок
сайта становится глобальным и `reverse_proxy` недопустим на строке 4.
Это воспроизведено настоящим Caddy v2.11.4 без изменения конфигурации.
[Правила подстановки Caddy](https://caddyserver.com/docs/caddyfile/concepts).

Исправленный [install.py](deploy/install.py):

- Берёт необходимые переменные из `systemctl show caddy ... Environment`, проверяет
  наличие значений. Не полагается на окружение sudo. `EnvironmentFiles` и неподдержанные
  placeholders блокируют запуск с требованием разобраться в конфигурации.
- Сохраняет исходные байты, добавляет отдельный сайт в конец; выполняет validation
  до создания user/release/env/service. Существующий глобальный блок остаётся целым.
- Проверяет неизменность Caddyfile и окружения перед атомарной заменой файла;
  после публикации выполняет только `systemctl reload caddy`.
- Режим `--resume-caddy-from EXISTING_REVISION` предназначен именно для этого
  частичного состояния. Проверяет current/release/manifest, равенство всех исходников
  кроме installer, установленный unit, активный Day 19, существующие host/token/root,
  владельца/режим каталогов, совпадение активного Caddyfile с прежним backup.
- Resume сохраняет runtime, token, user, unit, current, backup и failed candidate.
  Новый candidate создаётся эксклюзивно как `/etc/day19/Caddyfile.resume-2da85c77bb4be5e0`.
  Повтор или drift блокируются. Сервисы Days 18–19 не перезапускаются.

Прошли 19 focused tests. Четыре read-only `caddy adapt` сценария на VPS подтвердили
исходную ошибку, исправление, два правильных host→upstream при наличии глобального
блока и отклонение неправильной глобальной директивы. `caddy validate` с root и
режим recovery на момент подготовки ещё не выполнялись. Позднее оператор выполнил
resume успешно; актуальная блокировка readiness описана выше.

## Новый архив и сохранённый snapshot

Локальный архив: `.local/day19-deploy/snapshot-caddy-fix/snapshot.tar.gz`.
Его проверенная копия на VPS: `/home/aiadvent/day19-deploy/2da85c77bb4be5e0/snapshot.tar.gz`.

| Проверка | Значение |
| --- | --- |
| Installer snapshot revision | `2da85c77bb4be5e0` |
| Archive SHA-256 | `40777a72ebce782add99db28843198aa7dcdd86833bb9cd650d0fc4c6d33d9e6` |
| Installer SHA-256 | `27311c2d370dc6fac9739f05eb4f65f275d1540ec8b4c044d4468fc7f6e78ea3` |
| Состав | 17 source files + manifest; только regular files, hashes и bytes сверены |
| Изменение относительно старого snapshot | Только `deploy/install.py` |
| Runtime при Caddy-only recovery | Остаётся `def6cc340e666afd` |

Старый `.local/day19-deploy/snapshot/snapshot.tar.gz` не перезаписан. Его SHA-256:
`5705f07160d698dbd15632cbaf12269eb50a26e3e63d69a192da15506893364f`.
Старые staging/release/env/backup на VPS сохранены. Новый архив передан, распакован
и проверен. Впоследствии оператор успешно выполнил Caddy-only resume.

## Ближайшая диагностика и граница остановки

Пользователь выполнил диагностический `sudo stat` и подтвердил: `/var/lib/day19`
и `/var/lib/day19/reports` — обычные каталоги day19:day19 с режимом 700.
Агент sudo не выполнял. Повтор этой диагностики сейчас не требуется.

Caddy-only resume и readiness уже выполнены оператором с exit 0.
Повторять их не требуется. Post-live collector также выполнен оператором, повторять его не требуется.

## Безопасное продолжение после review

Шаги 1–3 ниже уже выполнены и сохранены как история. Шаг 4 также завершён.
Независимый сбор и финальная проверка тоже завершены; результат в начале файла.
При дальнейшем продолжении выполнять действия последовательно;
при ошибке остановиться, сохранить диагностику и не повторять команды вслепую.
SSH только по IP; HTTPS hostname остаётся `day19-132-243-120-220.sslip.io`.

1. Повторно убедиться, что Day 18 здоров, Caddy/backup/current соответствуют evidence,
   и проверить DNS A/AAAA: только IP VPS, отсутствие AAAA допустимо.
2. Из PowerShell 7 сверить новый локальный hash, создать отдельный staging и передать архив:

```powershell
$sshOptions = @('-i', 'C:\Users\Nikita\.ssh\ai_advent_vps_2026.pub',
  '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
  '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectionAttempts=1',
  '-o', 'ConnectTimeout=20')
$vpsTarget = 'aiadvent@132.243.120.220'
$archive = '.local/day19-deploy/snapshot-caddy-fix/snapshot.tar.gz'
$expected = '40777a72ebce782add99db28843198aa7dcdd86833bb9cd650d0fc4c6d33d9e6'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
  throw 'Archive changed; stop'
}
ssh @sshOptions $vpsTarget 'mkdir /home/aiadvent/day19-deploy/2da85c77bb4be5e0'
if ($LASTEXITCODE -ne 0) { throw 'Staging exists or failed; inspect, do not replace' }
scp @sshOptions $archive "${vpsTarget}:/home/aiadvent/day19-deploy/2da85c77bb4be5e0/snapshot.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed' }
$remoteHash = ssh @sshOptions $vpsTarget 'sha256sum /home/aiadvent/day19-deploy/2da85c77bb4be5e0/snapshot.tar.gz'
if ($LASTEXITCODE -ne 0 -or ($remoteHash -split '\s+')[0] -ne $expected) { throw 'Remote hash mismatch' }
ssh @sshOptions $vpsTarget 'mkdir /home/aiadvent/day19-deploy/2da85c77bb4be5e0/source && tar -xzf /home/aiadvent/day19-deploy/2da85c77bb4be5e0/snapshot.tar.gz -C /home/aiadvent/day19-deploy/2da85c77bb4be5e0/source'
if ($LASTEXITCODE -ne 0) { throw 'Unpack failed; inspect' }
$installerHash = ssh @sshOptions $vpsTarget 'sha256sum /home/aiadvent/day19-deploy/2da85c77bb4be5e0/source/deploy/install.py'
if ($LASTEXITCODE -ne 0 -or ($installerHash -split '\s+')[0] -ne '27311c2d370dc6fac9739f05eb4f65f275d1540ec8b4c044d4468fc7f6e78ea3') {
  throw 'Unpacked installer mismatch'
}
```

3. После review диагностики и нового staging использовать **исправленный** installer
   из нового `source`, передав этот же `source`, HTTPS hostname и обязательно
   `--resume-caddy-from def6cc340e666afd`. Этот ручной root-этап уже выполнен
   оператором с exit 0; команда не должна запускаться повторно.
   Не применять обычный initial-install, не удалять старый current/env/release.
4. После успешного Caddy-only recovery проверить сохранённый backup, current и
   состояние Day 18, затем весь gate 6.3: фактический manifest/packages, TLS/auth/Host,
   discovery трёх Day 19 tools и writable persistent root. Installer revision и
   runtime revision фиксировать раздельно. Только далее pre-live → один live.
5. При неудачном validate Caddyfile не публикуется. При ошибке reload файл на диске
   мог уже смениться: сначала снять status/logs и сравнить backup/candidate/active file.
   Не считать это rollback, не повторять installer автоматически; отдельно определить,
   требуется ли восстановление точного backup и reload. Старый backup не перезаписывать.

Видео: [VIDEO.md](VIDEO.md). Finish/archive/commit/push не выполняются.
