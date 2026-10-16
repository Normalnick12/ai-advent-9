# Структура AI Advent Challenge 9

## Основные компоненты

Репозиторий содержит учебные эксперименты в каталогах `day-NN-short-name`.
Их README описывают идею и фактические результаты; общий каталог дней находится
в корневом `README.md`. Наличие отдельного каталога дня не означает, что весь его
runtime расположен там: многие эксперименты используют общий backend и Android.

`backend/` — Python backend на FastAPI. Исходники находятся в `backend/app/`,
проверки — в `backend/tests/`, самостоятельные экспериментальные CLI — в
`backend/scripts/`. Сервер собирается в `backend/app/main.py`; отдельные API-модули
подключаются к нему как маршруты. OpenAI вызывается на стороне Python.
`backend/app/openai_responses_llm_client.py` реализует общий клиент Responses API,
`backend/app/llm_client.py` — конфигурацию, сообщения и нормализованный результат.

`android-app/` — Android-клиент на Kotlin, Jetpack Compose и Material 3.
Точка входа — `android-app/app/src/main/java/com/example/responsecontrollab/MainActivity.kt`;
главный экран расположен в пакете `ui/main` внутри того же дерева исходников.
Приложение отправляет запросы локальному backend и показывает результаты.
OpenAI API-ключ Android-приложению не требуется: направление взаимодействия —
Android → backend → OpenAI. У Python CLI отдельных дней может быть собственная
точка входа без запуска Android.

`scripts/dev.ps1` управляет окружением Windows: проверкой состояния, запуском
backend и эмулятора, Android-тестами и сборкой. Подробные команды и настройка
находятся в `scripts/README.md`, инструкции компонентов — в `backend/README.md`
и `android-app/README.md`.

`openspec/specs/` содержит основные спецификации поведения.
`openspec/changes/` хранит изменения с proposal, design, delta specs и tasks;
архив находится в `openspec/changes/archive/`. Активный план сам по себе
не доказывает, что соответствующее поведение уже реализовано или проверено.

## MCP: Week 4, Days 16–20

Day 16 (`day-16-mcp-discovery/main.py`) — самостоятельный Python CLI для
обнаружения инструментов DeepWiki через MCP; discovery не вызывает сами tools.

Day 17 (`day-17-android-dependency-mcp/server.py`) — MCP-сервер с инструментом
получения опубликованных версий из Google Maven. Интеграция эксперимента с OpenAI
и Android находится в общем backend/Android; Python-сервис эксперимента —
`backend/app/mcp_lab_service.py`.

Day 18 (`day-18-dependency-watch/`) добавляет фоновые проверки зависимостей,
хранение и планировщик. В Day 19 (`day-19-mcp-composition/`) реализована композиция
инструментов; backend-часть — `backend/app/mcp_composition_service.py`.
Day 20 (`day-20-mcp-orchestration/`) исследует оркестрацию нескольких MCP-серверов;
соответствующая backend-часть — `backend/app/mcp_orchestration_service.py`.
Эти дни имеют собственные сценарии, конфигурацию и результаты.

## RAG: Week 5, Days 21–25

Day 21 индексирует явно выбранный корпус. Загрузка источников, чанкинг,
embeddings и хранение реализованы в `backend/app/document_indexing/`.
CLI — `backend/scripts/day21_index.py`, исторический manifest —
`day-21-document-indexing/corpus.json`. Эксперимент сравнивает fixed-size
и structure-aware чанкинг, сохраняет тексты и происхождение фрагментов в SQLite.

Day 22 добавляет cosine-поиск и первый RAG-запрос:
`backend/app/first_rag/`, CLI `backend/scripts/day22_rag.py`.
Day 23 исследует query rewrite и relevance filtering:
`backend/app/rewrite_filter_rag/`, CLI `backend/scripts/day23_rag.py`.
Day 24 проверяет структуру ответа, источники и дословные цитаты:
`backend/app/grounded_rag/`, CLI `backend/scripts/day24_rag.py`.
Day 25 добавляет stateful mini-chat, историю и Task Memory:
`backend/app/stateful_rag/`, CLI сценариев `backend/scripts/day25_chat.py`.

Сценарии этих дней используют исторические corpus/run IDs и собственные условия
экспериментов. Их данные нельзя считать автоматически актуальным описанием
сегодняшнего checkout. Совпадение цитаты с документом проверяет происхождение
текста, но не доказывает правильность вывода модели.

## Локальный помощник: Week 6, Days 26–30

Day 26 — знакомство с локальной LLM через Ollama, без отдельной программы.
Общая утилита последующих дней находится в `day-27-local-architecture-assistant/`:
`assistant.py` — CLI, `workspace.py` — чтение разрешённого Kotlin-файла,
`ollama_client.py` — локальный транспорт.

Расширение Day 28 в том же каталоге добавляет Markdown Knowledge, SQLite,
текстовый FTS5 и векторный поиск (`knowledge.py`, `knowledge_index.py`,
`markdown_chunks.py`, `retrieval.py`, `local_embeddings.py`). В каталоге
`day-28-local-architecture-rag/` находятся материалы эксперимента и exporter.
Day 29 (`day-29-local-assistant-optimization/`) хранит отдельные эксперименты
настроек, инструкций и форматов ответа.

Day 30 (`day-30-private-assistant-service/`) содержит необязательный HTTP-адаптер
и клиент. Его общая операция объяснения использует
`day-27-local-architecture-assistant/assistant_runtime.py`.
Руководства: `day-27-local-architecture-assistant/docs/usage.md`
и `day-30-private-assistant-service/docs/http-service.md`.
Это самостоятельная цепочка Kotlin/Knowledge/Ollama; она не заменяет общий
OpenAI backend и RAG Week 5. Подтверждённые результаты и ограничения недели
описаны в `day-30-private-assistant-service/week-6-technical.md`.

## Ассистент разработчика: Week 7, Day 31

`backend/scripts/day31_help.py` — самостоятельная команда `/help` в backend
окружении. Её реализация находится в `backend/app/developer_assistant/`:
`corpus.py` читает явный manifest, `index.py` строит отдельный SQLite snapshot,
`service.py` соединяет RAG и генерацию, `mcp_client.py` вызывает локальный MCP.
`backend/scripts/day31_git_mcp.py` запускает `git_mcp_server.py` из этого пакета
в отдельном процессе через stdio. Только этот сервер выполняет Git-команды.

Корпус задаётся `day-31-developer-assistant/corpus.json`: корневой README,
этот документ и README backend, Android и scripts. Индекс располагается в
`backend/.local/day31/index.sqlite3`; перед вопросом проверяется актуальность.
Обработка вопроса: MCP discovery и `get_current_branch`, embedding вопроса,
поиск chunks, OpenAI Responses, проверка источников и рендеринг ответа.
Ветка отображается отдельно от документальных источников. Общие функции
чанкинга, embeddings, cosine-поиска и проверки цитат импортируются из Week 5.
История диалога не сохраняется; компоненты Ollama Week 6 не подключаются.

## Локальные данные и проверки

Backend использует ignored `backend/.local/` для пользовательских SQLite-баз,
индексов и результатов экспериментов. `.env`, `.venv`, Python-кэш и локальные
данные исключены из Git. `OPENAI_API_KEY` задаётся в окружении backend или его
локальном `.env`, а не в исходниках.

Backend-тесты находятся в `backend/tests/` и используют подставные ответы
провайдера и временные SQLite. Android JVM-тесты — в `android-app/app/src/test/`,
инструментальные UI-тесты — в `android-app/app/src/androidTest/`.
Команды запуска и выбор отдельных проверок описаны в README компонентов.
