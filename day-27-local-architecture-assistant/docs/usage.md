# Local Android Architecture Assistant — руководство

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
[OpenSpec design](../../openspec/changes/archive/2026-10-11-day-27-local-architecture-assistant/design.md).

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

Подробные контракты и тестовый план: [Day 28 design](../../openspec/changes/day-28-local-architecture-rag/design.md).

## Day 29: контролируемые эксперименты

В extended `explain --retrieval ...` добавлены `--temperature 0..2` и
`--keep-alive 0|5m`. Без этих опций прежние defaults сохраняются: temperature=0,
keep_alive=0. Legacy explain не изменён. `--num-ctx` и `--num-predict` остаются
прежними. RAG/SQLite/Workspace и проверка источников общие.

stderr содержит retrieval_seconds (включая query embedding), generation_seconds
(HTTP generation, включая возможную загрузку), elapsed_seconds всего CLI и
provider durations в наносекундах. Эти интервалы пересекаются: их нельзя
складывать. TTFT для stream=false unavailable. HTTP read timeout 180 s — не
wall-clock deadline повседневного CLI.

Маленький driver работает только с S1–S6 и двумя точными Q4 tags. Из корня repo:

```powershell
py -3 -B day-29-local-assistant-optimization/driver.py
```

Первый вызов — offline preview с проверкой frozen manifest, без HTTP. Для тестов
используйте рабочий каталог `day-27-local-architecture-assistant`:

```powershell
py -3 -B -m pytest tests ../day-29-local-assistant-optimization/tests -q -p no:cacheprovider
```

Python 3.12+, httpx, pytest уже достаточны.

Live выполняется **после отдельного разрешения на установку и эксперимент**:
проверить exact tags/digests, local-only конфигурацию работающего Ollama, затем
`--stage quality --approved-live-local-only --record`. Driver не выполняет pull.
Основной baseline: ctx8192/predict2048/temperature0/seed28/keep_alive5m. Полные
доступные sampling defaults и provenance фиксируются для Ollama 0.40.2; неизвестный
runtime/параметр блокирует серию. `backend=unavailable` честно означает отсутствие
подтверждённой backend metadata; API profile не доказывает activation каждого sampler.

Сначала bounded load-only/readiness и S1; после успеха S2–S6 без новых embeddings.
Admission обозначается cold только при `not_resident_before`; cache warmth и
OS page cache не выводятся из keep_alive. `resident_before` означает наблюдение
до запроса, не гарантию отсутствия eviction позже. Provider load_duration позволяет
увидеть повторную загрузку. Результаты разных config hashes анализируются раздельно.

`--record` разрешает только content-free `.local/day29-attempts.jsonl`, который
исключён из Git. Ответы, включая ответы с technical failure, выводятся только в
терминал для смыслового review; reasoning не сохраняется. Не перенаправляйте stdout
в отчёт. Записи start/end сохраняют все попытки; отсутствие end означает incomplete.
Budget: максимум 32 load/chat attempts и 90 минут суммарного ограниченного client
execution (включая metadata/инструментирование; паузы review не входят). Failed
configuration закрывается и между запусками. Повтор одинаковой попытки запрещён.
После deadline/cancel/неизвестной cleanup вся серия остановлена для review оператора;
не удаляйте журнал ради повторов. Отмена собственного subprocess не доказывает
завершение server runner. Driver не перезапускает Ollama и не завершает чужие процессы.

После review всех S1–S6 `--stage rag --candidate EXACT_TAG --semantic-reviewed`
(с теми же live/record флагами) использует существующие query embedding/retrieval/
generation. Нужен отдельный `.local/day29-knowledge` только с копиями
`day-28-local-architecture-rag/fixtures/knowledge/checkout.md` и
`day-29-local-assistant-optimization/fixtures/knowledge/compose.md`; индекс создаётся
обычной командой `knowledge index --knowledge .local/day29-knowledge --yes` из корня
repo **после разрешения на live embeddings**. Старые indexes не используются.
Driver проверяет состав и freshness, не строит index автоматически.

`--stage variation --candidate EXACT_TAG --semantic-reviewed --factor keep_alive`
(либо num_predict, temperature) сравнивает один фактор с принятой baseline, на S2/S6.
Результаты baseline переиспользуются. Комбинации факторов, token-fit для 4096,
prompt correction, Q8 и дополнительные повторы здесь не автоматизированы: только
при конкретной причине, отдельном review и оставшемся бюджете. Это не полный перебор.
Окончательный выбор требует [смысловой рубрики](../../day-29-local-assistant-optimization/rubric.md)
и реальных RAG S2/S6; `--semantic-reviewed` фиксирует решение человека, не оценивает модель.

RAM: GlobalMemoryStatusEx total/available; VRAM: nvidia-smi system-wide used MiB;
Ollama ps: model size/size_vram/context. Только before/after snapshots, не peak и не
процессный RSS. Mac pressure/swap и отзывчивость Android Studio проверяются вручную
на M1; Windows не подтверждает Mac. План и текущий статус —
[Day 29 validation](../../openspec/changes/day-29-local-assistant-optimization/validation.md).
