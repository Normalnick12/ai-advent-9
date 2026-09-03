# Backend

Локальный FastAPI-сервис для Android-приложения. Принимает запросы, обращается
к OpenAI Responses API и возвращает ответы с метриками. Поддерживает управление
форматом и длиной ответа, сравнение prompting-стратегий и значений temperature.
API-ключ используется только на сервере.

## Требования

Python 3.11+, зависимости из [requirements.txt](requirements.txt)
и переменная окружения `OPENAI_API_KEY`.

## Запуск

Из корня репозитория в PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "<ваш API-ключ>"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Ключ задаётся в текущей сессии; не сохраняйте его в исходниках или Git.
Если ключ уже хранится в локальном игнорируемом `.env`, добавьте к команде
uvicorn `--env-file .env` вместо задания переменной в терминале.

После запуска доступны [Swagger UI](http://127.0.0.1:8000/docs)
с описанием API и [проверка состояния](http://127.0.0.1:8000/health).
Подключение клиента описано в [Android README](../android-app/README.md).

## Тесты

Из папки `backend` с активированным окружением:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
