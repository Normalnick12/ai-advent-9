# Android-приложение

Android-клиент AI Advent на Kotlin, Jetpack Compose и Material 3.
Содержит каталог экспериментов, позволяет отправлять запросы и просматривать
ответы и метрики. Работает через локальный backend; API-ключ приложению не нужен.

- [Backend](../backend/README.md)
- [Настройка, запуск и проверки](../scripts/README.md)
- [Описание и результаты экспериментов по дням](../README.md#задания)

## Agent Playground — Day 15

В каталоге откройте «День 15 — Контролируемый жизненный цикл задачи». «Новая задача» открывает выбор Profile и четырёх ограничений, затем review и подтверждение создания. Эти ограничения сохраняются для всей задачи; Profile можно переключать для следующих ответов.

Основной экран содержит этап, следующий шаг, разговор и разрешённые lifecycle actions. «Уточнить требования» и «Проверка не пройдена» явно возвращают задачу по разрешённому ребру. Учебный forbidden skip находится отдельно. Результат lifecycle показывается карточкой и не добавляется в chat.

Inspector ответа или операции показывает summary, раскрываемые Memory/Profile/State/Invariants/Request/Validation/Lifecycle/commit sections и различает Current и Used in this turn. Raw Debug открывается отдельно. Хранятся последние 50 receipts в памяти процесса; после eviction/restart старые ответы остаются, а их диагностика обозначается unavailable.

После неопределённой отправки приложение читает authoritative state и не повторяет POST. При недоступном backend используйте «Прочитать состояние». Pause оставляет возможность обсуждать уточнения, Done делает conversation read-only. Setup, Send и events не запускаются при открытии экрана или повороте устройства.


## Первый MCP-инструмент — Day 17

В каталоге откройте «День 17 — Первый MCP-инструмент». По умолчанию заполнен запрос
`androidx.core:core-ktx` и выбран режим «Проверить вызов». «Отправить» создаёт одну попытку;
«Автовыбор» оставляет решение о tool модели. Backend URL настраивается по общей инструкции,
а remote MCP URL — только на backend.

Под ответом отображается краткий outcome. Inspector показывает imported tools и каждый
реальный call: arguments, optional status, result/error и response/call/lookup ids.
Новая отправка очищает старое evidence. Поворот и возврат из каталога не повторяют запрос;
после process death отправка возможна только новым явным действием.

Проверки из корня через PowerShell 7:
`./scripts/dev.ps1 unit -Test '*McpLab*'`,
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.McpLabUiTest'`, затем
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.RootNavigationUiTest'`.
UI-команды запускаются последовательно; backend/OpenAI для них не требуются.

## Фоновые проверки — Day 18

Карточка Day 18 находится после Day 17. «Создать» отправляет явный запрос регистрации,
«Сводка» читает выбранный watch отдельной agent operation. По умолчанию create
предлагает interval=21600 и max_runs=3; для короткого live interval=30 разрешается
только специальной конфигурацией VPS. Повторное нажатие блокируется до ответа;
автоматических retry, regeneration или запросов при открытии/повороте нет.

Подтверждённые IDs, параметры и выбор сохраняются в `day18_watch_receipts_v1`.
После process death показаны последние известные сведения, сводка сама не запрашивается.
Все IDs из нескольких create calls доступны для выбора. Неизвестный исход новой
попытки не удаляет прошлый receipt. Typed summary и объяснение модели показываются
отдельно; Inspector раскрывает каждый actual call, discovery и submitted snapshot.
Для фоновых checks приложение и локальный backend не нужны; для agent operations
backend должен работать. Token не настраивается и не хранится в Android.

Проверки через PowerShell 7, последовательно:
`./scripts/dev.ps1 unit -Test '*DependencyWatch*'`,
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.DependencyWatchUiTest'`,
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.DependencyWatchNarrowUiTest'`,
`./scripts/dev.ps1 ui -Test 'com.example.responsecontrollab.RootNavigationUiTest'`.
