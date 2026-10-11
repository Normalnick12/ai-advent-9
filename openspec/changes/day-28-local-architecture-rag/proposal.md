## Why

Разработчику нужен переносимый локальный инструмент для изучения архитектуры незнакомого Android-проекта: одного Kotlin-файла недостаточно, чтобы установить соглашения команды. Day 28 расширяет фактически реализованный CLI Day 27 постоянной Markdown Knowledge и локальным RAG; учебный A/B служит проверкой полезности инструмента с целевой средой Mac M1 16 GB, а не пределом его развития.

## What Changes

- Подключать каталог Markdown через понятные preview/index/status операции: показать выбранные файлы и изменения, явно принять расширение набора, хранить selection автоматически; ручное редактирование manifest не требуется. Обнаруживать добавленные, изменённые и удалённые документы и блокировать использование устаревшего индекса.
- Разделить постоянную Knowledge, её SQLite index и временную Workspace. Индексировать только разрешённый Markdown; выбранный Kotlin, вопросы и ответы не сохранять.
- Адаптировать чистые Markdown/provenance/cosine/citation функции Week 5 внутри существующей утилиты без runtime-импортов backend. Пересчитать embeddings локально через Ollama; OpenAI vectors и старый threshold не использовать.
- Добавить независимые vector и text retrieval по одному snapshot, с SQLite FTS5 для точных терминов, ограниченным context и проверяемыми источниками.
- Добавить explain с раздельными code observations, documented rules, applications, assumptions и limitations. Общий контракт действует для A без retrieval и B с retrieval; прежний запуск Day 27 сохраняет свой контракт.
- Сохранить loopback-only transport и отсутствие content logging. Проверять структурное отделение недоверенных Markdown/Kotlin от инструкций, не обещая доказанной невосприимчивости модели к prompt injection.
- Проверить synthetic A/B, качество обоих поисков и Markdown-подмножество Week 5, отдельно фиксируя mechanical, semantic и platform outcomes.

За рамками: несколько Kotlin-файлов, IDE integration, Android UI, новый агент/MCP/server, облачные модели, автоматический rewrite/reranker/hybrid, отдельная vector DB и рефакторинг завершённых Weeks 1–5.

## Capabilities

### New Capabilities

- `local-architecture-rag`: подключение и актуальность Knowledge, совместимый локальный индекс, два поиска, grounded explanation, privacy/portability и воспроизводимая оценка расширенного режима существующего CLI.

### Modified Capabilities

Нет изменений опубликованных main specs. Базовая capability `local-architecture-assistant` пока существует только в активном change Day 27; её legacy invocation и требования сохраняются. Новая capability описывает дополнительные команды и явно отделённый расширенный режим. Реализация зависит от текущего кода Day 27, но не требует его commit или архивирования.

## Impact

Реализация затронет `day-27-local-architecture-assistant/`: CLI routing, Ollama embedding transport, новые небольшие модули Knowledge/chunking/index/retrieval, extended explanation и tests. Runtime остаётся Python 3.12+, httpx и stdlib sqlite3 с доступным FTS5; внешние SQLite extensions, PyTorch и backend не требуются. Данные пользователя и index находятся вне Git.

`day-28-local-architecture-rag/` будет содержать только обзор дня и синтетические материалы/оценочный сценарий, без второй реализации приложения; корневой README получит ссылку. Week 5 используется через адаптацию функций и read-only экспорт девяти Markdown snapshots из существующего Day 21 index в отдельную локальную тестовую Knowledge. Его код, индекс и результаты не перезаписываются.

На этапе proposal изменяются только артефакты этого change. Day 27 (11/11, offline 101 passed / 1 skipped, live technical PASS / semantic PARTIAL) остаётся активным и неизменным; реализация, archive, commit и push требуют отдельного этапа.
