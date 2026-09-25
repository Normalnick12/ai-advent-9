# Day 20 — Orchestration MCP

## Суть эксперимента

Агент исследует зависимости `android/nowinandroid` для локального хранения и
фоновой работы, проверяет их публикации в Google Maven и получает сводки.
В отличие от Day 19, одновременно доступны два независимых сервера:
DeepWiki и существующий Dependency Composition MCP. Используется
`tool_choice="auto"`; prompt не содержит имён tools, готовых coordinates
или расписанного маршрута.

## Что проверяет

- Выбор возможностей разных MCP-серверов в рамках одной инженерной задачи.
- Переход research → lookup → summary каждой ветки с передачей полного результата.
- Разделение фактического tool flow, финальных publication facts и истины источников.

## Результаты

Одна live-попытка: 1 model run, 6 MCP calls. Модель дважды выбрала DeepWiki
`ask_wiki_question`: нашла зависимости и уточнила объявления. Затем через
Dependency MCP выполнила lookup → summary для Room и WorkManager.

| Coordinates | Публикаций | Последние три в порядке источника |
|---|---:|---|
| `androidx.room:room-runtime` | 92 | `2.8.3`, `2.8.4`, `2.8.5` |
| `androidx.work:work-runtime-ktx` | 91 | `2.12.0-beta01`, `2.12.0-rc01`, `2.12.0` |

Flow и финальные publication facts — **PASS**. Порядок, полная передача данных
и summaries проверены независимо. Для обеих веток точная проверка provenance
цитат дала **FAIL**, проверка объявленных версий — **NOT_PROVEN**;
истина исходников и revision также **NOT_PROVEN**. Это ограничения сохранённого
результата, не скрытые успешным flow. Одна попытка не доказывает устойчивость.

[Отчёт](evidence/live-20260925/review/report.md),
[пояснения FAIL / NOT_PROVEN](evidence/live-20260925/review/review-notes.md)
и [исходное evidence](evidence/live-20260925/) сохранены без повторного live.
Видео записано — подтверждено пользователем.

Настройка описана в [backend](../backend/README.md), команды подготовки и
offline-проверки — в [scripts](../scripts/README.md).
`OPENAI_API_KEY` и MCP token остаются на backend. Для подготовки credential
потребовалось отдельно разрешённое чтение существующего env через SSH;
серверы и конфигурация VPS не менялись.
