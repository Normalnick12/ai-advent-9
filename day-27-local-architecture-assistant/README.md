# Day 27 — Local Android Architecture Assistant

## Суть эксперимента

Небольшой самостоятельный Python CLI объясняет один Kotlin-файл из явно разрешённого
Workspace через локальную Ollama. Ответ разделён на факты с номерами строк,
предположения и ограничения. Код, вопросы и ответы приложение не сохраняет.
Backend, Android UI и облачные API не нужны. Расширение Knowledge и локальный RAG
добавлены в эту же утилиту в [Day 28](../day-28-local-architecture-rag/README.md).

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

## Knowledge и RAG (расширение Day 28)

Прежняя команда без subcommand сохраняет поведение Day 27. Новые команды:
`knowledge preview/index/status`, `search`, `explain`; подробности — `COMMAND --help`
или `knowledge index --help`. Ниже команды запускаются из каталога этой утилиты.

Один раз подключите **отдельный локальный каталог Markdown вне Git** и постройте
индекс. Knowledge и Workspace не могут совпадать или быть вложенными друг в друга.
Workspace никогда автоматически не индексируется. Нужна установленная embedding-модель:
`ollama pull qwen3-embedding:0.6b` выполняет сам пользователь. CLI ничего не скачивает.

Windows / PowerShell:

```powershell
$env:LAA_KNOWLEDGE = 'C:\LocalDocs\architecture'
$env:LAA_MODEL = 'qwen3.5:9b-q4_K_M'
.venv/Scripts/python.exe assistant.py knowledge index
.venv/Scripts/python.exe assistant.py explain --workspace C:\LocalWorkspace --file CheckoutCoordinator.kt --retrieval vector
# После изменения Markdown:
.venv/Scripts/python.exe assistant.py knowledge index
```

macOS / shell (фактическая проверка Mac пока PENDING):

```sh
export LAA_KNOWLEDGE="$HOME/LocalDocs/architecture"
export LAA_MODEL='qwen3.5:9b-q4_K_M'
.venv/bin/python assistant.py knowledge index
.venv/bin/python assistant.py explain --workspace "$HOME/LocalWorkspace" --file CheckoutCoordinator.kt --retrieval vector
.venv/bin/python assistant.py knowledge index
```

Переменная действует в текущем терминале; при желании задайте её в обычной настройке
shell. Явный `--knowledge` имеет приоритет, пустое значение — ошибка. Вопрос можно
вводить интерактивно. `--retrieval none` использует общий расширенный формат без
документов, игнорирует LAA_KNOWLEDGE и не принимает явный `--knowledge`.

Первый index показывает список относительных путей и требует `yes`. Добавление,
удаление файлов и изменение selection требуют нового принятия; изменение текста
уже разрешённых файлов принимается самим вызовом index. Для automation используйте
`--yes`: это явное принятие показанного набора. Без TTY и без принятия index не пишется.
`--include a.md --include sub/b.md` сужает список, `--exclude draft` исключает
файл/поддерево; это пути, не glob. Policy сохраняется автоматически; `--all-markdown`
сбрасывает её. Достаточно положить новый Markdown в Knowledge и повторить index.

Preview/status/search необязательны перед объяснением:

```text
python assistant.py knowledge preview
python assistant.py knowledge status
python assistant.py search --mode text --query PaymentGateway
python assistant.py search --mode vector --query "Когда разрешена навигация после оплаты?"
python assistant.py explain --workspace W --file A.kt --retrieval text
python assistant.py explain --workspace W --file A.kt --retrieval none
```

Индекс находится в `Knowledge/.laa/index.sqlite3`; он содержит читаемые фрагменты
документации и локальные float32-векторы. Его можно переносить вместе с каталогом K.
Ссылки/junctions/reparse points и служебные каталоги исключены; явный запрещённый
путь вызывает отказ. Markdown нормализуется в UTF-8/LF. ATX headings учитывают
вложенность и fenced code, Setext остаётся обычным текстом. Chunk — до 1800 символов;
overlap 180 используется только для слишком длинного фрагмента. Это не token limits.
Лимиты: 500 документов, 256 KiB raw на файл, 4 MiB raw суммарно, 4096 chunks,
10000 directory entries. Пустой набор не индексируется.

Перед search/explain проверяются hashes и состав документов, включая изменения
с прежними size/mtime. Устаревший/неполный index вызывает ошибку без fallback.
Полный rebuild атомарен; unchanged index — no-op без embeddings (metadata модели
проверяется). Модель сохраняется в profile; при смене digest/модели нужен
явный `knowledge index --rebuild`, при необходимости `--embedding-model MODEL`.
Несовместимую старую базу можно перестроить с повторным принятием selection;
старые OpenAI vectors не импортируются.

Text использует встроенный SQLite FTS5, unicode61, underscore внутри токена,
case-insensitive literal OR terms, до 64 terms. CamelCase целиком, без stemming,
fuzzy search или гарантии substring по endpoint. BM25: меньше score — выше rank.
Text не обращается к Ollama. Vector — cosine: больше score — выше rank, без
универсального порога. Scores между режимами несопоставимы. `--top-k` = 4 по
умолчанию, диапазон 1–10. Поиск не генерирует ответ. Query до 2000 символов;
explain добавляет filename stem и CamelCase words **только для retrieval**, до 4096
символов. Generation получает исходный вопрос.

Explain разделяет Kotlin observations/lines, Markdown rules/quotes, applications
с обеими опорами, assumptions и limitations. Источники показывают relative path,
section и Markdown lines отдельно от Kotlin lines. Валидатор проверяет done/stop,
JSON, IDs, строки и точные цитаты <=400 символов только из переданных chunks.
Цитата не доказывает применимость правила; смысл проверяет разработчик.
Нет retries, repair или выполнения команд из документов/ответов. Offline mocks
проверяют границу данных, но не гарантируют устойчивость модели к injection.

Extended chat: 8192/2048 tokens, temperature=0, seed=28, think=false при поддержке;
24 KiB всего JSON body, 16 KiB Kotlin, 2000 символов вопроса, 256 KiB ответа.
Помещаются только целые chunks; selected/omitted видны в stderr metrics. Если ни
один hit не помещается — budget error, а не «знаний нет». Точный tokenizer preflight
отсутствует; server truncation остаётся ограничением. Индекс/вопрос/модель влияют
на результат, одного A/B недостаточно для общего вывода о превосходстве RAG.

Для M1 16 GB начните с qwen3-embedding:0.6b (1024 dimensions); batches <=8 и
64 KiB, ответ embeddings <=2 MiB. Batches последовательны; последний embedding,
query embedding и extended chat используют keep_alive=0. В контролируемом сервере
отдельно задайте `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`; CLI не меняет
config и не выгружает чужие модели. Пригодность 9B на M1 ещё не измерена: выполните
focused tests и компактную A/B, запишите memory pressure, swap, времена и OOM.
Замена generation-модели требует новой сопоставимой пары.

Проверка FTS5: `python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(text)'); print('FTS5 OK')"`.
При отсутствии FTS5 нужна сборка Python с этой возможностью; CLI не скачивает
extensions и не заменяет алгоритм. Runtime dependencies общие для Windows/macOS:
Python 3.12+ и httpx, SQLite входит в Python. Полный offline suite: `python -B -m pytest -q -p no:cacheprovider`.

CLI сохраняет только одобренную Knowledge. Код Workspace, вопросы, query vectors,
prompts и ответы не пишутся в файлы, отчёты или index. Диагностика без текстов и
пользовательских путей. Отображение терминала, shell history, server logs/backups
и шифрование диска остаются ответственностью окружения. Корпоративные данные не
должны находиться в Git; индекс тоже содержит документы в читаемом виде.
Exit codes: 0 — результат (включая признание нехватки контекста), 2 — ввод,
1 — ошибка выполнения/index/output, 130 — отмена.

Подробные контракты и тестовый план: [Day 28 design](../openspec/changes/day-28-local-architecture-rag/design.md).
