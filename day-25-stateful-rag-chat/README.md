# Day 25 — Stateful RAG mini-chat

## Суть эксперимента

Mini-chat соединяет историю разговора, отдельную Task Memory и факты из
индекса документов Day 21. Полная история хранится на backend, но модель видит
только последние три подтверждённые пары, цель/условия пользователя и текущий
RAG Top-5. Один ответ модели предлагает grounded answer и memory patch;
runtime проверяет обе части перед атомарным сохранением.

## Что проверяет

- Сохранение ранних цели и ограничений после выпадения U1/U2 из recent history.
- Участие task memory в фактическом retrieval query и наличие проверенных sources/citations.
- Точное восстановление history/memory после reopen, отдельные outcomes для abstention и technical failure.

## Результаты

Один frozen A/B прогон 3 октября 2026 использовал 12 embeddings и 12 generations,
без повторов. A сохранил 5 пар: модель пропустила раннюю цель/условия в memory,
а A6 отклонён из-за искажённого chunk ID. B сохранил 6 пар и прошёл механические
U6-проверки: U1/U2 отсутствуют в actual recent input, но условия остались в memory
и embedding query. Оба сценария точно восстановились после reopen на T3.

Смысловой успех не подтверждён: B5/B6 перенесли правило reset после потерянного
Send из Day 07 в задачу Day 13. Проверенные literal citations не гарантируют
применимость источника к текущей задаче. Пользователь просмотрел saved report и
подтвердил эти выводы; reviewer и исходный разбор записаны в evidence.
Без ablation не доказана исключительная причинная роль memory.

Offline: 113 backend checks и 6 runner checks; Android — 12 JVM, 4 Day 25 UI
и 9 navigation checks. Android используется как thin client, а long-scenario
acceptance выполняется backend/CLI. Saved evidence и команды просмотра — в scripts.
Отдельная Android-демонстрация подтвердила отображение ответа, sources и Task Memory
за 1 embedding + 1 generation; скриншоты сохранены. Запись видео ещё не подтверждена.

Настройка и contracts описаны в [backend](../backend/README.md),
[Android](../android-app/README.md) и [scripts](../scripts/README.md).
`OPENAI_API_KEY` задаётся только на backend.
