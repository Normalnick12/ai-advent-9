# Day 09 — Управление контекстом: сжатие истории

## Суть эксперимента

Агент переходит от полной истории к rolling summary и четырём последним raw
сообщениям. SQLite сохраняет все подтверждённые сообщения; меняется только
контекст, отправляемый модели. Response и summarizer используют `gpt-4o-mini`.

## Что проверяет

- FULL и COMPRESSED input на одном снимке диалога, включая дополнительный расход,
  если короткую историю сжимать невыгодно.
- Отдельную стоимость обновления summary и получения ответов.
- Сохранение трёх точных фактов в явном сравнении двух ответов без изменения
  диалога. Оценка N/3 относится только к этим фактам.

## Результаты

Ручной live experiment подтверждён пользователем. После четырёх confirmed
turns карточка последнего normal response показала 2 сообщения в summary,
raw tail 4/4 и preflight **3485 → 1907 tokens**: уменьшение на **1578 (45.3%)**.
Compression использовалась для response context; полная raw history сохранена.

Итоговый compare после исправления verifier:

| Ветка | Сохранено фактов | Actual input | Output | Estimated cost, USD |
| --- | --- | --- | --- | --- |
| FULL | 2/3 | 3533 | 13 | 0.00053775 |
| COMPRESSED | 1/3 | 322 | 14 | 0.0000567 |

FULL вернул `identifier=unknown, limit=37, responsible=Мира`;
COMPRESSED — `identifier=unknown, limit=unknown, responsible=Мира`.
Baseline сам не сохранил identifier. COMPRESSED сохранил responsible, но потерял
limit, который FULL сохранил. В этом прогоне снижение input сопровождалось
потерей части точной информации. N/3 измеряет только эти три факта, не общее
качество ответа; результат не означает, что compression всегда ухудшает quality.
Старые ошибочные scores verifier исключены из итогов; баг исправлен и покрыт тестами.

Maintenance summarization имела отдельные actual usage/cost. Поэтому уменьшение
response input не доказывает такую же денежную экономию. Численные расходы
summarization в отчёт не переданы; полный net cost не рассчитывается.

После restart session восстановлена с count=4, старые bubbles не появились,
runtime measurements/compare results очищены, paid replay отсутствовал.
Summary после restart успешно прочитана. Reset подтверждён: старый диалог
после сброса не восстанавливается.

Зависимости, настройка и запуск описаны в [backend](../backend/README.md)
и [Android](../android-app/README.md). `OPENAI_API_KEY` задаётся только на backend.
