## Context

См. [proposal.md](proposal.md) — Why. Общий backend использует OpenAI-oriented AgentConfig/LlmResult, sessions и evidence; Day 21–25 связаны с pinned corpus, embeddings и сохранением входов/ответов. Day 27 не получает пользы от этих зависимостей. Заимствуем подходы (явные границы, подмена клиента, безопасная диагностика), но не импортируем backend.

В Explore GET-запросами обнаружены Ollama 0.40.2 и локальная `qwen3.5:9b-q4_K_M`. Генерация Day 27 ещё не выполнялась. По сообщению пользователя, Day 26 с окном 4096 исчерпал контекст и оборвал ответ. Mac M1 16 GB — будущая целевая среда, производительность там не измерена.

## Goals / Non-Goals

**Goals:** один прозрачный вызов, ограниченное чтение, переносимый Python и безопасные ошибки; отделение чтения Workspace, сборки объяснения и HTTP позволяет позднее явно добавить Knowledge.

**Non-Goals:** универсальный provider framework, DI-контейнер, AST/компилятор Kotlin, доказательство истинности модельных утверждений, sandbox против конкурентно враждебного процесса. Остальной scope см. proposal. Не создавать пустые Knowledge/RAG interfaces заранее.

## Decisions

### 1. Four small modules and a synchronous call

```text
day-27-local-architecture-assistant/
  README.md
  requirements.txt
  requirements-dev.txt
  assistant.py
  workspace.py
  explain.py
  ollama_client.py
  tests/
    test_workspace.py
    test_explain.py
    test_ollama_client.py
    fixtures/CheckoutCoordinator.kt
```

`assistant.py` отвечает за argparse, одноразовый terminal input, вывод и exit codes. `workspace.py` читает файл, `explain.py` собирает prompt и проверяет результат, `ollama_client.py` выполняет HTTP. Небольшие функции и, при необходимости, dataclass; синхронный httpx.Client передаётся в функцию для тестов с MockTransport. Отдельный Protocol/registry не требуется. Python 3.12+ даёт Path.is_junction для Windows. Альтернативы: расширение backend связывает независимые эксперименты; один огромный script мешает отдельно проверять файловую границу и HTTP.

```text
args / one terminal question
  --> configuration and path validation
  --> bounded Kotlin read
  --> numbered source + question + system instructions
  --> metadata POST /api/show (capabilities)
  --> one local POST /api/chat (think:false if supported)
  --> completion / schema / line checks
  --> Russian explanation and non-content metrics
```

### 2. Small explicit CLI configuration

Обязательны `--workspace` и `--file`. `--question` необязателен: без него и при TTY прочитать один вопрос; при non-TTY/EOF или пустом вопросе выдать ошибку без HTTP. Ctrl+C завершает процесс без traceback (exit 130); после dispatch отмена клиента не гарантирует немедленную остановку вычислений сервера.

Модель: `--model` > `LAA_MODEL`, без model default. URL: `--base-url` > `LAA_BASE_URL` > `http://127.0.0.1:11434`. Непустое явно переданное значение валидируется, ошибочное значение не заменяется скрытым fallback. Backend .env не читается. Минимальные дополнительные параметры: `--num-ctx` (8192) и `--num-predict` (2048); только положительные целые, num_predict < num_ctx. В Day 27 live используются именно defaults, без sweep, auto-tuning или automatic retries. Перед generation один metadata POST `/api/show` с именем модели проверяет capabilities: при `thinking` передать `think:false`, без этой capability не передавать think. Неизвестный/невалидный metadata response или ошибка show блокирует generation. Metadata не содержит исходник или вопрос и не является inference; после него выполняется максимум один `/api/chat`. Другие параметры модели не переопределяются; reasoning controls и сравнение режимов оставлены Day 29.

Пример из каталога утилиты:

```text
python assistant.py --workspace ../.local/day27/workspace --file CheckoutCoordinator.kt --question "Какую роль выполняет этот класс?" --model qwen3.5:9b-q4_K_M
```

Успех — exit 0, ошибка ввода/конфигурации — 2, I/O/API/незавершённый или непригодный ответ — 1. Ответ — stdout, безопасная диагностика и метрики — stderr. Интерактивный prompt не содержит исходник. Чата/истории нет.

### 3. Workspace is an explicit filesystem boundary

Разрешённый root — существующий локальный каталог, канонизированный resolve(strict=True); явный root определяет разрешённую область. Относительный file трактуется только от этого root. Отвергать абсолютные/drive-relative/UNC/device пути файла, компоненты `..`, двоеточие/ADS и Windows ambiguous trailing dot/space, а также не-.kt и не-обычные файлы. Не ограничивать допустимые обычные имена ASCII: пробелы и кириллица поддерживаются.

После определения root проверять каждый компонент относительного пути без следования symlinks/junctions; такие ссылки внутри Workspace отвергать, даже если их цель внутри. Конечный canonical path должен быть relative_to root, не строковым prefix. На Windows непонятный reparse point отвергать безопасно. Не поддерживать сетевой Workspace в этом локальном эксперименте. Ничего не читать до проверок; затем читать только выбранный файл с лимитом + 1 byte, а не неограниченный read_text после stat.

Файл декодируется UTF-8-sig со строгими ошибками, CRLF/CR нормализуются в LF. Нумерация 1-based относится к полученному тексту, пустые строки сохраняются. Пустой/пробельный файл отклоняется. Нет glob, обхода дерева, чтения импортов или соседних файлов. Модель получает только относительный путь.

Граница угроз — локальный checkout без конкурентной враждебной подмены путей во время проверки/открытия. Проверка resolve не является OS sandbox и не даёт обещания защиты от такой гонки. Усиление потребует платформенных file-handle механизмов и отдельного решения, а не скрытой декларации безопасности.

### 4. Byte limits and token settings are separate

Фиксированные стартовые лимиты: исходный файл <=16 KiB, вопрос <=2000 Unicode code points, сериализованное JSON HTTP body <=24 KiB UTF-8, HTTP response body <=256 KiB. JSON body включает инструкции, numbered source, schema, question и параметры; использовать один раз подготовленные bytes и для проверки размера, и для отправки. Превышение входного лимита прекращает работу до dispatch, без обрезки или summarization. Ответ читать ограниченно, даже при stream:false: транспортное чтение по блокам не является streaming-генерацией.

`options.num_ctx=8192`, `options.num_predict=2048` передаются явно. Это отдельные token settings, не перевод byte caps в токены. Запас окна зависит от tokenizer, template и thinking; точного tokenizer/preflight API здесь нет. Byte caps не доказывают, что модель получила весь контекст: возможная серверная обрезка остаётся явно документированной границей. Для первого live взять небольшой fixture, проверить начало/конец и ссылки, наблюдать actual prompt_eval_count; не объявлять счётчик доказательством отсутствия обрезки. tiktoken от OpenAI не использовать для оценки Qwen.

### 5. Loopback transport and server-local inference

Принимать только `http` и literal loopback IP (127.0.0.0/8 или ::1), а также имя `localhost`, которое нормализуется в 127.0.0.1 до HTTP без DNS. Порт 1–65535, без userinfo/query/fragment и без path кроме пустого или `/`. Remote hostname/IP, HTTPS cloud endpoint, UNC URL и cloud-model suffix отвергать до dispatch. Список cloud suffix не считается доказательством локальности произвольного alias.

httpx: trust_env=False, follow_redirects=False, connect timeout 5 s, read/write timeout 180 s, retries=0. Metadata POST `/api/show`, затем один POST `/api/chat` с model, system/user messages, format schema, stream:false, options и think:false при поддержке. Для show разрешён bounded metadata response до 2 MiB, для chat сохраняется 256 KiB. Remote model metadata блокирует generation. Все ограничения URL/proxy/redirect/timeouts действуют на оба endpoint. 3xx является ошибкой, не следующим запросом. Timeout относится к ожиданию операций HTTP; это не обещание жёсткого общего wall-clock deadline или отмены вычислений Ollama. Код клиента не запускает pull, web search, provider fallback или subprocess модели.

Обязательное условие эксплуатации: Ollama настроена local-only (`OLLAMA_NO_CLOUD=1` либо disable_ollama_cloud) и использует установленную локальную модель. Перед live это проверяется на сервере без генерации; CLI не выводит ложное утверждение, что проверил настройки отдельного процесса. Loopback может быть прокси, поэтому контролируемая локальная Ollama — часть предпосылок. Журналирование полных запросов на сервере не включать. Приложение не меняет настройки Ollama автоматически.

### 6. A small explanation contract with line references

Ollama format получает JSON Schema без дополнительных keys:

```json
{
  "facts": [{"text": "Наблюдение по коду", "lines": [3, 8]}],
  "assumptions": ["Возможная интерпретация"],
  "limitations": ["Реализация зависимости не предоставлена"]
}
```

Все три поля обязательны; значения текста непустые. Каждый fact требует непустой список уникальных integer line numbers в диапазоне 1..N (bool не integer для валидации). Это маленькая механическая проверка обычным Python/json, без Pydantic и переноса Day 24 citation framework. Если опоры для facts нет, допустим facts=[] с непустым limitations; полностью пустой объект объяснения непригоден. Не чинить ссылки/JSON и не запрашивать repair.

System instruction просит объяснить назначение, видимые зависимости и взаимодействия; не считать import доказательством вызова, не придумывать callers или внутреннее поведение зависимости. Исходник, комментарии и строковые литералы — данные, не команды. Render отдельно показывает три раздела, включая «нет» для пустого списка. Ссылки механически допустимы, но истинность и смысловая поддержка оцениваются человеком. Текст модели не выполняется и не интерпретируется как terminal control sequences.

Сначала проверить HTTP status/body/error, затем done=true и done_reason=stop, затем непустой message.content и его schema. done_reason=length, done=false, отсутствующий/неизвестный terminal reason, пустой content при наличии thinking или невалидный JSON не считаются успехом, даже если часть текста выглядит полезной. Не печатать partial answer как нормальное объяснение. Неизвестная причина даёт unsupported completion error, не выдуманное объяснение причины сбоя.

### 7. No content persistence and a small validation record

Нет file logging, transcript, cache, history или auto-report. Ошибки отображаются по безопасным собственным кодам/сообщениям, без raw exception/provider body/исходника/вопроса и без traceback по умолчанию. CLI question может остаться в истории shell; интерактивный ввод позволяет избежать аргумента с вопросом. Управление shell history и серверными логами не выдаётся за функцию приложения.

В терминале показывать wall elapsed time, requested model/settings, status/done_reason и предоставленные Ollama prompt_eval_count/eval_count/total_duration/load_duration; отсутствующие счётчики — unavailable, не 0. Счётчики не вычисляются из bytes; reported eval_count не выдаётся за число токенов только видимого ответа. Метрики не содержат prompt, absolute path или ответ. Runtime ничего автоматически не сохраняет.

Для одного live reviewer вручную переносит только значения метрик и краткие наблюдения в Day README; детали необходимости — в OpenSpec verification notes без transcript. Синтетический fixture с известными видимыми вызовами и отсутствующей реализацией зависимости хранится в tests. Пользовательские checkout рекомендуются вне репозитория; для домашнего synthetic scratch уже игнорируется `.local/`. Утилита ничего туда не копирует. README содержит предупреждение не помещать private checkout в обычную отслеживаемую папку.

### 8. Focused verification, then one observed live attempt

Offline: pytest + temporary directories + MockTransport; path traversal/symlink/junction/encoding/limits, interactive input, prompt isolation, HTTP settings, all failure branches, line validation, metadata and no content persistence. OS-specific tests выполнять на соответствующей ОС; отсутствие прав на создание symlink отмечать явным skip, не PASS. На Windows отдельно проверить junction. Проверка CLI import/syntax не должна запускать provider. Не нужны backend, Gradle или Android.

После offline проверить версию/наличие модели и local-only server configuration без generation; выполнить один synthetic explain на Windows (Ollama 0.40.2, qwen3.5:9b-q4_K_M, 8192/2048). Reviewer сопоставляет facts/lines и assumptions/limitations с fixture; механический PASS не заменяет human verdict. Наблюдения отмечаются как один run. При API failure/обрыве/ошибке смысла сохранить безопасные метрики и честный результат; не повторять ради улучшения. Новый live run возможен только как отдельно согласованная проверка. macOS smoke остаётся явно непроведённым, пока нет доступа к машине.

## Risks / Trade-offs

- [Один файл не показывает архитектуру целиком] -> явные limitations, отсутствие автоматических догадок о соседних классах.
- [8192 и модель 9B могут быть медленными или не поместиться в доступную память] -> один измеренный Windows run, ограниченный fixture; без обещания пригодности M1 и без тихого downgrade до 4096.
- [Server может обрезать input; совместимость thinking зависит от модели] -> think:false после capability discovery, явные budgets, строгая проверка completion и документирование границ; сравнение режимов Day 29.
- [Корректный номер строки не доказывает утверждение] -> ручная оценка, отсутствие label «проверенный факт» только по schema.
- [Path races и loopback proxy выходят за обычную проверку CLI] -> контролируемый checkout/сервер как явные предпосылки; никаких абсолютных sandbox/offline гарантий.
- [Строгие schema/stop checks отвергнут ответ другой модели] -> понятная ошибка без repair; модель настраивается, но совместимость проверяется, не предполагается.

## Migration Plan

При apply добавить только каталог Day 27 и ссылку README; установить отдельные зависимости. Данных и API для миграции нет. Отказ от утилиты не затрагивает прежние дни и пользовательские checkout. Proposal не создаёт runtime-файлы и не запускает live.

## Open Questions

- Windows latency/token counts и semantic quality установлены единственным run с think:false; см. [verification.md](verification.md). Пользователь подтвердил частичную полезность и замечания; это не обещание качества других запросов.
- Доступная память и время на корпоративном Mac M1 пока неизвестны; переносимость реализации не объявляется измеренной производительностью.

Справочные контракты: [Ollama chat API](https://docs.ollama.com/api/chat), [local-only mode](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features), [context length](https://docs.ollama.com/context-length).
