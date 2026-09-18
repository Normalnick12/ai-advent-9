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
