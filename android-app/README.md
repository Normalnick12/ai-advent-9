# Android-приложение

Клиент на Kotlin, Jetpack Compose и Material 3 для работы с локальным FastAPI
backend. Позволяет отправлять запросы, сравнивать ответы и просматривать метрики.
Все обращения к OpenAI выполняет backend; API-ключ в приложении не нужен.

## Требования

Android Studio, JDK 17 или совместимый более новый JDK, Android SDK
и Android Emulator. Зависимости загружаются при Gradle Sync.

## Запуск

1. Запустите [backend](../backend/README.md) на порту `8000`.
2. Откройте папку `android-app` в Android Studio и дождитесь Gradle Sync.
3. Выберите Android Emulator и запустите конфигурацию `app`.

Эмулятор подключается к серверу на компьютере по `http://10.0.2.2:8000/`.
Локальное HTTP-соединение разрешено в debug-сборке.
Переменные окружения для приложения не требуются.

## Сборка и тесты

Из корня репозитория в PowerShell:

```powershell
cd android-app
.\gradlew.bat testDebugUnitTest assembleDebug
```

Для инструментальных тестов на запущенном эмуляторе, из той же папки:

```powershell
.\gradlew.bat connectedDebugAndroidTest
```
