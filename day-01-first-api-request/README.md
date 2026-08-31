# День 1 — первый API-запрос

Минимальное CLI-приложение на Python отправляет запрос модели `gpt-5.6` через OpenAI Responses API и выводит ответ в консоль.

## Требования

- Python 3.9 или новее
- API-ключ OpenAI в переменной окружения `OPENAI_API_KEY`

## Запуск

Перейдите в папку задания и создайте виртуальное окружение:

```powershell
cd day-01-first-api-request
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Задайте ключ только в текущей сессии PowerShell:

```powershell
$env:OPENAI_API_KEY = "ваш_API_ключ"
```

Запустите приложение:

```powershell
python main.py
```

Клиент `OpenAI()` автоматически читает ключ из `OPENAI_API_KEY`. Не сохраняйте реальный ключ в файлах проекта и не добавляйте его в Git.

