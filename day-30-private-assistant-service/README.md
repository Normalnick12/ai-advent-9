# Day 30 — Private Local Architecture Assistant Service

## Суть эксперимента

Необязательный HTTP-чат поверх Local Android Architecture Assistant: FastAPI
переиспользует CLI runtime, разрешённый Kotlin, Markdown Knowledge, retrieval и
проверку источников. История живёт у клиента, каждый ход заново проверяет данные.
CLI работает самостоятельно без HTTP-зависимостей и сетевой инфраструктуры.

## Что проверяет

- Вопрос и контекстное уточнение с проверяемыми источниками.
- Два одновременно принятых запроса, отдельные ответы и предсказуемую перегрузку.
- Bearer-аутентификацию, ограничения входа/контекста и приватность диагностики.
- Сохранение занятых ресурсов при timeout и отключении клиента.

## Результаты

Итог принят пользователем: **IMPLEMENTED — ACCEPTED WITH KNOWN LIMITATION**.
OpenSpec **31/33** остаётся активным: удалённые отрицательные проверки и review
правил доступа не завершены; доставка двух ответов Windows + Android не подтверждена.

Offline-проверки на Windows выполнены с fake Ollama, без настоящего inference.
Два независимых TCP-клиента одновременно обслужены (`max_active=2`), третий запрос
получил 503; health/status оставались доступны, оба первых запроса получили
отдельные успешные ответы. Контекстное уточнение находит текущую документацию по
предыдущему пользовательскому вопросу; старый ответ модели не становится источником.

Первый локальный live-диалог на Windows: **2/2 HTTP 200**, done/stop и механическая
проверка PASS; 13,05 и 10,90 с. Во втором запросе подтверждена передача истории.
Совместный смысловой review: первый ответ **PARTIAL**, уточнение **FAIL** —
почти повторило первый ответ. Подробнее — [live validation](../openspec/changes/day-30-private-assistant-service/live-dialogue-2026-10-11.md).

Одна конкурентная live-пара: два допуска, `max_active=2`, health 200 за 1,15 мс.
Первый клиент получил 200 за 13,22 с; второй — 502 за 37,67 с из-за достижения
лимита выхода (`length`, 2048 токенов). HTTP concurrency **PASS**, критерий двух
успешных ответов **FAIL**; повторов не было. Исправлено подавление transport logs,
66 focused offline tests прошли. См. [concurrent validation](../openspec/changes/day-30-private-assistant-service/live-concurrent-2026-10-11.md).

Отдельно разрешённая дополнительная пара с более узкими вопросами: **2/2 HTTP 200**,
done/stop и механическая проверка PASS; 12,08 и 22,90 с, `max_active=2`, health
за 1,18 мс. Предварительный semantic review: A **FAIL**, B **PARTIAL**.
Критерий двух успешных технических ответов выполнен в новой паре; первоначальный
FAIL сохранён. Это единичная проверка, а не подтверждение устойчивого качества.
Подробнее — [additional concurrent validation](../openspec/changes/day-30-private-assistant-service/live-concurrent-additional-2026-10-11.md).

Пользователь подтвердил HTTPS `/healthz` с Android через мобильный интернет и
Tailscale, без предупреждений TLS: **remote health PASS**. Авторизованный GET
`/readyz` с телефона также подтверждён: **PASS**.

В remote-паре Windows + Android подтверждены два допуска, `max_active=2` и health
200 за 1,23 мс. Windows получил 200 за 11,98 с; исходное ожидание Android оборвалось
через 10 с, а телефон показал 503 дополнительной HTTP-попытки. Две генерации
завершились done/stop и mechanical PASS, но **два успешных клиентских ответа не
подтверждены**. Причина disconnect/дополнительной попытки не установлена.
Serve и HTTP выключены, временный телефонный токен отозван. Бюджет **8/8** исчерпан;
повторных generations нет. См. [remote validation](../openspec/changes/day-30-private-assistant-service/live-remote-2026-10-11.md).
API semantic_status остаётся `not_evaluated`; Coder 7B — технический кандидат, итог Day 29
**NO SUITABLE PROFILE CONFIRMED** сохранён. Mac M1 **NOT TESTED**.

Установка, запуск, клиент, ограничения и recovery — в
[HTTP-компоненте](laa_service/README.md). Фактические проверки и команды — в
[offline validation](../openspec/changes/day-30-private-assistant-service/offline-validation.md).

Финализация Week 6: [технический итог](week-6-technical.md).
