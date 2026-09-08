# Проверка Day 07

Дата: 2026-09-08. Реализация и offline-проверки выполнены; успешная live task 6.4 подтверждена пользователем.

## Offline

| Проверка | Фактический результат |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -q` из `backend` | 154 passed, 1 предупреждение Starlette/httpx |
| `pwsh -File scripts/dev.ps1 unit` | 49 JVM tests, 0 failures |
| `pwsh -File scripts/dev.ps1 ui` | 23 instrumented/UI tests, 0 failures, 0 errors; API 34 emulator |
| `pwsh -File scripts/dev.ps1 build` | BUILD SUCCESSFUL, debug APK; актуальные задачи переиспользованы |
| `openspec validate day-07-context-persistence --strict` | valid |
| `openspec validate --specs --strict` | 10 passed, 0 failed |
| `git diff --check` | ошибок whitespace нет |
| README relative links | неработающих ссылок нет |
| Git/local files | DB и journal/wal/shm игнорируются; локальные/секретные файлы не включены |

Backend restart oracle использует реальный временный SQLite-файл: первые
Store/Manager/Session references исчезают, новый manager лениво восстанавливает
history и передаёт fake LLM точный tuple U1/A1/U2. Проверены isolation, исходный
Unicode/text, неподходящие outcomes/cancellation, rollback между INSERT, ошибка
COMMIT без продвижения RAM, persistent delete и чистый runtime busy.

API-проверки подтверждают metadata-only GET без LLM/ключа, strict DTO, безопасные
404/409/422/500 и отсутствие ложного HTTP success при storage error.
Все pytest lifespan fixtures используют отдельную БД; `.local` DB не открывается.
SimpleAgent, LlmClient, Responses adapter и зависимости остались без изменений.

Android проверяет read/create/save/send/delete/clear ordering, явные retries,
read/save/clear failures, metadata baseline, отсутствие replay и bubbles из
прошлого процесса, разные ID и независимые busy/draft/reset Day 06/07.
Instrumented SharedPreferences test использует отдельный preferences file,
проверяет MODE_PRIVATE, выполнение вне main thread, запись/чтение/очистку между
экземплярами и ошибки commit. Пользовательский ключ этот тест не очищает.

Полный UI-набор покрывает шесть карточек, восстановление/error/reset, IME,
длинный текст, navigation и Activity recreation. Тест прокрутки сравнивает
фактический anchor в середине длинного сообщения. У нижней границы списка
Activity recreation может скорректировать offset при перерасчёте viewport;
такую граничную позицию не используем как oracle сохранения scroll state.
Activity recreation не считается доказательством Android process restart.

## Подготовленное окружение (6.3)

Backend запущен через `scripts/dev.ps1 backend` в управляемом терминале;
логи доступны, сервер слушает порт 8000. `scripts/dev.ps1 status` прошёл.
Эмулятор `emulator-5554` (Pixel 3a, API 34) работает. GET `/health` от эмулятора
через `10.0.2.2:8000` вернул HTTP 200 и status ok.
Это подтверждает доступ к FastAPI, но не доступность OpenAI.

## Live 6.4 — подтверждена пользователем

2026-09-08 пользователь явно подтвердил успешную live-проверку после запроса
подтверждения сценария restart обоих процессов и ответа/count 2. Task 6.4
закрыта на основании этого подтверждения. Агент не выполнял дополнительных
автоматических платных LLM-прогонов.

Подтверждённый сценарий:

1. Открыть Day 07; при необходимости явно начать новый диалог.
2. Сообщить выдуманный факт, дождаться completed/count 1.
3. Полностью остановить backend и force-stop Android без очистки app data.
4. Запустить backend, затем Android; открыть Day 07.
5. Проверить restored/count 1 без предыдущих bubbles.
6. Явно спросить факт и подтвердить фактический ответ/count 2.

Команды restart — в [scripts README](../../../../scripts/README.md).
Не replay'ить сообщения и не повторять платные запросы автоматически.
Crash во время неопределённой HTTP-операции не входит в acceptance Day 07.

## Завершение Day

Результаты backend pytest (154), JVM (49), полного UI suite (23) и debug build
переиспользованы из apply этой сессии: после успешных прогонов существенный
код и конфигурация не менялись. Повторно выполняются strict validation change
и основных specs, проверка diff/index и проверка секретов/локальных файлов.
Архивирование и обычные commit/push разрешены вызовом finish-day; Git фиксирует
итоговый commit. Подтверждение live не подменяется новым автоматическим прогоном.
