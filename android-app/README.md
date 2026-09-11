# Android-приложение

Клиент на Kotlin, Jetpack Compose и Material 3 для работы с локальным FastAPI
backend. Позволяет отправлять запросы, сравнивать ответы и просматривать метрики.
Все обращения к OpenAI выполняет backend; API-ключ в приложении не нужен.

При запуске открывается каталог «AI Advent» с днями 02–10. Нажмите карточку,
чтобы открыть урок; верхняя стрелка или системное действие назад возвращает
к списку дней. Day 01 доступен отдельно как Python CLI.

Запросы, настройки, результаты, история и положение экрана сохраняются при
переходах между днями в текущей сессии. Выполняющийся эксперимент продолжает
работу при уходе в каталог. После завершения процесса локальный UI transcript и runtime metrics не сохраняются;
Day 10 отдельно восстанавливает сохранённые backend experiment outputs.
Day 07 восстанавливает только identity текущего диалога и число ходов с backend.

Day 10 — [разные стратегии контекста](../day-10-context-strategies/README.md):
scenario-first экран с независимыми Окно/Факты/Ветки. Canonical fixtures загружаются
read-only с backend; «Подготовить шаг», раскрытие полного текста, Send и «Далее»
разделены. Каждый Send передаёт исходный текст, step/revision/attempt и explicit
branch target, без conversation history. Старые шаги доступны в compact timeline.

После шести shared шагов Branching требует checkpoint, затем A и B продолжаются
отдельно. Facts inspector показывает actual scoped values и отменённые записи,
редактирование отсутствует. После восьмого Send проверки ТЗ A/B запускаются
отдельными кнопками и не создают девятый conversation turn. Dashboard только читает
состояние: требования N/11, pre-evaluation retention, known tokens/coverage и
management actions. Navigation/strategy switch/disclosure не вызывают provider.

Текущая Day 10 identity — `day10-gpt4o-mini-n6-v3`. Preferences находятся в
`context_strategies_day10-gpt4o-mini-n6-v3`; старые файлы v1/v2 сохраняются, но их
IDs/progress/pending attempts/results не восстанавливаются в v3. Смена version
не создаёт runs и не вызывает provider. Все три новых runs создаются только
первым explicit Send; финальный dashboard использует только v3. Backend и Android
должны работать с одной version; v1/v2 metadata отклоняются без fallback.
Targeted JVM: `pwsh -File scripts/dev.ps1 unit -Test '*ContextStrategies*Test'`
из корня репозитория; тесты используют temporary preferences и fake/mock backend.

Versioned preferences сохраняют отдельные IDs, prepared step, strategy/branch и
число переключений. Confirmed progress/facts/topology/results берутся с backend.
Unknown HTTP outcome запускает read-only reconciliation; replay возможен только
по новому явному действию. Runtime receipts deduplicate attempt IDs, после process
recreation полный accounting помечается неполным. Live acceptance не проводился.

Targeted проверки из корня проекта через PowerShell 7:
`./scripts/dev.ps1 unit -Test '*ContextStrategies*'` и
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.ContextStrategiesUiTest'`.
Тесты используют mock HTTP/fake repository, не backend/OpenAI. Полные `unit`,
`build`, `ui` запускаются последовательно по [scripts README](../scripts/README.md).
Отдельный font-scale smoke не требуется; существующие accessibility tests сохранены.

Day 05 — [лаборатория моделей](../day-05-model-benchmark/README.md): три выбранные
модели решают один benchmark, экран показывает проверку, время, токены и стоимость.

Day 06 — [первый агент](../day-06-first-agent/README.md): русский chat UI,
несколько сообщений и «Новый диалог». UI transcript служит только отображению;
Android отправляет одно сообщение и session ID, без history, instructions,
model/settings или API key. Первая отправка создаёт session. Успешный reset
оставляет экран без session ID до следующей отправки. После потери backend
session или неизвестного результата отправки требуется явный новый диалог.

Day 07 — [сохранение контекста](../day-07-context-persistence/README.md): отдельная
карточка «Сохранение контекста» использует общий chat UI с независимым от Day 06
keyed ViewModel. Day 07 хранит `session_id` в private SharedPreferences
`day_07_current_session` через CurrentSessionStore. Чтение и проверяемый commit
выполняются вне main thread. После create запись ID должна завершиться до send.

При первом входе после cold start отсутствие ID оставляет пустой экран без HTTP.
Сохранённый ID проверяется через metadata GET: экран показывает восстановление,
backend count и «Диалог восстановлен. Предыдущие сообщения не отображаются».
История не загружается в Android и не отправляется заново; следующий POST содержит
только новое `message`. Ошибка восстановления допускает явный повтор, 404 — сброс.
«Новый диалог» сначала получает DELETE 204, затем подтверждает очистку локального
ID и сбрасывает UI. Ошибки записи/очистки не маскируются успешным состоянием.
Day 06 не сохраняет локальный ID, но работает с тем же durable backend.

Для ручной проверки Day 07 дождитесь успешного факта/count 1, полностью остановите
backend и force-stop приложение **без очистки app data**. Запустите backend,
затем приложение и откройте Day 07: ожидаются restored/count 1 без старых bubbles.
Явно спросите факт: ожидаются ответ/count 2. Команды управления процессами —
в [scripts README](../scripts/README.md). Activity recreation в UI-тестах
не заменяет эту проверку. Crash во время неопределённого HTTP turn, восстановление
pending/recoveryRequired и автоматический replay не поддерживаются.

## Требования

Android Studio, JDK 17 или совместимый более новый JDK, Android SDK
и Android Emulator. Для общего скрипта запуска нужен PowerShell 7.
Зависимости загружаются при Gradle Sync.

## Запуск

1. Запустите [backend](../backend/README.md) на порту `8000` в отдельном терминале.
2. Откройте папку `android-app` в Android Studio и дождитесь Gradle Sync.
3. Из корня репозитория выполните `.\scripts\dev.ps1 emulator` или выберите
   уже запущенный Android Emulator в Studio.
4. Запустите конфигурацию `app`.

Эмулятор подключается к серверу на компьютере по `http://10.0.2.2:8000/`.
Локальное HTTP-соединение разрешено в debug-сборке.
Переменные окружения для приложения не требуются.

## Сборка и тесты

Из корня репозитория в PowerShell 7:

```powershell
.\scripts\dev.ps1 unit
.\scripts\dev.ps1 build
.\scripts\dev.ps1 ui -Test 'com.example.responsecontrollab.MetaPromptExpansionUiTest'
```

Для полного UI-набора уберите `-Test`. Backend текущим UI-тестам не нужен.
Скрипт выбирает установленный JDK, блокирует конкурирующие запуски через себя
и переиспользует эмулятор. Не запускайте параллельно сборки напрямую через
`gradlew.bat` или Android Studio. Параметры выбора теста и устройства,
диагностика и ограничения: [окружение Windows](../scripts/README.md).


## Day 08 — Работа с токенами

Карточка 08 открывает отдельный TokenLabViewModel. Day 08 session ID сохраняется
только в preferences `day_08_current_session`, до первого send/prepare.
После cold start восстанавливаются ID/count через GET; transcript, diagnostics
и таблица последних 20 попыток предыдущего запуска отсутствуют. Day 06/07
сохраняют прежний ChatViewModel. Общими остаются только stateless bubble/composer.

Обычная «Отправить» сразу запускает backend preflight и одну generation,
без отдельного Preview. Current/history показаны как самостоятельные provider
counts с formatting, full preflight — как контекст с инструкциями; эти значения
не складываются. Actual usage и оценочная стоимость не вычисляются Android.
Неизвестные значения не заменяются нулём, маленькие USD не округляются до центов.

Кнопка длинного текста вставляет 200 видимых редактируемых строк без auto-send.
«Подготовить переполнение» выполняет только counting и показывает размер,
рецепт, образцы и digest нового payload. «Выполнить один overflow-запрос»
открывает отдельное подтверждение. Подготовка одноразовая и истекает через
10 минут; повторные нажатия/навигация не повторяют generation. Отмена убирает
локальную подготовку, backend RAM запись ограничена TTL. History не возвращается
на экран и не отправляется обратно.

При подтверждённой context error можно продолжить коротким сообщением.
Unknown normal-send outcome требует явного «Новый диалог»; unknown probe —
read-only проверки доступности диалога, без повтора использованного разрешения.
Подготовка и реальные short/long/overflow результаты — разные стадии;
offline UI tests используют fake repositories и не вызывают OpenAI.

## Day 09 — Управление контекстом: сжатие истории

[Лаборатория](../day-09-history-compression/README.md) имеет один
CompressionLabViewModel на вложенные Chat/Details. Основной экран показывает
chat, compact card последнего normal request (FULL/COMPRESSED, signed delta,
summary count и фактический raw tail при fixed N=4), composer и кнопку
«Статистика и сравнение». Details содержит context/phase diagnostics, раздельные
расходы summarization/response/compare, раскрываемую durable summary и явное
сравнение. На узком экране результаты идут вертикально, от 720dp — рядом.
Back: Details → Chat → каталог; IME закрывается первым. Navigation/recreation
сохраняют drafts/scroll/results и не запускают generation заново.

ID записывается до первого send в отдельные config-versioned preferences
`day_09_current_session_day09-gpt4o-mini-tail4-v1`, исключённые из backup.
Cold start делает только metadata GET: восстанавливаются identity/count/summary
metadata. Bubbles, observations и totals прошлого process не восстанавливаются.
Summary читается явным раскрытием, без paid repair. Reset удаляет backend
session и затем local ID/state. Unknown send требует явного reset; unknown
compare — read-only refresh, без automatic replay. Отдельный client:
read timeout 220s, call timeout 240s, retries=0; budgets Day 02–08 не меняются.

Backend возвращает metrics отдельной операции. VM deduplicates attempt IDs
и суммирует только observations текущего process, раздельно maintenance summary,
chat replies, compare preparation и обе compare branches. Неполное покрытие
usage/cost явно отмечается. Token saving не выдаётся за net денежную экономию.
Current durable summary и local compare summary подписаны отдельно;
compare result показывает snapshot freshness.

Для одного live прогона начните новый Day 09 диалог. Четыре раза используйте
«Вставить учебный шаг» и отдельно «Отправить»: identifier, limit, responsible,
нейтральный запрос. Длинный текст виден в composer и доступен для полного чтения.
Перед четвёртым turn впервые создаётся durable summary. В Details нажмите
«Проверить три факта»: значения отсутствуют в comparison question.
Результат N/3 проверяет только точное сохранение трёх фактов, не качество текста.
Если assistant повторил ранний факт в raw tail, результат будет not applicable.
Не повторяйте paid compare ради желаемого score или savings.

Итоговый ручной live experiment записан в Day 09 README: FULL=2/3,
COMPRESSED=1/3, actual input/output/cost обеих branches. Старые ошибочные UI
scores parser не являются итоговыми результатами. Maintenance usage/cost
наблюдались отдельно; их численные значения в отчёт не переданы.

Пользователь подтвердил restart: session/count=4 восстановлены, старых bubbles
нет, runtime measurements и compare results очищены, paid replay отсутствует.
Чтение durable summary после restart и reset также подтверждены пользователем:
после сброса старый диалог не восстанавливается.

Offline команды из корня: `.\scripts\dev.ps1 unit`,
`.\scripts\dev.ps1 build`,
`.\scripts\dev.ps1 ui -Test 'com.example.responsecontrollab.CompressionLabUiTest'`.
После изменений navigation выполняется полный `.\scripts\dev.ps1 ui`.
UI tests используют fake repositories, без backend и OpenAI.
