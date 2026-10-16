# Day 31 — команды короткой демонстрации

По подтверждению пользователя видео записано отдельно от репозитория;
файл видео не проверялся. Ниже сохранён сценарий воспроизведения.
Выполнять в PowerShell 7 из корня проекта.
Зависимости уже установлены; ключ остаётся в backend environment/локальном `.env`.
Не показывать `.env` или терминальную историю с секретами.

## Подготовка

```powershell
Set-Location C:\Projects\ai-advent-9
$day31Python = '.\backend\.venv\Scripts\python.exe'
$day31Help = '.\backend\scripts\day31_help.py'
Get-Content -LiteralPath .\day-31-developer-assistant\corpus.json
& $day31Python $day31Help index
```

При неизменившихся документах ожидается `status=unchanged`, `embedding_calls=0`.
Если документы изменились, `index` явно строит новый snapshot; это отдельная
подготовка, а не скрытый эффект вопроса.

## Основной фрагмент, около 2–3 минут

```powershell
& $day31Python $day31Help /help "Где находятся индексация и поиск RAG Days 21–25, и как запускаются их CLI?" --trace --trace-format text
& $day31Python $day31Help /help "Какой SLA доступности в процентах гарантирован этому проекту и кто указан владельцем production on-call?" --trace --trace-format text
```

Первый ответ: показать пути модулей/CLI и источники с диапазонами строк и
буквальными цитатами. В компактном trace показать MCP discovery/tool/call,
диагностическое `server_event`, первые три RAG hit, LLM usage и validation.
Git-блок выводится отдельно от текста LLM. Полные `call_id`, PID, chunk IDs и
fingerprint доступны в исходном JSONL (`--trace` без `--trace-format text`).
Второй ответ: показать честный `insufficient_context` и отдельно полученную ветку.
`server_event=unavailable` допускается при валидном MCP result; отсутствие
реального MCP-вызова или ошибка tool не допускаются.

Каждая из этих команд — новый live-запрос (одно query embedding и одна генерация).
Для показа уже выполненной приёмки можно открыть сохранённые `.out.txt` и
`.trace.jsonl` из `backend/.local/day31/acceptance/`; такой показ явно назвать
replay. Повторный API-вызов для простого просмотра отчёта не нужен.

Конкретный replay финальной приёмки (не вызывает API):

```powershell
Get-Content -LiteralPath .\backend\.local\day31\acceptance\index-v8.json
Get-Content -LiteralPath .\backend\.local\day31\acceptance\Q2-v8.out.txt
Get-Content -LiteralPath .\backend\.local\day31\acceptance\Q2-v8.trace.jsonl |
    ConvertFrom-Json | Where-Object event -In 'mcp','generation','validation' |
    ConvertTo-Json -Depth 6
Get-Content -LiteralPath .\backend\.local\day31\acceptance\Q4-v8.out.txt
```

Показать итог scoped pytest из `validation.md`: **160 passed**. Если нужен новый
локальный прогон для записи, выполнить ровно приведённую там команду; она offline
и не обращается к OpenAI. Старый вывод обозначать как сохранённый результат.

## Остальные вопросы приёмки

```powershell
& $day31Python $day31Help /help "Как связаны backend, Android-приложение и scripts в этом репозитории?" --trace --trace-format text
& $day31Python $day31Help /help "Как запустить JVM-тесты Android и один выбранный UI-тест по правилам проекта?" --trace --trace-format text
```

Эти вопросы можно проверить вне короткого видео. Итоги тестов, реальные ошибки
и ручные оценки находятся в [validation.md](validation.md). Не объявлять день
завершённым по одному валидному JSON или только по unit-тестам.
