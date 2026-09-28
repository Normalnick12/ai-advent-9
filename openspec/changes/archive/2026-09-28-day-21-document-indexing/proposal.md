## Why

Day 21 открывает Week 5 — RAG и должен сделать наблюдаемой цепочку documents → chunks → embeddings → persistent index. Тематический срез текущего repository позволяет изучить представление инженерных знаний о persistence и state management на реальных Markdown, Python и Kotlin, не смешивая индексацию с качеством retrieval.

## What Changes

- Зафиксировать явный corpus из 22 существующих файлов: README, актуальные OpenSpec specs, backend и Android вокруг сохранения диалога и состояния задачи. Обе стратегии получают один snapshot.
- Реализовать token-based fixed-size baseline: максимум 500 tokens, целевой overlap 50, с сохранением Unicode. Character-based fallback не требуется.
- Сравнить его со `structure-aware deterministic chunking`: Markdown headings, Python AST, Kotlin file/formatting boundaries; тот же token limit и общий token-based fallback для oversized blocks. Модель не определяет границы.
- Отделить Embedder; использовать OpenAI `text-embedding-3-small`, 1536 dimensions, с одинаковой конфигурацией для обеих стратегий.
- Сохранять текст, обязательное ядро metadata и embeddings в локальный SQLite; build содержит corpus/config provenance и наблюдения конкретного run.
- Добавить CLI corpus → preview → build --strategy both → compare → inspect/reopen. Центральная offline-команда preview показывает исходный участок → chunks fixed-size → chunks structure-aware с metadata на заранее выбранных representative locations.
- Ограничить обязательное сравнение chunk count, min/median/max tokens, total embedded tokens и fallback count; сложные аналитические метрики не являются условием готовности.
- Проверить корректность pipeline небольшими offline tests; зафиксировать реальные результаты только после live indexing. Timing, provider usage, число calls и размер базы являются наблюдениями run, а не доказательствами качества или производительности стратегии.

## Capabilities

### New Capabilities

- `document-indexing-experiment`: воспроизводимая подготовка corpus, две token-constrained стратегии, embeddings, persistent local index, CLI и ограниченное сравнение представления документов.

### Modified Capabilities

Нет. Контракты существующих Days не меняются.

## Impact

- Новый изолированный модуль `backend/app/document_indexing/`, CLI `backend/scripts/day21_index.py`, scoped backend tests; существующий generation-oriented `LlmClient` не расширяется.
- `day-21-document-indexing/README.md` и manifest corpus; ссылка Day 21 в корневом README; команды и зависимости в README компонентов/scripts.
- Новая зависимость `tiktoken`; существующие OpenAI SDK и стандартный `sqlite3` переиспользуются. Достаточно стандартной инициализации encoding перед offline checks; собственное управление tokenizer cache не требуется.
- Артефакты индекса находятся в игнорируемом `backend/.local/day21/`; ключ остаётся в backend environment. Embedding API получает выбранные тексты; локальное хранение не означает полностью локальное вычисление embeddings.
- В scope не входят retrieval, cosine search, FAISS, reranking, LLM generation, agent orchestration, MCP, Android UI, Kotlin parser, новые сервисы или incremental indexing.
