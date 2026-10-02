# Окружение разработки Windows

Настройка и команды для [backend](../backend/README.md) и
[Android-клиента](../android-app/README.md). `dev.ps1` работает в PowerShell 7
из любого каталога; инструменты и зависимости автоматически не устанавливает.
Команды ниже выполняются из корня репозитория, если не указано иное.

## Day 23 — Query rewrite и relevance filtering

Используйте existing backend Python environment; FastAPI, Android и Gradle не нужны.
Из корня repository в PowerShell 7:

```powershell
$python = '.\backend\.venv\Scripts\python.exe'
$ragCli23 = 'backend/scripts/day23_rag.py'
& $python $ragCli23 --help
Push-Location backend
try {
    & .\.venv\Scripts\python.exe -m pytest tests/test_first_rag.py tests/test_rewrite_filter_rag.py -q
} finally {
    Pop-Location
}
```

Frozen config: Top-N=10, cosine threshold=0.50, final Top-K<=5, один LLM rewrite
только по question. Единственный live выполнен 2 октября 2026 после 37 focused
offline tests и сохранения config/questions. Semantic pre-runs отсутствовали.
Команды двух stages ниже документируют уже выполненную отправку: требуют backend
`OPENAI_API_KEY` и означают новые calls, а не просмотр. Не повторяйте их:

```powershell
$baseline22 = 'backend/.local/day22/f7b78426-9672-437f-ab93-717a826934da'
& $python $ragCli23 retrieve --baseline $baseline22
# compare уже выполнен; использовал этот saved retrieval без повторного поиска.
$result23 = 'backend/.local/day23/facf8d92-bd1d-482f-bf6e-2585565f6904'
& $python $ragCli23 compare $result23
```

При полном успехе stages дают 20 и 10 calls соответственно; baseline=0.
В сохранённом run все 30 calls completed; retained counts Q01–Q10:
2/4/5/3/2/5/5/5/5/2. Manual review заполнен; рядом есть `report.txt` со всеми
полными карточками. Raw run/Qxx не редактировались вручную; frozen config и
hashes исходного Day 22 baseline остались прежними.
Не повторяйте retrieve/compare ради улучшения. Technical failures/unknown остаются
evidence. Не изменяйте run/baseline/Qxx JSON вручную; заполняйте только review.json.
В manual review: rewrite_preserves_intent=yes/partial/no,
rewrite_added_project_assumption=yes/no и короткая note при необходимости;
per-fact context/answer=yes/partial/no, существенные claims grounded=yes/no.
Null/pending и unavailable не означают semantic no. Q10 context=no относится
к искомым RPO/RTO; честный no-answer может получить answer coverage=yes.

Offline просмотр и видео без API calls:

Для скринкаста используйте компактный `--video`: summary, затем Q05 regression,
Q07 Top-K limit и Q10 без RPO/RTO evidence. Числа и coverage берутся из saved
run/review. Candidates: kept и явные ссылки `candidate N` / `rank=N` в fact notes;
форматтер не определяет релевантность заново. TAKEAWAY сравнивает per-fact labels
и показывает saved review, без evaluator. Для записи из корня repository:

```powershell
$python = '.\backend\.venv\Scripts\python.exe'
$ragCli23 = 'backend/scripts/day23_rag.py'
$result23 = 'backend/.local/day23/facf8d92-bd1d-482f-bf6e-2585565f6904'
& $python $ragCli23 report $result23 --video
& $python $ragCli23 report $result23 --question Q05 --video
& $python $ragCli23 report $result23 --question Q07 --video
& $python $ragCli23 report $result23 --question Q10 --video
```

Подробный evidence report без `--video` сохраняет прежний формат:

```powershell
$result23 = 'backend/.local/day23/facf8d92-bd1d-482f-bf6e-2585565f6904'
& $python $ragCli23 report $result23
& $python $ragCli23 report $result23 --question Q07 --full
& $python $ragCli23 report $result23 --question Q08 --full
& $python $ragCli23 report $result23 --question Q10
```

Карточка показывает original → rewrite → Top-10 → threshold/kept/dropped →
final context → saved baseline answer → enhanced answer → per-fact/manual review.
Report требует только Day 23 result folder. Threshold откалиброван на original
Day 22 queries с участием Q10; rewritten scores изменятся, поэтому comparison
не независимый benchmark. Dropped count не является semantic relevance оценкой.

## Day 22 — Первый RAG-запрос

Используйте существующее backend Python environment и сохранённый Day 21 index.
Сервер, эмулятор и Gradle не нужны. Из корня в PowerShell 7:

```powershell
$python = '.\backend\.venv\Scripts\python.exe'
$ragCli = 'backend/scripts/day22_rag.py'
$indexRun = '3a3c3319-5516-4526-8e56-33ab1251da72'
Push-Location backend
try {
    & .\.venv\Scripts\python.exe -m pytest tests/test_first_rag.py -q
} finally {
    Pop-Location
}
& $python $ragCli --help
```

Backend environment/игнорируемый `backend/.env` содержит `OPENAI_API_KEY`.
Единственный основной live run уже выполнен 29 сентября 2026 после offline checks
и фиксации questions/config. Команда ниже документирует отправку, а не просмотр:

```powershell
& $python $ragCli eval --run $indexRun
```

При нормальном завершении это 10 query embedding и 20 generation calls.
Не запускайте сначала search/ask этих контрольных вопросов для настройки и не
повторяйте eval ради лучших ответов. Technical failure/unknown остаётся evidence;
при failed query RAG не отправляется. Уже сохранённые calls не повторяются.

CLI печатает `Evidence: ...` до calls и `Saved evidence: ...` после обхода вопросов.
Для просмотра выполненного run и записи видео без новых provider calls:

```powershell
$result = 'backend/.local/day22/f7b78426-9672-437f-ab93-717a826934da'
& $python $ragCli report $result --question Q01 --retrieval-only
& $python $ragCli report $result --question Q01
& $python $ragCli report $result --question Q08 --full
& $python $ragCli report $result --question Q10
& $python $ragCli report $result
```

Карточка показывает QUESTION → RETRIEVED TOP-5 → DIRECT ANSWER → RAG ANSWER →
EXPECTED FACTS / REVIEW; `--full` раскрывает тексты hits, `--retrieval-only` —
только сохранённый search stage. Все report помечены SAVED RUN. Report не требует
API key, Day 21 DB или рабочих source files. Не изменяйте run/Qxx JSON вручную.
В этом run уже сохранены заполненный `review.json` и текстовый `report.txt`
с общей таблицей и карточками всех десяти вопросов. Ручной разбор выполнил Codex
по сохранённым текстам; отдельный evaluator/LLM judge не запускался.

В `review.json` укажите reviewer, заполните per-fact labels и notes со ссылками
на S-label/chunk/цитату; добавьте существенные RAG claims (claim, grounded_in_retrieved_context,
notes), diagnosis и status=reviewed после разбора. Не заполняйте оценки
недоступных ответов: оставьте null, report обозначит unavailable. Для Q10 context
presence искомых RPO/RTO = no, честное признание недостатка информации в answer
может получить coverage=yes; diagnosis — knowledge coverage/no-answer. Пустой
Top-5 для этого не требуется. Scores не являются вероятностью релевантности.

Отдельные explicit команды для произвольного вопроса доступны независимо от eval:

```powershell
$question = 'Ваш новый вопрос о проекте'
& $python $ragCli search $question --run $indexRun --full
& $python $ragCli ask $question --mode direct
& $python $ragCli ask $question --mode rag --run $indexRun
```

Search расходует 1 embedding/0 generation calls, direct — 0/1, RAG — 1/1.
Они сохраняют отдельный evidence directory. `--db PATH` меняет расположение базы;
eval проверяет pinned run/hash. Top-K фиксирован на 5. SQLite/evidence/ключи
остаются локальными и игнорируются Git. Offline tests используют только fake clients.

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

## Day 21 — Индексация документов

CLI не требует запущенного backend или эмулятора. Из корня репозитория в PowerShell 7:

```powershell
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\backend\.venv\Scripts\python.exe -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
& .\backend\.venv\Scripts\python.exe backend/scripts/day21_index.py corpus
& .\backend\.venv\Scripts\python.exe backend/scripts/day21_index.py preview
```

Установка и первая инициализация tokenizer могут использовать сеть. Последующие
corpus/preview и offline tests работают без OpenAI/API key. Чтобы подробно показать
один заранее выбранный участок, добавьте к preview `--example atomic-turn`,
`--example sqlite-commit`, `--example android-restore` или `--example task-send`.
Вывод показывает исходник с номерами строк, затем полный текст пересекающих его
fixed-size chunks и structure-aware chunks с metadata. Все четыре примера
зафиксированы в manifest до результата, включая длинные блоки с fallback.

Явный live build использует `OPENAI_API_KEY` из environment или игнорируемого
`backend/.env`, отправляет выбранный corpus в OpenAI и расходует API tokens:

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/day21_index.py build --strategy both
```

После успешного commit команда выводит `Saved run: <UUID>` и путь SQLite.
Подставьте этот UUID вместо `RUN_ID` в новом процессе:

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/day21_index.py compare --run RUN_ID
& .\backend\.venv\Scripts\python.exe backend/scripts/day21_index.py inspect --run RUN_ID --example sqlite-commit
```

Эти команды читают сохранённые тексты/vectors и не вызывают OpenAI. Inspect также
принимает `--source backend/app/sqlite_conversation_store.py` или `--chunk CHUNK_ID`.
По умолчанию показаны dimension и первые шесть координат; `--full-vector` раскрывает
vector целиком. `--db PATH` выбирает локальную базу вместо стандартной
`backend/.local/day21/index.sqlite3`. Индекс не добавляйте в Git.

Offline checks, из каталога backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_document_indexing.py -q
```

Тесты используют fake provider только внутри temporary test storage. Они проверяют
chunking, metadata, embedding count/dimension и SQLite round-trip, но не качество
embeddings. При ошибке build выходит nonzero без готового неполного run. Не
запускайте второй build автоматически: новая попытка повторяет embedding calls.

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

## Day 19 — композиция MCP

Порядок: offline → изолированное deployment/readiness → pre-live sizing → одна
live-попытка. Поручение на все эти этапы достаточно; технические gates не требуют
нового разрешения на каждый переход. Не пройденный gate останавливает следующий.
Нет нового Android экрана, scheduler или SQLite Day 19.

Из `day-19-mcp-composition` создайте отдельный `.venv`, установите
`requirements-dev.txt` и выполните `.venv/Scripts/python.exe -m pytest tests -q`.
Windows требует Developer Mode для реального symlink-теста. Его нельзя пропускать
ради PASS. Backend regression command приведён в [backend](../backend/README.md#композиция-mcp--day-19).
Тесты используют MockTransport и временные каталоги, без Google Maven/OpenAI/VPS.

Deployment artifacts: [systemd](../day-19-mcp-composition/deploy/day19-composition.service),
[Caddy fragment](../day-19-mcp-composition/deploy/Caddyfile.fragment),
[installer](../day-19-mcp-composition/deploy/install.py),
[readiness](../day-19-mcp-composition/deploy/readiness.py).
Отдельные user/process `day19`, loopback 8019, host с HTTPS `/mcp`, state
`/var/lib/day19/reports` (0700), protected `/etc/day19/composition.env` (0640),
release `/opt/day19/releases/<manifest-revision>`, current symlink. OpenAI key
на VPS не нужен. MCP Bearer обязателен до discovery; Host/Origin проверяются.
Запрос ограничен 32 MiB, upstream XML — 2 MiB и 15 s. Файлы накапливаются по hash;
автоматического удаления нет. Сверяйте свободное место до эксперимента.

После offline создайте reviewed snapshot: из Day 19
`.venv/Scripts/python.exe deploy/snapshot.py ../.local/day19-deploy/snapshot`.
Сохраните manifest и archive SHA-256, передайте snapshot на уже настроенный VPS,
сверьте hash и распакуйте в новый каталог. Installer вызывается от root как
`python3 deploy/install.py <unpacked-source> <day19-host>` и отказывается от повторной
первой установки. Он добавляет отдельный Caddy host, проверяет конфигурацию и
reload Caddy, не рестартует Day 18 и не меняет SSH/firewall. При частичной ошибке
сначала исследуйте состояние. До/после сохраните discovery старых endpoints,
PID/start time Day 18 и исходный Caddyfile. Readiness:
`sudo -u day19 /opt/day19/current/.venv/bin/python /opt/day19/current/deploy/readiness.py`.
Это TLS/auth/discovery/manifest/permissions, без model generation и создания watch.

Для фактической частичной установки 24 сентября initial install повторять нельзя.
Проверенное состояние, новый архив и порядок Caddy-only recovery описаны в
[deployment handoff](../day-19-mcp-composition/DEPLOYMENT-HANDOFF.md).
Исправленный installer получает переменные из systemd Environment Caddy и валидирует
candidate до создания Day 19 ресурсов. Режим `--resume-caddy-from <existing-revision>`
сверяет прежний runtime и backup, сохраняет credentials/releases и меняет только
Caddy route. Оператор успешно выполнил resume и readiness; pre-live тоже PASS.
Единственная live-попытка и независимая проверка завершены: chain/final/full acceptance PASS.
Операторский export server events и actual file bytes сохранён отдельно, прежняя трасса
и предварительные NOT_PROVEN неизменны. Результат и evidence в handoff; launcher не повторять.

Pre-live: установите Day 19 URL/token только в окружении локального процесса.
`preflight.py <new-preflight.json>` делает один direct MCP lookup core-ktx,
сохраняет полный ответ и не вызывает summarize/save или модель.
`sizing.py <preflight.json> <readiness.json> <new-sizing.json>` измеряет все объекты,
schemas и prompt, downstream arguments и final, использует консервативную оценку
по UTF-8 bytes с запасом. Проверенные model limits имеют ссылку в artifact.
Это estimate, не billing. Полный список также прогоняется через offline fixture
перед live; insufficient budget блокирует live, без сокращения/другого artifact.

После PASS всех gates запустите backend с выбранными budget/deadline и выполните
ровно один раз из Day 19:
` .venv/Scripts/python.exe launch.py ../.local/day19-live/attempt --deadline 660`.
Deadline launcher должен превышать backend deadline. Уже существующий attempt
directory запрещает повторную отправку. Сохраните output и native backend evidence;
на timeout/ошибку/неверную цепочку не делайте retry или forced continuation.

Независимый collector выполняется после попытки отдельно от tools:
`sudo -u day19 /opt/day19/current/.venv/bin/python /opt/day19/current/collect.py file
<64hex-file-id> <operation-id> <lookup-id> <revision> <endpoint>` (одна команда).
Он читает actual bytes только из fixed root, экспортирует base64/size/hash/time;
не сериализует report и не вызывает save. Журнал:
`sudo /opt/day19/current/.venv/bin/python /opt/day19/current/collect.py events <since>`.
Сохраните stdout каждого как отдельный JSON. Затем локально:
`verify.py <operation.json> <events.json> <file-read.json> <new-verdict.json>`.
Если response утрачен, сохраняйте unknown и read-only диагностику, не создавайте
недостающий файл. Chain и final_text_accuracy оцениваются независимо; original
evidence неизменно. Одна попытка не доказывает надёжность будущих запусков.

Rollback: остановить только `day19-composition`, убрать только добавленный Day 19
host block, выполнить Caddy validate/reload. `/etc/day19/Caddyfile.before-day19`
можно восстановить целиком лишь после проверки отсутствия последующих изменений.
Reports и evidence сохранить. Day 18 process/SQLite не трогать. Finish/archive/
commit/push остаются отдельной задачей пользователя.

## Day 20 — подготовка и один отдельный live

Команды ниже выполняются из корня репозитория в PowerShell 7.
Новый deployment, Android build и серверный save не нужны. Для восстановления
существующего credential отдельно разрешили чтение env через SSH; это не часть
model flow, VPS не изменялся.

Offline suite (fakes и synthetic traces; без внешних research/lookup calls):

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest tests/test_mcp_orchestration.py ../day-20-mcp-orchestration/tests tests/test_mcp_composition.py tests/test_mcp_lab.py tests/test_dependency_watch.py tests/test_dependency_watch_summary.py tests/test_dependency_watch_evidence.py tests/test_api.py -q
Pop-Location
```

Подготовка: задайте локально переменные из [backend README](../backend/README.md).
Старые Day 19 SSH launchers не применять. Запустите backend в отдельной
управляемой терминальной сессии: `pwsh -File scripts/dev.ps1 backend`;
в другой сессии — `pwsh -File scripts/dev.ps1 status`.
`/health` подтверждает FastAPI, а не OpenAI или MCP credentials.

Discovery-only проверка использует существующий Day 16 venv (`mcp==2.2.0`)
и переменные текущего shell; она не загружает backend `.env` автоматически.
Выберите новый output filename:

```powershell
day-16-mcp-discovery/.venv/Scripts/python.exe day-20-mcp-orchestration/readiness.py .local/day20-readiness.json
backend/.venv/Scripts/python.exe day-20-mcp-orchestration/sizing.py .local/day20-sizing.json
```

Readiness выполняет только protocol negotiation и `tools/list`, без `tools/call`.
Она сохраняет definitions и blockers отдельно от model trace. Если token отсутствует,
Dependency discovery получает `NOT_PROVEN`. Отдельно разрешённое восстановление
credential уже выполнено; секрет передан process environment и в Git не хранится.

Единственная live-попытка уже выполнена. Следующая команда документирует запуск
эксперимента; для просмотра результата её повторять не нужно:

**Команда отправки (не offline-просмотр):**

```powershell
backend/.venv/Scripts/python.exe day-20-mcp-orchestration/run.py --live
```

Это одна отправка; deadline CLI по умолчанию 930 секунд. Без `--live` запрос
не отправляется. Модель исследует repository и выбирает по одному артефакту
для хранения и фоновой работы. По полученным coordinates она может обратиться
к другому серверу за публикациями и сводкой. Между ветками допускается любой
порядок, сохраняющий их зависимости. Не повторяйте live ради лучшего результата.

На завершении CLI покажет `report.md`. На потере HTTP-ответа сначала найдите
новый attempt directory в `backend/.local/day20`; повторная отправка запрещена.
Сохранённые данные можно проверять без сети:

```powershell
backend/.venv/Scripts/python.exe day-20-mcp-orchestration/verify.py backend/.local/day20/<operation-id>
```

Если `review` уже существует, используйте `--output <новый-каталог>`.
На видео можно показать задачу и два descriptors, затем фактическую DeepWiki
capability, две найденные зависимости и их Maven summaries в отчёте.
Отдельно покажите flow verdict, final facts и ограничения. Это демонстрация
сохранённой первой попытки, не повтор сценария. Пользователь подтвердил запись видео.

Сохранённую в Git попытку можно проверить без backend, credentials и сети:

```powershell
backend/.venv/Scripts/python.exe day-20-mcp-orchestration/verify.py day-20-mcp-orchestration/evidence/live-20260925 --output .local/day20-offline-review
```

Output directory должен быть новым. Исходные файлы не перезаписываются.
Проверка воспроизводит также сохранённые provenance FAIL / NOT_PROVEN.
