# Day 21 — Индексация документов

## Суть эксперимента

CLI превращает 22 реальных файла проекта о сохранении диалога и состоянии задачи
в локальный knowledge index: documents → chunks → embeddings → SQLite.
Corpus включает README, актуальные OpenSpec specs, Python backend и Kotlin Android.

На одном snapshot сравниваются fixed-size окна с лимитом 500 tokens и целевым
overlap около 50 и structure-aware deterministic chunking. Вторая стратегия
использует Markdown headings, Python AST и Kotlin formatting boundaries;
слишком большой блок делится тем же token-based helper. Обе используют
OpenAI `text-embedding-3-small`, 1536 измерений.

## Что проверяет

- Как границы chunks меняют представление одних и тех же исходных участков.
- Сохранность текста, metadata и embeddings после повторного открытия SQLite.
- Полный путь от corpus и offline preview до сохранённого индекса.

## Результаты

В одном live-прогоне 28 сентября 2026 создан SQLite index с 321 chunk и настоящими
embeddings размерности 1536. Обе стратегии использовали один snapshot 22 файлов.

| Стратегия | Chunks | Min / median / max tokens | Всего tokens | Fallback chunks |
| --- | ---: | --- | ---: | ---: |
| Fixed-size | 95 | 56 / 500 / 500 | 41 717 | 0 |
| Structure-aware deterministic | 226 | 3 / 112,5 / 500 | 38 512 | 16 |

На заранее выбранных участках structure-aware отделила Markdown Requirement
и Scenario, а Python `append_turn` сохранила отдельным chunk; fixed-size тоже
содержал весь этот метод, но вместе с соседним кодом. Длинные `restore()` и
`send()` потребовали разбиения — структура не отменяет token limit.

10 offline-тестов прошли. После live `compare` и `inspect` прочитали SQLite
в новых процессах без API key и повторных embedding calls. Provider usage
составил 80 229 tokens за 11 calls; это наблюдение одного запуска, не оценка
производительности. Retrieval quality не проверялось; поиска в Day 21 нет.

Сохранённый run: `3a3c3319-5516-4526-8e56-33ab1251da72`.
Corpus hash: `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`.

Зависимости и контракт описаны в [backend](../backend/README.md#day-21--индексация-документов),
команды — в [scripts](../scripts/README.md#day-21--индексация-документов).
`OPENAI_API_KEY` используется только на backend; выбранные тексты отправляются
OpenAI для embeddings, SQLite хранится локально.
