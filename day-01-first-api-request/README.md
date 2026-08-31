# День 1 — первый API-запрос

Интерактивное CLI-приложение на Python отправляет введённые сообщения модели `gpt-5.6` через OpenAI Responses API и выводит ответы в консоль.

## Требования

- Python 3.9 или новее
- API-ключ OpenAI в переменной окружения `OPENAI_API_KEY`

## Запуск

Из корня репозитория создайте виртуальное окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\day-01-first-api-request\requirements.txt
```

Задайте ключ только в текущей сессии PowerShell:

```powershell
$env:OPENAI_API_KEY = "ваш_API_ключ"
```

Запустите приложение:

```powershell
python .\day-01-first-api-request\main.py
```

Введите сообщение после приглашения `Вы:`. После ответа можно отправить следующее сообщение. Команды `exit` и `quit` завершают программу, а пустой ввод игнорируется.

Клиент `OpenAI()` автоматически читает ключ из `OPENAI_API_KEY`. Не сохраняйте реальный ключ в файлах проекта и не добавляйте его в Git.
