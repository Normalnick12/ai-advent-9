## Why

Days 21–24 проверяли отдельные RAG-вопросы, а ранние дни — conversation и memory по отдельности. Day 25 соединяет их в mini-chat и делает наблюдаемым сохранение пользовательской цели после выпадения исходных сообщений из model history.

## What Changes

- Добавить один Day25ChatService: durable full history, recent window из трёх подтверждённых пар и отдельная extractive Task Memory (goal, constraints, terms, clarifications).
- Собирать deterministic contextual query из текущего сообщения, памяти до turn и предыдущего recent user; искать pinned Day 21/22 Top-5 без Day 23 rewrite/filter.
- Получать grounded answer и proposed memory patch одним structured generation call; независимо валидировать payloads и атомарно сохранять pair, grounded result, memory и revision.
- Сохранять корректные abstention turns с пустыми sources/citations и неизменной task memory. Technical failures не становятся успешными turns; отдельного extractor для abstention нет.
- Добавить CLI acceptance harness: два frozen сценария по шесть user turns, saved evidence, ручной review и компактный offline `report --video`.
- Добавить минимальный Android thin client с sources, collapsible Task Memory, session restore и loading/error на существующих chat components.

## Capabilities

### New Capabilities

- `stateful-rag-chat`: backend conversation/task memory/retrieval/grounding contracts и воспроизводимый CLI experiment.
- `stateful-rag-android`: небольшой Compose thin client для визуального использования того же backend.

### Modified Capabilities

Нет. Contracts предыдущих дней сохраняются; их primitives переиспользуются в отдельном namespace.

## Impact

Backend: изолированный Day 25 service/store/API, существующие conversation primitives, provider client, Day 22 search и Day 24 validation. Один локальный SQLite store для chat state; существующий индекс только читается. Android: отдельные DTO/repository/ViewModel/screen, reuse ChatBubble/ChatComposer/Retrofit/navigation. CLI и документация: day-25-stateful-rag-chat, backend/scripts, component READMEs и ссылка из корневого README. Новые внешние сервисы и зависимости не планируются; live baseline — до 24 provider calls на оба сценария, без retries/repair/judge.
