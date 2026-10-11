# Day 27 — verification notes

## Implementation and offline

2026-10-09, Windows, Python 3.14.7, httpx 0.28.1, pytest 9.1.1.
Проверки запускались установленным Python из backend/.venv; приложение не импортирует
backend и требует только собственный requirements.txt. Другие дни не тестировались/не изменялись.

Команда из каталога Day 27: `../backend/.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider`.
Результат: **101 passed, 1 skipped, 0.42 s**. Skip — POSIX FIFO на Windows;
Windows symlink и junction реально проверены. AST syntax check: 8 Python files, PASS.
Первая попытка тестов имела два setup errors из-за автоматически сгенерированного
огромного pytest ID для 256 KiB fixture; введены короткие IDs. После исправления
прогон прошёл. Никакого live inference при offline tests не было.

## Server prerequisite and single live attempt

Первоначальный журнал показывал cloud disabled=false; generation не выполнялась.
Пользователь включил local-only и перезапустил сервер. Проверен новый процесс 27520,
старт 2026-10-09 22:18:33 Europe/Moscow; его актуальный server.log:
cloud disabled=true, OLLAMA_NO_CLOUD=true, OLLAMA_DEBUG_LOG_REQUESTS=false,
OLLAMA_DEBUG=INFO, listener 127.0.0.1:11434, версия 0.40.2.
Настройки сервера приложением/агентом не менялись.

Metadata /api/show подтвердила completion и thinking для qwen3.5:9b-q4_K_M,
без remote_model/remote_host. CLI повторно проверила capabilities перед единственной
generation; отправлен think=false. Исходник — только tests/fixtures/CheckoutCoordinator.kt.
Вопрос просил роль класса, зависимости, порядок взаимодействий и ветви пустой корзины/отказа оплаты.
Полный prompt/response не сохранялись в файлы; результат предоставлен пользователю в чате.

| Metric | Observed |
|---|---:|
| Inference calls | 1 |
| num_ctx / num_predict | 8192 / 2048 |
| think | false |
| exit / status / done_reason | 0 / completed / stop |
| wall elapsed | 18.421 s |
| prompt_eval_count | 530 |
| eval_count | 256 |
| Ollama total_duration | 18.3017114 s |
| Ollama load_duration | 7.8941516 s |

Повторов, repair и подстройки после live нет. Счётчики — reported Ollama,
не пересчёт байтов; performance на Mac M1 16 GB не измерялась.

## Semantic review

Mechanical validation: PASS (schema, required fields, completion, integer line ranges).
Codex source inspection: **частично полезно, есть неподтверждённые утверждения**.

- Верно: ранний EmptyCart без оплаты, вызов charge, отказ PaymentDeclined,
  очистка корзины только после approved и перед навигацией.
- PaymentGateway назван интерфейсом, хотя определения типа в файле нет.
- Отсутствие импортов ошибочно названо причиной неизвестности: типы могли бы быть
  в том же package; действительная граница — отсутствие их определений/реализаций.
- Термин «транзакция» неоднозначен, атомарность/rollback код не показывает.
- Ссылка на одну строку cart.clear механически допустима, но не охватывает следующий
  вызов navigator.openReceipt; типы зависимостей, расчёт суммы и роль координатора раскрыты неполно.
- В assumptions пусто, хотя некоторые интерпретации следовало отделить от facts.

**Human review: completed.** Пользователю предоставлены fixture и полный ответ в чате;
он подтвердил verdict: **«Частично полезно, замечания подтверждаю»**.
Задача ручной оценки завершена с частичным качественным результатом; это не semantic PASS.
Технический успех не означает полную смысловую достоверность.
Никаких обещаний production/corporate readiness.
