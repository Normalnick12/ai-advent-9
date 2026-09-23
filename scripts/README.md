# Окружение разработки Windows

Настройка и команды для [backend](../backend/README.md) и
[Android-клиента](../android-app/README.md). `dev.ps1` работает в PowerShell 7
из любого каталога; инструменты и зависимости автоматически не устанавливает.
Команды ниже выполняются из корня репозитория, если не указано иное.

## Первичная настройка

### Backend

Нужны Python 3.11+ и PowerShell 7. Создайте окружение и установите
[зависимости](../backend/requirements.txt):

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

Создайте локальный игнорируемый `backend/.env` с переменной `OPENAI_API_KEY`
или задайте её в терминале запуска backend. Ключ не сохраняйте в исходниках
или Git и не передавайте Android-приложению.

### Android

Нужны Android Studio, JDK 17 или совместимый более новый JDK,
Android SDK и Android Emulator.

1. Откройте папку `android-app` в Android Studio и дождитесь Gradle Sync:
   зависимости загрузятся автоматически.
2. Если эмулятор ещё не настроен, создайте AVD в Device Manager Android Studio.
3. Запустите `.\scripts\dev.ps1 backend` в отдельном терминале.
4. Во втором терминале выполните `.\scripts\dev.ps1 emulator`, затем запустите
   конфигурацию `app` в Android Studio.

Эмулятор подключается к серверу по `http://10.0.2.2:8000/`.
Локальное HTTP-соединение разрешено в debug-сборке.
Переменные окружения для приложения не требуются.

## Команды из корня проекта

| Команда | Назначение |
| --- | --- |
| `.\scripts\dev.ps1 status` | Пути JDK/SDK, наличие Python, `/health`, PID процессов |
| `.\scripts\dev.ps1 backend` | Backend в текущем терминале; логи здесь же; остановка Ctrl+C |
| `.\scripts\dev.ps1 emulator` | Переиспользовать единственный эмулятор или запустить единственный AVD |
| `.\scripts\dev.ps1 unit` | JVM-тесты Android |
| `.\scripts\dev.ps1 build` | Сборка debug APK |
| `.\scripts\dev.ps1 ui` | Подготовка эмулятора и инструментальные UI-тесты |

Backend для живых проверок оставьте в отдельном терминале. Во втором выполните `status`, затем `emulator` и запустите приложение из Android Studio. `status` проверяет HTTP с таймаутом 3 секунды; код 1 означает недоступный backend или отсутствующий инструмент. Выключенный backend не мешает текущим unit/UI-тестам. `/health` подтверждает FastAPI на компьютере, но не доступ из эмулятора и не OpenAI.

Backend загружает локальный `backend/.env`, если он есть; альтернатива — `OPENAI_API_KEY` в окружении терминала. Значения ключей скрипт не выводит. Занятый порт 8000 блокирует второй запуск, существующий процесс не завершается. Автоперезагрузка не включена: после изменения backend остановите его Ctrl+C и запустите снова.

После запуска backend доступны [Swagger UI](http://127.0.0.1:8000/docs)
и [проверка состояния](http://127.0.0.1:8000/health).
Backend запускается одним worker: блокировки диалогов действуют внутри процесса.

## MCP-сервер Day 17

Сервер из [Day 17](../day-17-android-dependency-mcp/README.md) использует отдельное
Python-окружение и не требует `OPENAI_API_KEY`. Нужен Python 3.11+;
локальная проверка и Render deployment выполнены на Python 3.14.7.

```powershell
cd day-17-android-dependency-mcp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```

Для offline-проверок из той же папки и окружения:
`python -m pip install -r requirements-dev.txt`, затем `python -m pytest -q`.

Render Web Service использует `day-17-android-dependency-mcp` как Root Directory,
build command `pip install -r requirements.txt` и start command
`python -m uvicorn server:app --host 0.0.0.0 --port $PORT`.
Задайте `PYTHON_VERSION=3.14.7`, Health Check Path `/health`.
Разрешённый hostname берётся из `RENDER_EXTERNAL_HOSTNAME` либо `MCP_PUBLIC_HOST`.
Публичный endpoint — `https://<service-host>/mcp`.

На время эксперимента отключите Auto-Deploy, чтобы последующие изменения документации
не сменили участвующую в проверке revision. Deployment выполняется из проверенного
pre-live commit; фактический deployed SHA сохраняется в evidence попытки.
`/health` проверяет готовность сервера, а MCP discovery проверяется отдельно до запроса модели.

URL сервера задаётся на [backend](../backend/README.md) через `DAY17_MCP_SERVER_URL`;
ключ OpenAI остаётся только на backend. Локальный MCP endpoint предназначен для
разработки; для вызова через Responses API нужен публичный HTTPS endpoint.

## Тесты backend

Из папки `backend` с активированным окружением:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Тесты используют подставные ответы провайдера и временные SQLite-файлы;
живые запросы OpenAI и пользовательские базы в `.local` не нужны.
Сборка и тесты Android запускаются командами `build`, `unit` и `ui`
из таблицы выше. Выбор отдельного теста описан ниже.

## Проверки Day 15

Targeted offline backend checks из `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_playground_coding.py tests/test_playground_service.py tests/test_playground_boundaries.py tests/test_playground_http_acceptance.py -q
```

Android из корня, по одной Gradle-команде за раз:

```powershell
.\scripts\dev.ps1 unit -Test '*Playground*'
.\scripts\dev.ps1 ui -Test 'com.example.responsecontrollab.PlaygroundUiTest'
```

Fake clients/repositories не обращаются к OpenAI. Перед согласованным live проверьте backend через `status` и доступность `http://10.0.2.2:8000/health` с эмулятора. Сценарий хранится в [OpenSpec design](../openspec/changes/archive/2026-09-18-day-15-agent-playground/design.md); перед отправкой payload внешнему provider требуется отдельное разрешение. Live не повторяется автоматически при отказе или ошибке.

## Ручной restart Day 07

После подтверждённого ответа/count 1 остановите backend через Ctrl+C в его
терминале. Во втором терминале выполните force-stop (путь SDK возьмите из `status`):

```powershell
& "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" -s emulator-5554 shell am force-stop com.example.responsecontrollab
```

Не выполняйте `pm clear`, uninstall или очистку app data. Снова запустите
`.\scripts\dev.ps1 backend` в управляемом терминале, проверьте `status`, затем:

```powershell
& "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" -s emulator-5554 shell am start -n com.example.responsecontrollab/.MainActivity
```

Откройте Day 07, проверьте восстановление/count 1 и явно отправьте вопрос о факте.
Зафиксируйте фактический ответ/count 2; `/health` и offline tests этого результата
не доказывают. Остановка во время неопределённой HTTP-отправки в этот сценарий
не входит. Платные запросы автоматически не повторяются.

## Выбор теста и устройства

```powershell
.\scripts\dev.ps1 unit -Test '*TemperatureLabViewModelTest'
.\scripts\dev.ps1 ui -Test 'com.example.responsecontrollab.MetaPromptExpansionUiTest#generatedPromptExpandsAndCollapses'
.\scripts\dev.ps1 emulator -Avd 'Pixel_3a_API_34_extension_level_7_x86_64'
.\scripts\dev.ps1 ui -Serial 'emulator-5554' -Test 'com.example.responsecontrollab.RootNavigationUiTest'
```

`-Avd` и `-Serial` взаимоисключающие; при нескольких устройствах укажите выбор явно. Скрипт ожидает adb и `sys.boot_completed` до 90 секунд (`-ReadyTimeoutSeconds` меняет лимит). После таймаута он не завершает существующий процесс: проверьте логи перед повтором. Обычный запуск сохраняет Quick Boot; настройки анимаций и данные AVD не сбрасываются.

Для логики запускайте соответствующие JVM-тесты. Для UI — затронутый класс/метод; полный набор — после связанных изменений экранов и навигации. Успешную проверку не повторяйте, если соответствующий код не менялся. Текущие UI-тесты не требуют backend или OpenAI; живой запрос — отдельная проверка.

## Gradle и диагностика

Gradle использует daemon и configuration cache. Не добавляйте `--no-daemon`, `--no-configuration-cache`, `--max-workers=1`, `clean` или `--rerun-tasks` без конкретной причины.

JDK ищется в `JAVA_HOME`, PATH, Android Studio и Gradle JDK cache; SDK — в `android-app/local.properties`, `ANDROID_HOME`, `ANDROID_SDK_ROOT` и стандартной папке SDK. Для стабильного выбора между CLI и Studio задайте один установленный JDK через `JAVA_HOME` и Gradle JDK в Studio.

Эксклюзивные блокировки в игнорируемой `.local/environment/` защищают от двух запусков Gradle/backend/emulator через скрипт. ОС освобождает блокировку при выходе или падении процесса; оставшийся файл не мешает следующему запуску. Файл содержит PID владельца. **Прямой gradlew и Android Studio не участвуют в этой защите:** не запускайте сборки одновременно в одном checkout. Не удаляйте занятые lock-файлы и не завершайте все Java/Python-процессы.

Долгую сборку наблюдайте в её исходной сессии: session ID и отсутствие завершения за время одного ожидания не означают зависания. Проверяйте последний вывод и владельца блокировки, не запускайте дубликат.

Скрипт сообщает время подготовки эмулятора, Gradle-команды и всего действия. Длительности самих UI-тестов — в `android-app/app/build/reports/androidTests/`. Логи эмулятора — `.local/environment/emulator.stdout.log` и `emulator.stderr.log`; backend пишет в свою терминальную сессию. Локальные файлы в Git не попадают.

## Day 18 — Dependency Watch

Standalone service находится в [day-18-dependency-watch](../day-18-dependency-watch/README.md).
Python 3.11+, отдельный venv; локально из его каталога:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Для запуска задайте `DAY18_MCP_TOKEN` в environment (случайное значение >=32 символов,
без пробелов), затем `.\.venv\Scripts\python.exe run.py`. Не печатайте token и не
передавайте его аргументом командной строки. По умолчанию SQLite в `.local/day18/`,
HTTP только `127.0.0.1:8018`. `/health` не содержит credentials; `/mcp` требует
`Authorization: Bearer <token>`. Сервис не требует OpenAI key. Owner lock не удаляйте:
ОС освобождает его при завершении процесса. Запускать только через `run.py`, одним
процессом: он останавливает HTTP с exit=1 при падении scheduler. systemd перезапускает его.

### Публичный VPS после выбора hostname

Пользователь выбрал временный `132-243-120-220.sslip.io`; A-запись проверена и указывает
на `132.243.120.220`. Public settings — в [public.conf](../day-18-dependency-watch/deploy/public.conf).
Deployment выполнен; trusted HTTPS, auth/discovery и upstream readiness проверены. Service restart/VPS reboot probes и основной live прошли; фактические результаты — в [live report](../openspec/changes/archive/2026-09-23-day-18-dependency-watch/live-report.md). При смене DNS проверяйте также AAAA.
При ошибке DNS, trusted certificate или принятия endpoint OpenAI остановитесь для review;
автоматический переход на tunnel, self-signed certificate или другой hostname запрещён.
Позже hostname/URL можно заменить в environment Caddy/service/backend без миграции SQLite.
Ubuntu: установите Python/venv и Caddy из официальных пакетов; создайте отдельного
непривилегированного пользователя `day18` без интерактивного входа.

1. Разместите проверенный snapshot в `/opt/day18/releases/<revision>/`, создайте его
   venv, установите `requirements.txt`. Сопоставьте вывод `python deploy/manifest.py`
   локально и на VPS; сохраните manifest и фактические `pip freeze` в безопасном отчёте.
   Symlink `/opt/day18/current` указывает на выбранный release, код принадлежит root.
2. Установите [unit](../day-18-dependency-watch/deploy/day18-watch.service) в
   `/etc/systemd/system/`. `StateDirectory` создаёт `/var/lib/day18` с mode 0700;
   SQLite и owner lock остаются вне release. Секретный environment разместите в
   `/etc/day18/dependency-watch.env` (root:day18, 0640, parent 0750) по
   [шаблону](../day-18-dependency-watch/deploy/service.env.example). Генерируйте token
   на VPS без вывода в терминал, передавайте его только защищённо в backend environment.
3. Для Caddy задайте выбранный `DAY18_MCP_PUBLIC_HOST` в systemd environment Caddy
   и используйте [Caddyfile](../day-18-dependency-watch/deploy/Caddyfile).
   Выполните `caddy validate --config /etc/caddy/Caddyfile`,
   `systemd-analyze verify /etc/systemd/system/day18-watch.service`, затем
   `systemctl daemon-reload` и `systemctl enable --now day18-watch caddy`.
4. Разрешите HTTPS 443/TCP и HTTP 80/TCP для ACME. Сохраните SSH-доступ до применения
   firewall. Port 8018 остаётся loopback-only и закрыт извне. Проверьте доверенный TLS,
   `/health`, 401 без/с неправильным token, authenticated tools/list и чужой Host.
   Authenticated probes читайте token из environment, не из командных аргументов.
5. Безопасные JSON logs: `journalctl -u day18-watch`. Не включайте дампы request headers,
   SDK debug или полный XML. Watch/run/lookup IDs связывают операции с SQLite. Backend
   проверяйте отдельно через `dev.ps1 status`, затем доступ с эмулятора: FastAPI health
   не доказывает OpenAI/MCP readiness.

`DAY18_ALLOW_SHORT_INTERVALS=false` по умолчанию: interval 3600–86400, max_runs 1–100,
максимум пять active watches. Для согласованного короткого acceptance временно включите
`true`: interval 30–3599, max_runs<=3, максимум один active accelerated watch.
После проверки верните `false` и перезапустите service; существующая история сохраняется.

### Recovery, backup и проверка фактов

SQLite — source of truth. Один execution slot уникален по `(watch_id, scheduled_at)`;
это не idempotency create. Fixed UTC grid не выполняет backlog серией. Stale running
становится failed/interrupted и расходует max_runs в одной транзакции с aggregate и
next_run_at. Summary готов сразу после recovery commit; повторный startup не удваивает
counts. Exactly-once upstream не обещается.

Перед backup/rollback остановите service, дождитесь его остановки и скопируйте БД в
закрытый backup directory (0700/0600), затем запускайте снова. Не заменяйте живую SQLite
копированием. При code rollback переключайте symlink только на совместимый со schema
release; неизвестная schema отклоняется без очистки. Restore БД — отдельное явное действие,
которое откатывает историю; обычный code rollback БД не трогает.

Live acceptance требует публичного HTTPS: отдельные service restart/VPS reboot probes,
затем одна Android create attempt `androidx.core:core-ktx`, interval=30/max_runs=3.
Сохраните все actual calls/IDs и время окончания Responses. Остановите локальный backend
и закройте Android на background window; сверьте реальные executions с SQLite и logs.
После возврата backend получите summary отдельным явным запросом. Сравнивайте отдельно
mechanism, временную независимость, aggregate и точность prose. Если первый run случился
до окончания Responses, соответствующий temporal criterion не доказан; timestamps не
исправлять. Отсутствие новых версий — нормальный результат. Overnight необязателен.

Для первой установки подготовлен проверяемый [bootstrap.sh](../day-18-dependency-watch/deploy/bootstrap.sh).
Он требует root через интерактивный `sudo`; пароль вводится пользователем только в SSH terminal.
Рядом должны лежать reviewed `snapshot.tar.gz` и `snapshot.sha256`. Скрипт сверяет archive
и file manifest, отказывается заменять существующий deployment/Caddy config, генерирует
credential только на VPS, разрешает оператору `aiadvent` чтение protected env через группу
`day18` и не печатает token. Сначала открывает SSH в UFW, затем включает firewall;
password/root SSH login отключается после подтверждённого key login. При частичной ошибке
нужен review текущего состояния, а не слепой повтор bootstrap.

[readiness.py](../day-18-dependency-watch/deploy/readiness.py) запускается на VPS release venv
и читает token только из protected env. Выводит безопасный JSON с TLS/auth/discovery/upstream
результатами, без credential. Это техническая readiness, не Android/OpenAI live acceptance.

### Ручные recovery probes с VPS reboot

[recovery_probe.py](../day-18-dependency-watch/deploy/recovery_probe.py) выполняется
отдельно от основного live acceptance и не обращается к OpenAI. `pre` требует sudo:
сохраняет manifest/packages/UFW/sshd evidence, временно включает short intervals,
создаёт два последовательных watch по 30 секунд/max_runs=2 и проверяет service restart.
Перед reboot возвращает normal interval configuration. `post` проверяет boot ID,
сохранённую историю, последующий execution и completed. Ни SSH, ни UFW не изменяются.

Из корня проекта, PowerShell 7:

```powershell
scp .\day-18-dependency-watch\deploy\recovery_probe.py aiadvent@132.243.120.220:/home/aiadvent/day18-deploy/recovery_probe.py
if ($LASTEXITCODE -ne 0) { throw 'Upload failed' }
$localHash = (Get-FileHash -Algorithm SHA256 .\day-18-dependency-watch\deploy\recovery_probe.py).Hash.ToLowerInvariant()
$remoteHash = ssh aiadvent@132.243.120.220 "python3 -m py_compile /home/aiadvent/day18-deploy/recovery_probe.py && sha256sum /home/aiadvent/day18-deploy/recovery_probe.py"
if ($LASTEXITCODE -ne 0 -or ($remoteHash -split '\s+')[0] -ne $localHash) { throw 'Syntax/hash check failed' }
ssh -t aiadvent@132.243.120.220 "sudo /opt/day18/current/.venv/bin/python /home/aiadvent/day18-deploy/recovery_probe.py pre"
```

Обычно около 90 секунд до сообщения `Normal configuration restored. Rebooting.`,
затем SSH disconnect из-за reboot — ожидаемый результат. При traceback остановиться,
сохранить вывод и не повторять `pre`: неизвестный create outcome не даёт права на retry.
`pre` сам откажется работать при наличии `/var/lib/day18-probes/recovery.json`.

После загрузки VPS:

```powershell
ssh aiadvent@132.243.120.220 "/opt/day18/current/.venv/bin/python /home/aiadvent/day18-deploy/recovery_probe.py post" > .\.local\day18-deploy\recovery-result.json
if ($LASTEXITCODE -ne 0) { throw 'Post probe failed; inspect output before proceeding' }
$recovery = Get-Content -Raw .\.local\day18-deploy\recovery-result.json | ConvertFrom-Json
$recovery | Select-Object phase, normal_configuration_restored
$recovery.restart.completed | Select-Object watch_id, status, runs_total, successful, failed, through_execution_id, next_run_at
$recovery.reboot.completed | Select-Object watch_id, status, runs_total, successful, failed, through_execution_id, next_run_at
```

Ожидаются `phase=passed`, normal configuration=true, оба watch completed/runs_total=2,
next_run_at=null, разные boot IDs и сохранённый prefix executions. Failed lookup также
расходует max_runs; его наличие остаётся в evidence и не превращается в success.
Полный безопасный JSON нужен для review; token/пароль отсутствуют. `post` только читает
и может быть повторён после проверки причины ошибки; новый watch он не создаёт.
