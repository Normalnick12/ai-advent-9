# Android-приложение

Клиент на Kotlin, Jetpack Compose и Material 3 для работы с локальным FastAPI
backend. Позволяет отправлять запросы, сравнивать ответы и просматривать метрики.
Все обращения к OpenAI выполняет backend; API-ключ в приложении не нужен.

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
