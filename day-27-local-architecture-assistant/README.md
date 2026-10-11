# Day 27 — Local Android Architecture Assistant

## Суть эксперимента

Небольшой самостоятельный Python CLI объясняет один Kotlin-файл из явно разрешённого
Workspace через локальную Ollama. Ответ разделён на факты с номерами строк,
предположения и ограничения. Код, вопросы и ответы приложение не сохраняет.
Backend, Android UI и облачные API не нужны.

## Что проверяет

- Полезность объяснения роли класса, его зависимостей и видимых вызовов по одному файлу.
- Отказ при выходе за Workspace, ссылках/junctions, превышении лимитов и обрыве генерации.
- Разделение механической проверки строк и ручной оценки смысла.

Один metadata-запрос `/api/show` определяет поддержку thinking; при поддержке
передаётся `think:false`. Затем выполняется максимум одна генерация без повторов.
Стартовые `--num-ctx 8192 --num-predict 2048` задают токены. Отдельные лимиты:
файл 16 KiB, вопрос 2000 символов, полное тело запроса 24 KiB. Байтовые ограничения
не гарантируют вмещение в token context; исходник автоматически не обрезается.

## Результаты

9 октября 2026 выполнен один запуск на Windows: Ollama 0.40.2,
`qwen3.5:9b-q4_K_M`, 8192/2048, `think:false`. Завершение `stop`, exit 0;
18,421 с целиком, 530 входных и 256 выходных токенов. Ollama сообщила
18,302 с обработки, включая 7,894 с загрузки модели.

Сопоставление с синтетическим [CheckoutCoordinator.kt](tests/fixtures/CheckoutCoordinator.kt)
показало полезное описание пустой корзины, отказа оплаты и очистки после успеха.
Есть замечания: модель необоснованно назвала PaymentGateway интерфейсом, связала
недостаток контекста с отсутствием импортов и неполно раскрыла роль координатора
и навигацию. Структура и диапазоны строк прошли проверку; это не доказывает
семантическую корректность. Пользователь подтвердил ручной verdict:
**«Частично полезно, замечания подтверждаю»**.
Это наблюдение одного запуска, не benchmark; на macOS запуск ещё не проверен.

## Запуск

Нужны **Python 3.12+**, Ollama и заранее установленная локальная модель.
Перед работой включите `disable_ollama_cloud: true` в существующем
`~/.ollama/server.json` (сохранив остальные настройки) или `OLLAMA_NO_CLOUD=1`
в окружении сервера, перезапустите Ollama и проверьте актуальный startup log:
`Ollama cloud disabled: true`. Не включайте request-body logging.
[Инструкция Ollama](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).
CLI не управляет сервером; loopback URL сам по себе не доказывает local-only.

Windows, PowerShell, из корня репозитория:

```powershell
cd day-27-local-architecture-assistant
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe assistant.py --workspace tests/fixtures --file CheckoutCoordinator.kt --model qwen3.5:9b-q4_K_M
```

macOS, Terminal, из корня репозитория (команды пока не проверены на Mac):

```sh
cd day-27-local-architecture-assistant
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python assistant.py --workspace tests/fixtures --file CheckoutCoordinator.kt --model qwen3.5:9b-q4_K_M
```

Без `--question` программа спросит один вопрос в терминале. Можно добавить
`--question "Какую роль выполняет этот класс?"`; такой аргумент может попасть
в историю shell. `--model` или `LAA_MODEL` выбирает модель, `--base-url` или
`LAA_BASE_URL` — HTTP loopback адрес (default `http://127.0.0.1:11434`).
Флаги имеют приоритет; proxy и redirects отключены.

Пользовательский Workspace держите вне Git-репозитория; домашние синтетические
данные можно поместить в уже игнорируемую `.local/`. Используйте локальный checkout
без конкурентной подмены путей: CLI не является OS sandbox. В этом задании
корпоративные данные не используются. Программа ничего не копирует в Workspace.

Для offline-проверок установите `requirements-dev.txt` вместо `requirements.txt`
и выполните тем же Python `-m pytest tests -q`. Подробности проверки и ограничения:
[OpenSpec design](../openspec/changes/archive/2026-10-11-day-27-local-architecture-assistant/design.md).
