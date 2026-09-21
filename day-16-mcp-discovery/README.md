# Day 16 — MCP Connection / Tool Discovery

## Суть эксперимента

Самостоятельный Python CLI подключается к публичному DeepWiki MCP через
Streamable HTTP и официальный SDK `mcp==2.2.0`. Программа выполняет
`connect → protocol negotiation → tools/list → catalog` и завершает работу.
SDK сам выбирает совместимый способ negotiation. Инструменты не вызываются,
модель в эксперименте не участвует.

## Что проверяет

- Реальное подключение и согласование протокола с DeepWiki без авторизации.
- Получение каталога и читаемый вывод names, descriptions и input schemas.
- Штатное закрытие соединения и exit code 0.

Endpoint: `https://mcp.deepwiki.com/mcp`. CLI также показывает negotiated
protocol version и сведения о сервере, если они предоставлены. Количество
и имена tools определяются ответом сервера и могут меняться. Пустой каталог
выводится честно, но не удовлетворяет live-проверке этого дня.

## Результаты

21 сентября 2026 года live-запуск подключился к DeepWiki, согласовал протокол
`2025-11-25` и получил 3 инструмента с описаниями и input schemas. Соединение
закрылось штатно, процесс завершился с кодом 0. Это наблюдение одного запуска:
состав каталога внешнего сервиса может измениться. Инструменты не вызывались.

Offline-проверки локальной логики прошли. Подробности live и границы проверки —
в [OpenSpec](../openspec/changes/archive/2026-09-21-day-16-mcp-discovery/live-result.md).

## Запуск

Нужны Python 3.11+ и доступ к интернету. PowerShell из корня репозитория:

```powershell
cd day-16-mcp-discovery
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
$LASTEXITCODE
```

Для deterministic offline-проверок из той же папки:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Backend, Android и API-ключи не нужны. Ожидание подключения/discovery
ограничено 60 секундами; при ошибке процесс завершается с ненулевым кодом.
