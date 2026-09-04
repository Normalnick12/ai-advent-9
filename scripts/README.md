# Окружение разработки Windows

`dev.ps1` работает в PowerShell 7 из любого каталога. Использует существующие JDK 17+, Android SDK и `backend/.venv`; инструменты и зависимости автоматически не устанавливает. Первичная настройка — в [Android README](../android-app/README.md) и [backend README](../backend/README.md).

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
