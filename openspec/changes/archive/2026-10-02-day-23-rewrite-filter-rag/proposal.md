## Why

Day 22 cosine Top-5 иногда находит тематически близкие chunks без нужных фактов: Q07/Q08 имеют retrieval gaps, а Q10 получает context при отсутствии RPO/RTO в corpus. Day 23 проверит, как LLM query rewrite и фиксированный similarity filter меняют найденные факты и ответы, включая регрессии, используя сохранённый baseline.

## What Changes

- Добавить CLI-only эксперимент: original question → LLM rewrite → query embedding → cosine Top-10 → threshold 0.50 → максимум Top-5 → generation по ORIGINAL question.
- Переиспользовать pinned Day 21 structure-aware index и frozen Q01–Q10, answers, retrieval и manual review сохранённого Day 22 run; baseline live не повторять.
- Rewrite получает только original question. Сохранять точный retrieval query; добавить ручные `rewrite_preserves_intent` (yes/partial/no) и `rewrite_added_project_assumption` (yes/no), с короткой note при необходимости.
- Показывать все candidates и решения `kept`, `dropped_below_threshold`, `dropped_top_k_limit`; пустой context сохранять без fallback.
- Разделить `retrieve`, `compare` по сохранённому retrieval и полностью offline `report`; сравнивать per-fact context/answer coverage обеих версий и enhanced groundedness без общего score.
- До live закрепить config. Threshold выбран по Day 22 evidence, включая Q10, на original queries; comparison не является независимым benchmark. После rewrite результаты, включая Q10 выше порога и ухудшения успешных вопросов, сохранять без перенастройки или semantic reruns.

## Capabilities

### New Capabilities

- `rewrite-filter-rag-experiment`: наблюдаемый rewrite/filter pipeline, staged CLI, сохранённое baseline comparison и минимальный manual review.

### Modified Capabilities

Нет. Контракты Day 21/22 остаются прежними; параметризация shared cosine search сохраняет default Top-5 Day 22.

## Impact

- Небольшой Day 23 layer в backend, новый `backend/scripts/day23_rag.py`, focused tests; переиспользовать existing embedding, Responses, context assembly и evidence helpers без новых зависимостей.
- Новая папка `day-23-rewrite-filter-rag/README.md`, ссылка в корневом README, команды/контракт в scripts/backend README. Локальные evidence остаются вне Git.
- Без Android UI, FAISS/vector DB, BM25/hybrid retrieval, отдельного reranker/cross-encoder, RAGAS/LLM judge, MCP, VPS, reindexing и generic RAG framework. Строгий abstention contract относится к Day 24.
