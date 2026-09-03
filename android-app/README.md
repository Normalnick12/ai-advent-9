# Response Control Lab Android app

Минимальный Android-клиент Day 02 на Kotlin, Jetpack Compose и Material 3. Экран
поддерживает режимы FREE, CONTROLLED и COMPARE, а OpenAI API key в приложение не
передаётся.

В том же `app` module доступен экран
[Day 03 Reasoning Lab](../day-03-reasoning-strategies/README.md). Нижняя
навигация переключает «Управление ответом» и «Лаборатория рассуждений» без
дополнительной navigation library.

## Открытие и сборка

1. Откройте папку `C:\Projects\ai-advent-9\android-app` в Android Studio.
2. Дождитесь Gradle Sync и используйте JDK 17 или совместимый более новый JDK
   (командная сборка проверена с существующим JDK 21).
3. Запустите backend на порту `8000`.
4. Выберите Android Emulator и запустите конфигурацию `app`.

Командная сборка из PowerShell:

```powershell
cd C:\Projects\ai-advent-9\android-app
.\gradlew.bat testDebugUnitTest assembleDebug
```

## Локальный backend

Android Emulator использует `10.0.2.2` как специальный адрес host-машины, поэтому
base URL клиента — `http://10.0.2.2:8000/`, а не `localhost`. Cleartext HTTP разрешён
только debug-манифестом и только для `10.0.2.2`; release-сборка не получает эту
network-security config.

Retrofit использует явный OkHttpClient: connect `10 с`, write `30 с`, read
`180 с`, общий call timeout `190 с`. Этот бюджет покрывает backend timeout
`75 с` и один ограниченный retry OpenAI SDK. Бесконечных и прикладных повторов
Android не делает; `retryOnConnectionFailure=false` не дублирует POST скрыто. Если
клиентский timeout всё же сработает, UI показывает отдельное
сообщение `Android timeout`; timeout upstream возвращается как `openai_timeout`.

Для Reasoning Lab тот же 190-секундный budget покрывает два последовательных
75-секундных META_PROMPT-вызова без SDK retries. Один tap отправляет один batch
request; во время loading повторная кнопка отключена. Частичная ошибка остаётся
в карточке своей стратегии.

## Проверка COMPARE

1. Оставьте prompt `Составь рецепт греческого салата.`.
2. Выберите `COMPARE`.
3. Оставьте включёнными Structured JSON, Length limit (`600`) и Finish instruction.
4. Нажмите Generate.
5. Сравните обычный FREE-текст и предсказуемый CONTROLLED JSON, а также status,
   request id, output tokens и фактически применённые controls.

## Проверка Reasoning Lab

1. Выберите «Лаборатория рассуждений» в нижней навигации.
2. Нажмите «Запустить все стратегии».
3. Проверьте четыре русские карточки, их correctness и метрики.
4. У «Мета-промпт» проверьте два API-вызова и раскрытие/скрытие generated prompt.
5. Полный emulator checklist находится в
   [README Day 03](../day-03-reasoning-strategies/README.md#ручная-end-to-end-проверка).

## Day 04 Temperature Lab

Третья вкладка — [Лаборатория температуры](../day-04-temperature-lab/README.md):
русскоязычный экран сравнения temperature 0 / 0.7 / 1.2, редактируемый prompt,
read-only параметры, session-only история максимум трёх прогонов текущего prompt
и benchmark-счётчики уникальных названий. Полный сценарий проверки — в README Day 04.
