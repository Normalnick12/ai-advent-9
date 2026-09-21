# Day 16 live acceptance — 2026-09-21

## Проверенный запуск

Из `day-16-mcp-discovery/`, PowerShell 7:

```powershell
.\.venv\Scripts\python.exe -u main.py
$LASTEXITCODE
```

Python 3.14.7, MCP SDK 2.2.0. Установлены отдельные зависимости Day 16;
backend и Android не используются. Проверенный запуск после исправления
UTF-8 вывода выполнен 21 сентября 2026 в 15:42 по локальному времени.

| Acceptance | Наблюдение |
| --- | --- |
| Remote connection | Endpoint `https://mcp.deepwiki.com/mcp`, default Client, без auth |
| Protocol negotiation | Успешно; `protocol_version = 2025-11-25` |
| Реальный tools/list | CLI вызвал SDK list_tools на новом Client; fixtures и сохранённый каталог не используются |
| Непустой каталог | Получены 3 definitions |
| Читаемый вывод | Для каждого показаны name, description и полная JSON input schema; русский вывод читается корректно |
| Clean exit | Финальное сообщение после закрытия Client; exit code 0 |

Сервер сообщил имя `DeepWiki`, version `2.14.3`. Каталог этого запуска:
`ask_question`, `read_wiki_contents`, `read_wiki_structure`.
Эти значения являются наблюдением, а не постоянными acceptance requirements.

Raw stdout/stderr и exit code сохранены локально в
`.local/day-16-mcp-discovery/live-20260921-154248.txt` от корня репозитория.
Этот игнорируемый файл не входит в Git. Ранее выполненный запуск
`live-20260921-154159.txt` также получил каталог и code 0, но русские сообщения
при перенаправлении были нечитаемыми. После явного UTF-8 для stdout/stderr
проверка повторена; именно повторный запуск удовлетворяет полному acceptance.

## Offline verification

- `python -m pytest -q`: 7 passed на актуальном коде.
- `python -m py_compile main.py tests/test_discovery.py`: успешно.
- `python -m pip check`: несовместимых зависимостей не найдено.

Тесты проверяют сохранение schema/Unicode, optional metadata, пустой ответ,
сбор страниц, failure продолжения, negotiation failure, timeout/cleanup и
отсутствие финального success при ошибке. Они не заменяют live evidence.

## Границы результата и видео

Инструменты не вызывались, definitions модели не передавались. Результат
подтверждает connection, negotiation и discovery в этом запуске; invocation,
качество инструментов и orchestration не проверялись.

Для демонстрации готовы команда запуска в Day README, вывод каталога и
проверка `$LASTEXITCODE`. Видео не записывалось и пользователем пока не
подтверждено; task 5.3 остаётся открытой.
