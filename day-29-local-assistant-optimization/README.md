# Day 29 — Оптимизация Local Android Architecture Assistant

## Суть эксперимента

Продолжаем существующую утилиту Day 27–28. Сравниваем Qwen3 4B и Qwen2.5-Coder 7B Q4_K_M на одинаковых Kotlin/Markdown-входах. Основной режим — keep_alive=5m; фактическую резидентность проверяем отдельно. Целевая машина — Mac M1 16 GB с Android Studio, домашняя — Windows с RTX 4070 SUPER 12 GB.

## Что проверяет

- Шесть небольших сценариев, включая Compose, StateFlow и lifecycle; качество объяснения и применение правил оцениваются отдельно от JSON.
- Время загрузки, generation, retrieval и пользовательского запроса; надёжность, snapshots памяти и причины незавершённых попыток.
- Изменение одного параметра после выбора предварительного кандидата, с ограниченным бюджетом и остановкой после ошибок.

## Результаты

**Итог совместного review: NO SUITABLE PROFILE CONFIRMED.** Compact S4 — technical PASS / semantic PASS по основной задаче; S6 — technical PASS / semantic FAIL: модель неверно объяснила перезапуск LaunchedEffect при изменении ключей. Уменьшение копирования Kotlin не подтвердило общую практическую пригодность. Эксперименты prompt/schema Day 29 завершены, compact не переносится в default CLI.

Тестовая Markdown Knowledge содержит архитектурные соглашения, но не полную семантику Compose API; это не оправдывает фактическую ошибку модели. Локальная справочная Knowledge по Kotlin/Coroutines/StateFlow/Lifecycle/Compose отмечена только в будущем backlog. Последняя offline-проверка: **349 passed / 1 skipped**; всего **14/32 попыток**, Mac NOT TESTED. OpenSpec **23/33**: закрыт состоявшийся совместный review, невыполненные задачи остаются открытыми. [Финальный review и backlog](../openspec/changes/day-29-local-assistant-optimization/final-review-2026-10-11.md).

Ниже сохранена хронология прежних проверок; их промежуточные статусы не заменяют итог выше.

Offline: **258 passed / 1 skipped**. После установки кандидатов и подтверждения local-only выполнена ограниченная Windows-серия с точными digests.

Qwen3 4B загрузилась за 3,55 с, прошла технический S1, но S2 нарушил ссылки на observation IDs. Смысловая оценка assistant: S1 PARTIAL (пропущен успешный путь), S2 FAIL (в том числе enum вместо sealed interface). S3–S6 не запускались. Coder 7B достиг admission deadline 60 с; его S1–S6 не запускались. Клиент прекращён, завершение server runner не подтверждено, серия остановлена.

Использованы 4/32 load/chat attempts. Полноценное сравнение качества и Compose не состоялось; модель не выбрана, ожидается совместный review. Подробности и безопасные метрики — в [live review](../openspec/changes/day-29-local-assistant-optimization/live-review-2026-10-10.md), подготовка — в [offline checkpoint](../openspec/changes/day-29-local-assistant-optimization/validation.md). Q4/Q8 и Mac M1 — NOT TESTED. Исторические результаты Day 27–28 сохранены.

Зависимости и команды описаны в [README общей утилиты](../day-27-local-architecture-assistant/README.md#day-29-контролируемые-эксперименты). Никакие модели автоматически не скачиваются.

Отдельное продолжение 2026-10-11 после устранения посторонней нагрузки GPU: Coder загрузился за 11,17 с и завершил S1–S6 технически успешно. S1 semantic PARTIAL подтверждён пользователем. Предварительный review S2–S6: PARTIAL / PASS / FAIL / PARTIAL / PARTIAL; S4 неверно применяет нерелевантное правило, S6 не объясняет lifecycle. S2 включал повторную загрузку после паузы и занял 18,06 с; S3–S6 при резидентной модели — 6,71–9,41 с. Общий счёт с историческими отказами — 11/32 attempts. Модель не выбрана, ожидается смысловой review; RAG и оптимизации не выполнялись. Подробнее: [новый отчёт](../openspec/changes/day-29-local-assistant-optimization/coder-quality-2026-10-11.md). Исторический TIMEOUT сохранён, его причина не доказана.

После подтверждения этих verdicts пользователем подготовлена одна opt-in коррекция prompt без изменения schema и обычного приложения. Focused tests: **118 passed**. Новые S4/S6 не запускались: третий снимок GPU показал 30%, preflight остановил опыт. Улучшение объяснения пока **NOT TESTED**, счёт остаётся 11/32. [Отчёт коррекции](../openspec/changes/day-29-local-assistant-optimization/prompt-correction-2026-10-11.md).

При следующем разрешённом продолжении новый GPU-критерий пройден (6 снимков, медиана 1%). S4 с тем же corrected prompt стал объяснять код своими словами и не применил weather-rule, но зациклился в limitations и исчерпал 2048 токенов: **technical FAIL**, S6 **NOT RUN** по gate. Практическое улучшение не подтверждено; история сохранена, общий счёт 12/32. [Результат и сравнение](../openspec/changes/day-29-local-assistant-optimization/prompt-correction-live-2026-10-11.md).

Подготовлен отдельный экспериментальный контракт `compact-evidence-v1`: правило, цитата, применение и строки Kotlin находятся в одном объекте; нумерацию и статус Knowledge задаёт Python. Базовая инструкция адаптирована к формату, отклонённая prompt-коррекция не используется. **349 passed / 1 skipped** в полной offline-проверке; обычные режимы и история сохранены. Новых live-вызовов нет: полезность нового контракта **NOT TESTED**, ожидается review перед S4→S6. [Schema, отличия и проверки](../openspec/changes/day-29-local-assistant-optimization/compact-contract-offline-2026-10-11.md).

После отдельного разрешения выполнены compact S4→S6: **2/2 technical PASS**. Предварительная смысловая оценка: S4 PASS по отсутствующим знаниям (чужие правила исключены); S6 FAIL (неверное ограничение LaunchedEffect, StateFlow/lifecycle не раскрыты). Копирование Kotlin уменьшилось, но практическая пригодность профиля не подтверждена. HTTP wall: 4,90 с с холодной загрузкой / 9,97 с при резидентной модели. Общий счёт 14/32; default CLI не изменён, остановка для совместного review. [Результаты и метрики](../openspec/changes/day-29-local-assistant-optimization/compact-contract-live-2026-10-11.md).
