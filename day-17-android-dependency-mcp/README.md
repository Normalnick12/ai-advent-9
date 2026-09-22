# Day 17 — Первый MCP-инструмент

## Суть эксперимента

Собственный read-only MCP server получает опубликованные версии точной зависимости
из Google Maven. Android отправляет запрос через backend в Responses API;
native remote MCP возвращает модели результат, а приложение показывает ответ и evidence.

## Что проверяет

- Регистрацию tool, schema входных параметров, валидацию и structured result.
- Реальный MCP call, его arguments/output и upstream log по lookup id.
- Forced-вызов отдельно от самостоятельного выбора модели в auto.

## Результаты

Offline-проверки пройдены: 57 server tests, 51 backend tests (Day 17 и общий Responses adapter),
7 Android JVM tests и 10 UI/navigation tests на эмуляторе API 34. APK собран.
Это проверка реализации с fixtures, а не доказательство remote-вызова.
22 сентября 2026 выполнена одна forced-попытка из Android через Render MCP.
Discovery, вызов `androidx.core:core-ktx`, structured result и серверный лог подтверждены.
Tool вернул 129 версий; модель правильно указала последние три элемента, но ошиблась
в количестве — ответила 133. Поэтому вызов MCP успешен, а проверка точности final response
не пройдена. Повторов и исправления ответа не было; auto не проводился. Видео записано, что подтверждено пользователем.
[Полный evidence и verdict](../openspec/changes/archive/2026-09-22-day-17-first-mcp-tool/live-result.md)
сохранены с deployed SHA.

Standalone server: Python 3.11+, `pip install -r requirements.txt`,
запуск из этой папки: `python -m uvicorn server:app --host 127.0.0.1 --port 8001`.
Offline tests: `pip install -r requirements-dev.txt`, затем `python -m pytest -q`.

Render Web Service использует эту папку как Root Directory, build command
`pip install -r requirements.txt`, start command
`python -m uvicorn server:app --host 0.0.0.0 --port $PORT`.
Укажите Python runtime `PYTHON_VERSION=3.14.7` (версия локальной проверки),
Health Check Path `/health`; на время эксперимента отключите Auto-Deploy,
чтобы последующие docs commits не сменили участвующую в live revision.
Разрешённый hostname берётся из `RENDER_EXTERNAL_HOSTNAME` либо `MCP_PUBLIC_HOST`.
Рабочий endpoint — `https://<service-host>/mcp`. Секретов server не требует.
Deploy выполняется из проверенного pre-live Git commit; его фактический Render SHA
сохраняется в evidence эксперимента. Этот commit не завершает день.

Настройка клиента описана в [backend](../backend/README.md)
и [Android](../android-app/README.md). `OPENAI_API_KEY` задаётся только на backend.
