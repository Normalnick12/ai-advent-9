## 1. Corpus and token baseline

- [x] 1.1 Добавить изолированный модуль, tiktoken в backend environment и manifest с 22 путями/source_type и четырьмя locations из design; реализовать corpus loader/snapshot и CLI corpus. Проверить inventory, отсутствие secrets/runtime paths, корректность manifest и один hash/snapshot для обеих стратегий; encoding инициализировать штатно, без cache machinery.
- [x] 1.2 Реализовать небольшой token-window helper на source character offsets с actual count <=500, approximate overlap <=50 и fixed-size strategy; добавить metadata/IDs. На mixed-language fixture проверить exact substring, Unicode, продвижение, coverage, отсутствие пустых chunks и стабильность IDs/metadata.

## 2. Structure-aware and visible preview

- [x] 2.1 Реализовать Markdown headings/sections с учётом fences и общим oversized token fallback; небольшим fixture проверить реальные headings, сохранение текста и <=500 tokens.
- [x] 2.2 Реализовать Python AST boundaries с decorators, методами, сохранением imports/comments/gaps и общим fallback; небольшим fixture проверить source coverage и вложенную функцию внутри родителя.
- [x] 2.3 Реализовать Kotlin file/formatting blocks без parser и declaration regex; fixture должен подтвердить честные labels, сохранение текста и oversized fallback с тем же token limit.
- [x] 2.4 Добавить preview на заранее закреплённых locations: исходный участок с номерами строк → полный текст пересекающих chunks fixed-size → chunks structure-aware с metadata. Проверить все четыре примера на реальном corpus без OpenAI/API key; показать также случаи без преимущества одной стратегии, если они получились.

## 3. Embeddings and persistent index

- [x] 3.1 Добавить отдельный Embedder и OpenAI adapter (text-embedding-3-small, 1536), exact chunk inputs, batching и базовые count/dimension checks. Проверить fake adapter без API, правильную связь text/vector и отказ при неверном количестве/размерности.
- [x] 3.2 Добавить build --strategy both: один snapshot/config, embeddings обеих стратегий в памяти, затем одна SQLite transaction в игнорируемом Day 21 каталоге. Проверить real SQLite round-trip/reopen и что ошибка provider/записи не создаёт готового неполного run; не добавлять per-strategy publication/resume.
- [x] 3.3 Добавить compare/inspect из сохранённой базы: chunk count, min/median/max tokens, total embedded tokens, fallback count и те же representative examples, metadata/vector preview. Проверить keyless reopen без повторных calls; timing/usage/calls/размер базы выводить отдельно как наблюдения run. Расширенные метрики не являются частью этой задачи.

## 4. Documentation and end-to-end demonstration

- [x] 4.1 Создать краткий Day README и root README link по порядку дней; setup и CLI команды описать в backend/scripts README. Проверить ссылки/help, явно указать передачу текста OpenAI и отсутствие live результатов до запуска; cache framework и новые сервисы не добавлять.
- [x] 4.2 Выполнить компактный scoped offline suite и syntax checks, пройти corpus → preview → fake integration build → compare/inspect. Проверить ключевые invariants и git diff/status без расширения до exhaustive edge cases; fake не представлять live результатом, Android проверки не нужны.
- [x] 4.3 Выполнить авторизованный live build обеих стратегий и reopen/inspect новым процессом; по фактическим результатам обновить Day README с исходным corpus hash и заранее выбранными примерами. Проверить наличие настоящих vectors/metadata и отсутствие retrieval/performance superiority claims; если live не авторизован или недоступен, оставить задачу открытой с ясным статусом, без выдуманного результата.
