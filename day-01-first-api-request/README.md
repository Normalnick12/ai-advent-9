# Day 01 — Первый API-запрос

## Цель

Сделать первый запрос к OpenAI API из Python и получить ответ модели в консоли.

## Что реализовано

Интерактивный Python CLI отправляет каждое введённое сообщение через OpenAI
Responses API и печатает ответ. Сообщения отправляются независимо, без истории
диалога. Для выхода — `exit` или `quit`.

## Запуск

Нужны Python 3.9+, пакет `openai` и переменная окружения `OPENAI_API_KEY`.
Из корня репозитория в PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\day-01-first-api-request\requirements.txt
$env:OPENAI_API_KEY = "<ваш API-ключ>"
python .\day-01-first-api-request\main.py
```

Введите сообщение после `Вы:` и проверьте, что ответ появился в консоли.
Ключ задаётся только в текущей сессии; не сохраняйте его в Git.

## Код

- [CLI](main.py)
- [Зависимости](requirements.txt)
