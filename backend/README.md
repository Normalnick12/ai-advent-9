# Backend

Локальный FastAPI-сервис для Android-приложения. Принимает запросы, обращается
к OpenAI Responses API и возвращает ответы с метриками. Поддерживает управление
форматом и длиной ответа, сравнение prompting-стратегий, значений temperature и моделей.
API-ключ используется только на сервере.

[Day 05](../day-05-model-benchmark/README.md): каталог доступен через
GET /api/v1/model-benchmark/catalog; POST /api/v1/model-benchmark/run принимает
три выбранных model id и возвращает независимую проверку пяти задач и метрики.
Каталог не требует ключа. Запуск делает по одному вызову на слот без retries.

## Требования

Python 3.11+, зависимости из [requirements.txt](requirements.txt)
и переменная окружения `OPENAI_API_KEY`. Для общего скрипта запуска нужен PowerShell 7.

## Подготовка

Из корня репозитория в PowerShell 7, один раз:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

Создайте локальный игнорируемый `backend/.env` с `OPENAI_API_KEY`
или задайте эту переменную в терминале. Не сохраняйте ключ в исходниках или Git.

## Запуск

Из корня репозитория:

```powershell
.\scripts\dev.ps1 backend
```

Скрипт использует `backend/.venv`, автоматически загружает `backend/.env`,
если он существует, и не запускает второй сервер на занятом порту `8000`.
Сервер работает в текущем терминале, здесь же доступны логи; остановка — Ctrl+C.
После изменения backend перезапустите его: автоматическая перезагрузка не включена.

В другом терминале выполните `.\scripts\dev.ps1 status` для проверки готовности.
После запуска доступны [Swagger UI](http://127.0.0.1:8000/docs)
и [проверка состояния](http://127.0.0.1:8000/health).
`/health` проверяет FastAPI, но не доступность OpenAI.
Подключение клиента описано в [Android README](../android-app/README.md),
работа с процессами и диагностика — в [окружении Windows](../scripts/README.md).

## Тесты

Из папки `backend` с активированным окружением:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
