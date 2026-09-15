## Context

Мотивация описана в [proposal.md](proposal.md). Explore и последующие уточнения утверждены пользователем. Design нужен из-за нового durable state, composition нескольких подсистем и Android/backend contracts.

Точки опоры в текущем коде:

- `backend/app/agent.py`: `run_turn()` получает policy/config, блокирует session и сохраняет completed пригодную pair; `generate()` не получает session/store и не имеет commit path. Существующие ветки Day 09/10 не расширяем.
- `context_policy.py`: `prepare(session_id, confirmed_history)` подготавливает history; `ConversationMessage` поддерживает user/assistant. Profile не следует превращать в synthetic user memory block.
- `memory_context.py`: deterministic Working architecture override, маркированные data blocks и snapshot-checking policy находятся рядом с A–E fixtures/verifier.
- `memory_store.py`: один demo owner, независимые owner/task/session IDs, exact schema v11, durable memory binding, snapshot hash. Проверка exact таблиц не допускает простое добавление Profile tables в существующую базу.
- `agent_sessions.py` / `sqlite_conversation_store.py`: atomic pair commit и восстановление подтверждённой истории. `main.py` разделяет namespaces и управляет ресурсами.
- Android: `AppContainer` + Retrofit, screen-level ViewModel, явная enum navigation, Day 11 read/reconciliation без replay. Старый ChatViewModel ориентирован на session-only lifecycle и не становится runtime нового дня.

## Goals / Non-Goals

**Goals:**

- Profile domain без experiment/provider/storage-layout зависимостей; deterministic persistence и selection, pure instructions projection.
- Один и тот же путь подготовки Profile для ordinary Send и controlled probes; наблюдаемость фактической границы LlmClient.
- Сохранение независимых memory lifecycle и old namespace contracts; ровно один generation на explicit Send/probe.
- Конкретные поддерживаемые UI fields и ограниченные checks вместо произвольного prompt editor или общего оценщика.

**Non-Goals:**

- Список исключений в proposal обязателен. В частности, здесь нет нового AgentRuntime, universal PromptBuilder, State/Invariants, validation/retry loop, смены providers или migration старых Days.
- Нет profile deletion, automatic selection при create, multi-user authentication, multi-worker concurrency или долговременного журнала experiment results.
- Нет изменения `SimpleAgent.run_turn()` ради будущей validation-before-commit.

## Decisions

### 1. Profile is behavioral state, separate from remembered facts

Profile хранит явно заданные предпочтения взаимодействия. Long-term сохраняет сведения владельца, включая существующее `preferred_architecture`; Working `current_architecture` остаётся текущим решением задачи. Эти поля не переносятся в Profile. Domain operations не зависят от того, находятся данные в одном или разных файлах.

`owner_id` Profile соответствует `memory_owner_id` композиции Day 12. Profile ID независим от owner/task/session IDs. Domain API принимает owner ID и проверяет принадлежность, но не импортирует MemoryStore и не принимает database paths. Альтернатива "вложить профиль в Long-term" отклонена: durable lifetime не определяет семантику.

### 2. Minimal concrete profile schema

Все входы strict, extra fields запрещены, никаких неявных string/int/bool coercions. Полная typed запись создаётся/редактируется через форму:

| Поле | Контракт |
| --- | --- |
| `profile_id` | Server-generated canonical UUID, immutable |
| `owner_id` | Canonical UUID владельца, immutable |
| `name` | Строка 1–80 символов после trim, не пустая; только metadata, уникальность не обязательна |
| `revision` | Integer >= 0, задаётся backend, increment только при действительном edit |
| `language` | `ru` или `en`; A/B используют `ru` |
| `tone` | `technical` или `explanatory` |
| `verbosity` | `concise` или `detailed` |
| `response_format` | Discriminated union, описанная ниже |
| `constraints` | Объект из трёх обязательных boolean flags |

Форматы:

- `{kind: summary_bullets, max_bullets: N}`, N — integer 1–5. Инструкция: heading `## Вывод` / `## Summary`, непустой краткий вывод и от нуля до N bullet items. Нет требования искусственно заполнять N пунктов.
- `{kind: teaching_sections}` без `max_bullets`. Фиксированные H2: `Идея`, `Почему`, `Пример`, `Ограничения` для ru; `Idea`, `Why`, `Example`, `Limitations` для en. Порядок фиксирован, содержание свободное. Поле произвольных headings отсутствует.

Constraints: `no_emoji`, `skip_basic_explanations`, `explain_unfamiliar_terms`. False означает отсутствие дополнительной инструкции, а не требование противоположного поведения. Два последних flags совместимы. Для текущего поддерживаемого поведения `skip_basic_explanations` означает "не пересказывать базовые Android/Kotlin концепции", а `explain_unfamiliar_terms` — "пояснять вводимые специальные термины за пределами этой базовой подготовки". Это явная семантика flag, не поведение из имени Profile. Универсальную taxonomy expertise/domain сейчас не вводим. При расширении областей позже контракт constraints можно расширить осознанно.

Name/IDs/revisions не входят в renderer. Две записи с одинаковыми behavioral fields, но разными metadata дают одинаковые instructions. Разрешённые комбинации не ограничиваются двумя fixtures. Model/settings/purpose/domain/system_prompt/skills/tools не входят в schema.

### 3. One storage contract and durable binding

`ProfileStore` задаёт create(owner, typed_fields), read/list(owner), edit(owner, profile_id, expected_revision, typed_fields), read_binding(owner), select(owner, profile_id, expected_profile_revision, expected_binding_revision). Он возвращает immutable profile/binding snapshots. SQLite implementation и tests реализуют тот же контракт; отдельные Repository/Provider/Manager без собственной обязанности не добавляются.

`ActiveProfileBinding`: owner_id, nullable active_profile_id, revision >= 0. Отсутствующий binding читается как unselected, без writes; первое explicit select создаёт binding с revision 1 при expected revision 0. Новый profile начинается с revision 0; create не меняет selection. No-op edit/select сохраняют revision, но сначала проверяют expected revisions. Rename увеличивает profile revision как metadata edit, instructions остаются одинаковыми. Edit active Profile не меняет binding revision, но следующий request использует новую profile revision. Select не редактирует profile record.

Profile storage имеет собственный schema version, records и binding с owner-consistent ссылкой. Profile data и revision обновляются атомарно, failed/stale/foreign-owner операции не имеют частичных эффектов. Missing/unselected различается с corruption; corruption не исправляется молча. Все SQL statements параметризованы. Один локальный owner в UI не отменяет isolated-owner tests domain contract.

Конкретный layout Day 12: отдельные локальные `memory.sqlite3` и `profiles.sqlite3` в Day 12 namespace; существующие базы не трогаются. MemoryStore используется с прежней memory schema. Paths выбирает composition root. Это выбранный adapter layout, не ограничение Profile API и не требование будущего integration storage.

Initialize создаёт отсутствующий Memory owner/task/session через существующую идемпотентную операцию. Profiles создаются отдельными явными operations. Отсутствие profiles/selection показывается как состояние подготовки; generation запрещена до выбора. Нет обещания all-or-nothing между двумя SQLite-файлами и нет distributed transaction. Частично завершённая подготовка перечитывается; existing memory не сбрасывается. Удаление owner вне scope.

### 4. Composition and actual request capture

Выделить существующие `selected_memory`, `MemoryContextPolicy`, memory block assembly в нейтральный модуль, если это нужно для импорта без A–E harness; сохранить точные Day 11 payload/order/selection. Не обобщать пять текущих memory keys и не переписывать MemoryStore.

`ProfileInstructionsBuilder` — pure abstraction: validated Profile behavioral fields -> deterministic text. Нейтральная fixed база описывает использование memory как данных, границы текущей задачи и отсутствие выдуманных фактов; не фиксирует language/tone/verbosity/format. Результат renderer добавляется к базе через новую immutable `AgentConfig`, без изменения global configs. Fixed sections/messages не включают name или сериализованный Profile целиком. Это constrained projection typed state, не произвольные инструкции пользователя.

```text
query + expected snapshot references
                  |
          owner operation guard
                  |
       +----------+-----------+
       |                      |
   Memory read           Profile + binding read
       |                      |
   selected sources      typed instructions
       |                      |
   ContextPolicy         effective AgentConfig
       +----------+-----------+
                  |
          SimpleAgent instance
            /             \
       run_turn         generate
       ordinary          A/B probe
            \             /
          captured LlmClient boundary
                  |
          existing provider adapter
```

Application service разрешает active Profile на каждый dispatch. Создание небольшого SimpleAgent wrapper на запрос сохраняет общий lifecycle, не является новым agent stack. Ordinary path передаёт memory policy в `run_turn`; probe использует те же policy messages + тот же query и `generate`, без `probe()` из overflow lab (у него другой контракт).

Для inspector использовать request-scoped capturing LlmClient decorator: перед forwarding фиксирует messages/config ровно из аргументов complete и сохраняет immutable receipt вместе с profile/memory source snapshots. Не регистрирует headers/secrets и не делает второй call. Recording-client tests сверяют receipt и то, что увидел delegate. Preview может быть полезен до dispatch, но не выдаётся за actual request. Profile core не импортирует capture/harness.

Receipt: attempt_id, mode (send/probe/seed), optional comparison_id/slot, memory_snapshot_id и owner/task/session, selected/excluded source manifest, profile snapshot + profile revision, binding revision, base/template version, rendered profile instructions, actual instructions/messages/config, outcome/raw available reply и отдельные checks. Name показывается только в metadata. Неизвестные provider values не заменяются выдуманными. Низкоуровневый OpenAI payload не является основным domain observation.

### 5. Consistent snapshots and lifecycle

Day 12 application service использует один owner operation guard для memory writes/lifecycle, profile create/edit/select, freeze, seed, Send и probe. Локальный scope: один event-loop worker, без обходных write paths к этим store instances. Все проверки и capture до первого provider await; guard действует до окончания операции, SQL transaction — только во время коротких storage operations. ProfileStore сам по себе не удерживает network operation lock.

Dispatch содержит ожидаемые memory snapshot ID, profile ID/revision и binding revision. Backend заново разрешает authoritative current state и сравнивает references; клиент не задаёт произвольный provider profile override. Stale/foreign/unselected/incompatible snapshot отклоняется до effects/provider call. Один и тот же профиль с новой revision после edit не считается прежним snapshot. Потерянный HTTP outcome ведёт к read/reconciliation, не к automatic replay.

| Action | Profile | Memory |
| --- | --- | --- |
| New Conversation | Records/binding/revisions прежние | Новая session, прежняя history inactive; task/Working/Long прежние |
| New Task | Прежний Profile | Новые task/session, старые retained inactive; owner/Long прежние |
| Select other Profile | Только active binding + его revision | Все IDs, три слоя и memory snapshot/revision прежние |
| Edit Profile | Только запись/revision | Все memory state прежнее |
| Clear Long-term | Profile/binding прежние | Только active Long-term очищается |
| Restart | Records/binding восстановлены | Identities, history, Working/Long восстановлены |

Old transcript не переписывается при switch. Instructions не являются confirmed messages. Ответ завершившейся попытки показывается с использованной revision, даже если позже state изменился.

### 6. Controlled A/B setup and freeze

Фиксированная Day 12 configuration: `gpt-4o-mini`, reasoning_effort=None, service_tier=default, truncation=disabled, max_output_tokens=2000, text_format=None, version=day12-v1. Это server experiment configuration, не Profile. Общий budget одинаков для A/B, увеличен относительно Day 11, чтобы подробный Mentor не обрезался искусственно. Поддержка provider проверяется live; silent fallback запрещён.

Fixtures создаются через обычный create, имеют те же права edit/select, что остальные profiles:

| Field | Compact Engineer | Mentor |
| --- | --- | --- |
| language | ru | ru |
| tone | technical | explanatory |
| verbosity | concise | detailed |
| format | summary_bullets, max_bullets=3 | teaching_sections |
| no_emoji | true | true |
| skip_basic_explanations | true | false |
| explain_unfamiliar_terms | false | true |

Кнопки "Создать из шаблона" предзаполняют тот же editor и сохраняют через тот же create. Нет startup seeding, поиска особого поведения по name, скрытого overwrite пользовательских edits. Runtime setup запоминает выбранные A/B IDs; при freeze проверяет behavioral fields fixtures, а не name. Для controlled A/B пользователь явно назначает записи слотам A/B; custom profiles доступны обычному Send. Edit fixture делает прежнее сравнение stale, не восстанавливает значения автоматически.

Подготовка без большого stepper:

1. Explicit Initialize memory, создание/назначение A/B и select A.
2. На пустой active Memory выполнить один настоящий seed Send: `Готов продолжить. Подтверди получение сообщения.` Он проходит тот же Profile assembly и normal run_turn. Инструкция просит подтверждение без domain explanation; Compact настроен на краткий ответ. Не применяется отдельная generation configuration или скрытый seed profile.
3. Показать raw completed seed response. Предпочтителен короткий нейтральный acknowledgment без обучения/советов; модель может сохранить оформление Compact. Нейтральность — human observation, не гарантия. Нельзя подменять, обрезать или синтезировать assistant turn. Если он сильно стилизован, пользователь может явно начать новую conversation при подходящей подготовке и повторить, без automatic retry. Это фиксируемое ограничение style bleed.
4. Явно записать настоящие LONG `project_code=ORION-17`, `preferred_architecture=MVVM`; WORKING `task=Checkout`, `current_architecture=MVI`, `release_marker=RC-42`. Действия показывают конкретные записи; prepared existing data не перезаписываются скрыто.
5. Explicit Freeze фиксирует immutable memory/transcript, A/B profile revisions, общий query/config и новый runtime comparison_id. Preconditions: exact memory values и ровно одна real completed seed pair; user видит seed и принимает его для сравнения. Повторный Freeze явен, создаёт новый comparison, не превращает старые результаты в новые.

Fixed query: `Как организовать обработку loading/error/success для текущего экрана? Учти текущую задачу и выбранную архитектуру, назови проект и релиз.` Exact memory values не подставляются в query/base/profile templates.

Каждая probe требует explicit activation соответствующего A/B profile и current memory equality frozen snapshot. A и B используют идентичные memory messages/transcript/query и non-profile config. Binding revision различается из-за explicit switch; это observation metadata, не model input. Profile ID/revision также не передаются как инструкции. Только profile-derived instructions различаются на model boundary. Working MVI исключает stored MVVM из selected Long-term.

Обе probes side-effect-free и не редактируют Profile/binding. Предыдущий response/observations/oracle не становится input B. Повторные probes только explicit, каждый attempt имеет ID; live failures не скрываются удачными retries. Runtime results имеют comparison_id и versions; сравнивать разные freeze snapshots как controlled pair запрещено. После memory mutation или ordinary Send старый checkpoint остаётся historical и не dispatchable; после restart требуется explicit Freeze, не новый seed при уже подходящем durable state.

### 7. Ordinary Send is a separate demonstration

Минимальный composer использует active Profile и current Memory автоматически через normal `run_turn`, сохраняет только completed пригодную user/assistant pair. Например после сравнения спросить "Какой следующий шаг реализации?" без стилевых указаний, затем явно switch и задать следующий обычный вопрос. Captured requests показывают актуальные profile revisions. Это проверка автоматического применения, не strict A/B: история уже меняется. Нарушение profile format не меняет completed в provider/storage failure и не предотвращает обычный commit; Day 12 verifier observational.

### 8. Narrow verification with separate human observations

Четыре независимые группы: selection, assembly, deterministic output checks, human observations. Нет aggregate personalization score и LLM judge.

- Selection: owner, profile ID/revision, binding revision совпадают с принятой попыткой и frozen slot при A/B.
- Assembly: exact rendered instructions, actual config/messages, memory/query equality, absence of previous-profile assembly fragments, metadata-only rename, отсутствие synthetic instructions в transcript. Shared clauses между профилями не считаются утечкой; проверяется exact сборка выбранного профиля, не substring-запрет всех слов прежнего.
- Summary: точный H2 summary heading и непустое содержимое, число Markdown list items <= max_bullets. Считаются bullet и ordered markers вне fenced code (включая вложенные items), чтобы numbered list не обходил лимит.
- Teaching: ровно четыре ожидаемых H2 вне fenced code в заданном порядке, каждая секция непустая (code example считается содержимым); содержательность не оценивается автоматически.
- No emoji: deterministic проверка всего raw response, включая code, по небольшому явному документированному набору Unicode code points/простых sequences, достаточному для Day 12 fixtures. Покрытие и положительные/отрицательные примеры фиксируются в tests; обычные цифры и non-emoji text не должны срабатывать. Успех означает отсутствие символов объявленного набора, не полное отсутствие всех Unicode emoji. Не строить полноценный Unicode Emoji compliance engine, не требовать исчерпывающей поддержки flags/keycaps/ZWJ/variation selectors и не добавлять тяжёлую dependency ради проверки.
- Memory markers: literal occurrence ORION-17 / RC-42 / Checkout / MVI в raw response, с узкой подписью "упоминание маркера". Это не доказательство семантической корректности MVI. Profile constraints и marker diagnostics показываются раздельно.
- Language, tone, полезность, подробность, пропуск базовых объяснений и объяснение новых терминов остаются human observations. Нет кириллического regex как доказательства языка. Human notes — optional plain text на конкретный attempt, runtime-only, без числового рейтинга.

Fenced Markdown parser должен учитывать opening/closing backtick/tilde fences и не считать headings/bullets внутри code. Не строить универсальный Markdown validator: поддерживаемая проверка точно объявлена. Completed format violations показываются как fail конкретных checks; failed/refused/incomplete оставляют selection/assembly доступными после dispatch, output checks unavailable. При отказе до dispatch actual assembly отмечается not_dispatched, не fabricated pass. Available raw outcome сохраняется без реконструкции недоступного текста. Автоматического retry/repair нет.

### 9. Minimal application API and Android composition

Day 12 API prefix: `/api/v1/profile-personalization`. Contract groups:

- read-only current (memory summary/selection, profiles, binding, busy, preparation status), scenario catalog;
- explicit memory initialize/mutations/lifecycle с существующей Day 11 semantics;
- profiles list/read/create/edit/select с typed bodies, revisions и owner validation;
- seed/messages, explicit comparison freeze, probe A/B по comparison_id и expected references.

UI не отправляет history, instructions, provider config или Profile fields в Send вместо selection. Profiles редактируются только отдельным typed endpoint. Runtime checkpoint/results не становятся durable domain state. API input errors safe, strict extra fields запрещены; неизвестный исход mutation/Send обрабатывается read без повторения. Возможное незавершённое setup не выглядит пустой новой памятью.

Android uses existing Retrofit/MVVM/AppContainer и отдельный ViewModel key/destination. Main: active selector, create/edit entry, memory summary, компактная подготовка/Freeze/A/B controls, две result cards и ordinary composer. Editor поддерживает все declared fields, dirty draft не становится active data до подтверждённого save. Формат teaching скрывает и не отправляет max_bullets. Оба explanation flags доступны одновременно. Profile name не используется как уникальный ключ, различение дубликатов возможно кратким ID.

Inspector показывает captured receipt, human notes и историчность результата; не пересобирает request из current state. Full IDs/JSON находятся в inspector, main читается как эксперимент. Lifecycle controls остаются доступны для проверки независимости Profile от Memory. Navigation/rotation сохраняют drafts/observations/scroll, не запускают operations. Cold start читает authoritative backend state; runtime observations могут исчезнуть. Existing Chat UI primitives можно переиспользовать, session-only ChatViewModel/reset contract не переносить.

### 10. Reuse map and future integration constraint

| Reusable | Day12 harness |
| --- | --- |
| AgentProfile, formats/constraints, revisions | A/B fixture definitions and slot assignment |
| ProfileStore + SQLite adapter | Shared seed/query and fixed experiment config |
| ActiveProfileBinding, create/edit/select | Freeze/probe coordinator and comparison dashboard |
| Pure ProfileInstructionsBuilder | Narrow adherence checks and human notes |
| Memory selection/policy, session primitives, LlmClient | Experiment request receipts/capture presentation |
| Profile snapshot resolution/composition pattern | Day 12 endpoints and UI flow |

Profile reusable modules не импортируют harness. Domain contracts не содержат paths, OpenAI payload или placeholders будущих компонентов. Отдельный generalized AgentRequestContext не создаётся; небольшой immutable preparation/receipt с реально используемыми полями допустим.

Будущие Memory/Profile/State/Invariants будут соседними inputs. `run_turn() -> validate` непригоден для validation-before-commit: completed reply уже сохранён. На integration day coordinator сможет использовать существующий `generate`, затем validate/retry, а принятый ответ commit и state transition согласовать отдельно. Атомарность conversation/state пока не реализуется и не обещается. Эти будущие изменения не требуют переписывать Profile API/renderer. Integrated Android Playground логичен после State/Invariants; Web и миграция всех старых labs не нужны.

## Risks / Trade-offs

- [Seed style bleed] -> короткий acknowledgment через настоящий Send, human review до Freeze, одинаковый raw transcript; не обещать полного отсутствия влияния прежнего ответа.
- [Correct input != compliant output] -> раздельные checks и raw outcome, live observations без cherry-picking или требуемого искусственного 100%.
- [Two-file setup partial completion] -> explicit idempotent memory init, отдельные profile operations, readiness gate, no distributed transaction; layout скрыт за adapters.
- [One owner/worker] -> общий guard и contract tests другого owner; не заявлять production auth/concurrency.
- [Renderer is still text sent to a model] -> typed validation и нейтральная база исключают known conflicts, но не дают enforced safety/invariants; semantic adherence остаётся наблюдением.
- [Provider availability and output budget] -> fixed same settings, explicit failure без fallback; incomplete виден, не zero score.
- [Profiles edited during comparison] -> immutable revision references, stale rejection, explicit new Freeze без silent fixture reset.
- [Overengineering] -> один storage contract, pure renderer, ограниченное выделение memory assembly; no future empty fields.
- [Exact checks have limited meaning] -> declared Markdown/Unicode scope, marker labels, human notes отдельно.
- [Future storage/runtime changes] -> layout-independent Profile API; current MemoryStore schema остаётся учебной и может позднее получить другой adapter.

## Migration Plan

1. При apply добавить Profile subsystem и отдельный Day 12 wiring/API/UI, не меняя старые DB files/configurations. Startup открывает stores, не создаёт demo identities/profiles и не вызывает provider.
2. Если переносится memory assembly, сохранить Day 11 payload/selection contracts и проверить затронутые regression tests.
3. Выполнить domain/storage/recording-client и Android scoped tests. Preferred path для build/UI и live setup — PowerShell 7 `scripts/dev.ps1` по `scripts/README.md`; при недоступном `pwsh` или блокировке ExecutionPolicy разрешён существующий fallback: Android — прямые Gradle commands для тех же tasks; backend — `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` из каталога `backend`. Починка PowerShell/tooling не входит в Day 12. Подробности проверок — tasks.md; live calls не выполнять как скрытую часть offline tests.
4. Live acceptance отдельно: neutral seed + frozen A/B, ordinary sends до/после switch, restart/recovery, фактические observations. README не утверждает прохождение live, пока оно не проведено/подтверждено.
5. Rollback отключает Day 12 wiring/card; локальные data files остаются сохранёнными. Не удалять и не мигрировать чужие namespace data.
6. Planning завершается review artifacts; implementation только по отдельному запросу пользователя.
