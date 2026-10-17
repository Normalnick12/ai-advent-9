# Day 19 — Проверка сохранённой MCP-цепочки

Ровно одна live-попытка: operation `085e5b0a-863f-4a62-abd9-f62359a2393d`.
Все gates PASS. Независимая проверка завершена по операторскому экспорту:
три отдельных tools, точные оба transitions, правильные отчёт и файл, final — PASS.
130 версий; tail 1.19.0-rc01/1.19.0/1.19.1. Файл 415 bytes, hash начинается с
5bac0dfe3e5a. Предварительные NOT_PROVEN сохранены как история отсутствовавшего evidence.

Сохранённые технические основания:

- [Native response](evidence/live-20260924/response.json) и [actual calls](evidence/live-20260924/operation.json).
- [Серверные события](evidence/live-20260924/operator-verification-20260924T151255Z/server-events.json).
- [Независимое чтение](evidence/live-20260924/operator-verification-20260924T151255Z/file-read.json)
  и [фактический JSON-файл](evidence/live-20260924/operator-verification-20260924T151255Z/file-bytes.json).
- [Раздельные final verdicts](evidence/live-20260924/operator-verification-20260924T151255Z/verdict-final.json).

Порядок технической проверки:

1. Проверить состав цепочки: один запрос, один MCP-сервер, три отдельных tools — получение,
   обработка, сохранение. Discovery содержит ровно три имени;
   Day 18 scheduler в цепочке не участвует.
2. Сверить сохранённые gates: offline, actual deployment revision, readiness
   и pre-live измерение полного списка с выбранным бюджетом. Preflight — отдельная
   техническая проверка, не первый вызов live.
3. Открыть evidence единственной попытки: operation ID, model, auto, allowlist,
   отключённые retries, затем ordered MCP items и actual arguments/outputs.
   Учесть фактическое число calls, включая лишние/ошибочные, если они были.
4. Проверить два отдельных сравнения verifier: полный lookup → summarize arguments
   и полный report → save arguments. Проверка охватывает весь список, а не только
   количество и последние три строки.
5. Сверить отдельный read-only экспорт файла с VPS: file ID, bytes/hash и JSON.
   Затем verdicts tools/order/transfers/report/file и отдельно raw final text с
   final_text_accuracy. Receipt без независимого чтения недостаточен.
6. Различать фактические итоги: chain PASS и отдельно final_text_accuracy PASS. Один прогон не доказывает
   устойчивость модели; неверный финальный текст не отменяет доказанный правильный
   файл, и наоборот.

Проверка использует сохранённую трассу единственной завершённой попытки.
Чтение отчёта не требует повторного запуска launcher или новых вызовов модели.

Используйте только redacted evidence. `.env`, protected VPS environment,
приватные SSH-ключи и пароли не входят в публикуемые технические материалы.
