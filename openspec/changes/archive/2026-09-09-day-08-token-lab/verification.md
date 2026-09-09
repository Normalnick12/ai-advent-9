# Day 08 apply verification — 2026-09-09

## Выполненные проверки

| Проверка | Фактический результат |
|---|---|
| Полный backend pytest | 183 passed; одно существующее предупреждение Starlette/httpx |
| Синтаксис изменённых Python и Android XML | Passed |
| Android JVM через `scripts/dev.ps1 unit` | 55 tests, 0 failures/errors/skips |
| Полный Android UI прогон через `scripts/dev.ps1 ui` | 26 tests passed |
| Дополнительный TokenLab UI test с font scale 1.5 и IME | 1 test passed; исходный font scale 1.0 восстановлен |
| Debug APK через `scripts/dev.ps1 build` | BUILD SUCCESSFUL |
| OpenSpec strict validation change | Passed |
| OpenSpec strict validation current specs | 10/10 passed |
| Git whitespace / проверка изменённых файлов на секреты и локальные данные | Passed |

UI проверки используют fake repository и не обращаются к OpenAI. Backend tests проверяют реальные адаптеры с mock transport, nullable usage, pricing, immutable snapshots, partial count failures, one-use preparations, отмену/concurrency, отсутствие commit path у probe и восстановление SQLite. Сохранены прежние Day 02–07 regression tests. Day 05 pricing/results и current specs не изменены; SQLite schema не расширена.

## Provider counting integration

Подробная хронология, включая исходный baseline HTTP 400 и transient timeout, сохранена в [provider-count-smoke.md](provider-count-smoke.md).

Интеграционный запуск через реализованный OpenAI adapter и overflow preparation использовал production timeout 15 s, connect 5 s, max_retries=0:

- current-only: 19 tokens, 2.487 s;
- history-only: 35 tokens, 0.637 s;
- full instructions + history + current: 139 tokens, 0.391 s;
- oversized preparation: 139902 tokens после двух count calls, 13975 строк, 546130 bytes; preparation elapsed 1.359 s.

Итого в этом integration run: 5 count calls, 0 generation calls. Использована synthetic history во временной SQLite; сохранённая пара не изменилась. Это измерения count-контрактов, а не результаты живого short/long диалога. Timeout 60 s прежней диагностики не перенесён в production.

## Ручной live acceptance — подтверждён пользователем

Результаты ниже зафиксированы по явному подтверждению пользователя после ручного запуска. Это отдельный живой прогон, последовавший за описанными выше count-only integration и offline проверками; новые provider calls при обновлении отчёта не выполнялись.

### Short / long — task 7.3 завершена

Четыре обычных хода завершились успешно: короткий, короткий, длинный текст, снова короткий запрос. Actual API input по наблюдаемым попыткам: **110 → 150 → 3174 → 3196 tokens**. После длинного обмена следующий короткий user message всё равно имел большой full input из-за сохранённой history. UI отображал оценочную стоимость по actual usage; ответы и conversation count были корректны. Конкретные суммы стоимости этих четырёх ходов не переданы и здесь не восстанавливаются расчётным предположением.

### Настоящий overflow — task 7.4 завершена

- Fixed model: `gpt-4o-mini`; model context window: **128000 tokens**.
- Exact provider preflight: **137924 tokens**, показанное заполнение **107.8%**.
- Отдельный явно подтверждённый generation request был действительно отклонён provider как context-limit overflow. Это подтверждённый live rejection, не mock и не application soft limit.
- Actual usage rejected request отсутствовал; UI корректно показал «нет данных».
- History не изменилась, committed count остался **4**. Trimming, compression, replay и commit oversized payload не произошли.

### Recovery после полного restart backend

Day 08 session восстановилась из SQLite; rejected oversized payload отсутствовал в history. Следующий обычный короткий запрос успешно завершился:

| Метрика | Наблюдаемое значение |
|---|---:|
| Сохранённая история, standalone provider count | 3117 |
| Новое сообщение, standalone provider count | 17 |
| Full preflight input | 3219 |
| Actual API input | 3219 |
| Actual output | 6 |
| Оценочная стоимость хода, USD | 0.00048645 |
| Committed count | 4 → 5 |

Agent правильно вспомнил кодовый цвет «янтарный». Standalone history/current counts не являются аддитивными частями full preflight. Runtime attempt table после restart не восстанавливается, тогда как conversation history/session сохраняется, согласно design.

## Итоговый статус apply

Все **34/34 tasks** завершены, включая 7.3–7.4 на основании ручного подтверждения пользователя. Реализация и архитектура при фиксации acceptance не менялись. Ранее успешные backend/JVM/UI/build проверки переиспользованы: изменены только tasks и документация. Финальная strict validation change/current specs, проверка diff и status выполнены повторно.

Исторический baseline HTTP 400, transient timeout и успешные count smoke сохранены в исходном отчёте. Дополнительные live/provider calls, commit, push и archive при закрытии acceptance не выполнялись. Change готов к отдельному workflow `finish-day Day 08`.

## Finish Day 08 — 2026-09-09

Код после успешных проверок и ручного acceptance не менялся. Для finish-day результаты текущей рабочей сессии переиспользованы без дополнительных provider calls:

| Проверка / команда | Режим | Результат |
|---|---|---|
| Backend `.venv/Scripts/python.exe -m pytest -q` | reused | 183 passed |
| `scripts/dev.ps1 unit` | reused | 55 JVM tests passed |
| `scripts/dev.ps1 ui` и отдельный TokenLab test с большим шрифтом/IME | reused | 26 + 1 UI tests passed |
| `scripts/dev.ps1 build` | reused | Debug APK собран |
| Count-only integration и ручной short/long/overflow/recovery | reused | Подтверждены выше |
| Strict validation change перед archive | run | Passed; 34/34 tasks, все artifacts done |
| Сверка пяти delta specs с main после sync | run | Все изменения перенесены, прежние scenarios сохранены |
| `openspec validate --specs --strict --no-interactive` после sync | run | 12/12 passed |

OpenSpec архивирован штатным CLI в `openspec/changes/archive/2026-09-09-day-08-token-lab/`. Sync выполнен и проверен до archive; поэтому archive запускался с `--skip-specs`, без повторного применения delta. Ссылка backend README на smoke report обновлена. Исторические результаты apply и smoke сохранены.
