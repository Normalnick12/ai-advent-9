# context-strategies-android Specification

## Purpose

Определяет scenario-first интерфейс Day 10: независимые strategy runs, явные реальные отправки, наглядное состояние памяти/веток и компактное сравнение сохранённых результатов без скрытых provider calls.

## Requirements

### Requirement: Strategy selection restores three independent experiment states

Day 10 main SHALL показывать `[Окно] [Факты] [Ветки]`, выбирающие независимые runs `window | facts | branches`, без migration. Каждый SHALL иметь собственные run ID, progress, draft/prepared step, latest response, activity/errors и evaluation results. ID и выбранные strategy/branch SHALL сохраняться client-side с config/version identity. Switching SHALL не создавать run, не запускать generation/extraction/count/evaluation и не переносить данные между strategies; read-only restore разрешён. Run SHALL создаваться только перед первой явной отправкой. Результат выполняющейся операции SHALL обновлять только её исходный run/branch, независимо от текущей вкладки.

#### Scenario: A strategy switch does not migrate a conversation
- **WHEN** после трёх Window steps пользователь открывает Facts и возвращается
- **THEN** Facts показывает собственный progress, Window сохраняет свои три steps и latest response; provider calls от switching отсутствуют

#### Scenario: In-flight result belongs to its originating run
- **WHEN** пользователь переключился из Facts во время отправки
- **THEN** её завершение изменяет только Facts state и не подменяет latest response выбранной стратегии

#### Scenario: V3 preferences do not restore historical experiment state
- **WHEN** приложение v3 запускается при сохранённых v1/v2 IDs/outputs/preferences
- **THEN** v3 использует отдельные config-versioned keys, не удаляет v1/v2 records и не подставляет их state/receipts/results; без своего ID новый run создаётся только первым explicit Send
- **AND** callbacks или metadata с чужой config identity не публикуются в v3 state, несовместимость не вызывает migration/reset/replay

### Requirement: The main screen prioritizes state and scenario over transcript

Main SHALL последовательно показывать selector, strategy state card, compact stepper/timeline, latest Agent response и действие открытия dashboard. Полный длинный transcript SHALL не быть центральным обязательным UI. Stepper SHALL показывать `Шаг N из 8`, название, compact facts и полный исходный fixture по явному disclosure. Preparation/insertion и Send SHALL быть отдельными explicit действиями; preparation не вызывает provider. Full text SHALL быть доступен до Send и оставаться доступным после commit. Передаваемый raw text SHALL не меняться из-за presentation cards.

После completed Send шаг SHALL помечаться подтверждённым, latest reply показываться, а переход к следующему prepared step SHALL требовать явного действия. Автоматическая отправка цепочки, synthetic seed и fake assistant SHALL отсутствовать. Free-form composer SHALL отсутствовать на основном пути; если добавлен optional free-form, отклонение SHALL явно отключать controlled benchmark без подмены fixtures.

#### Scenario: Compact presentation sends the entire fixture
- **WHEN** пользователь подготавливает Turn 5, раскрывает original text и нажимает Send
- **THEN** backend получает точный полный fixture из experiment spec, а timeline после commit показывает компактную карточку с доступным raw disclosure

#### Scenario: Next step requires a user action
- **WHEN** response завершён
- **THEN** UI не отправляет и не подготавливает следующий step автоматически, сохраняя explicit Next/prepare action

### Requirement: Window and Facts cards distinguish current state from measurements

Window card SHALL показывать N=6, current active messages, out-of-window count и полосу `old old [u][a][u][a][u][a]` без необходимости раскрывать каждое сообщение. Facts card SHALL показывать active facts count, raw tail limit 6, несколько scoped key-value rows и действие read-only inspector. Cleared records SHALL отображаться отдельно от active values. Обе cards SHALL различать current state, tokens последнего отправленного context и retention перед final evaluation A/B. Unknown/unmeasured SHALL не рисоваться нулевым progress. Никаких count/extraction calls при открытии cards/inspector SHALL не происходить.

#### Scenario: Window advances after a committed pair
- **WHEN** confirmed message count превышает 6
- **THEN** полоса показывает новые active messages и старые out-of-window; подпись поясняет, что audit сохранён, но модели доступно только окно

#### Scenario: Facts correction and cancellation are visible
- **WHEN** подтверждены Turns 5 и 6
- **THEN** inspector показывает actual extracted deadline value и состояние reminders, включая clear; он не подставляет ожидаемые значения вместо actual facts

### Requirement: Branching exposes one checkpoint and two local conversations

После six confirmed shared steps Branching SHALL предлагать explicit «Создать checkpoint». После durable success SHALL отображаться простая topology checkpoint/A/B, prefix count, active branch и local A/B counts. Default selection A после первого checkpoint SHALL быть UI preference, не provider operation. Turn 7 SHALL предлагаться для A, Turn 8 — для B; Send SHALL передавать explicit branch target. Switch SHALL показывать соответствующие local progress/latest replies без mixed transcript. Graph editor, arbitrary branches и отдельный delete branch SHALL отсутствовать. Reset SHALL явно относиться ко всему Branching run.

#### Scenario: Branch B starts from the shared checkpoint
- **WHEN** Turn 7 подтверждён в A и пользователь переключается на B
- **THEN** B показывает тот же shared prefix и собственный пустой local state, без ответа A; switch не вызывает provider

#### Scenario: Checkpoint creation is explicit
- **WHEN** shared Turn 6 завершён
- **THEN** checkpoint не создаётся автоматически; отдельное нажатие создаёт ровно A/B без LLM calls

### Requirement: Evaluation actions are explicit and outside the conversation

После восьми confirmed scenario steps main SHALL показывать два explicit действия «Проверить ТЗ A» и «Проверить ТЗ B» с disclosure их fixed questions. Оба SHALL ссылаться на один final snapshot/revision и сохранять независимые loading/result/error states. Запуск одного SHALL не авторизовать второй; пользователь SHALL иметь возможность запустить второй, пока первый выполняется. Повторный запуск того же running variant SHALL блокироваться. Evaluation SHALL не отображаться как новый scenario step, user bubble или assistant conversation turn. Fact inspector/counts/progress SHALL не меняться от evaluation. Завершение одного SHALL не блокировать просмотр успешного результата при failure другого. Повтор после failure SHALL быть только явным.

#### Scenario: Two explicit evaluations can run independently
- **WHEN** пользователь нажал A, затем B до завершения A
- **THEN** обе проверки имеют independent states одного snapshot, всего два authorized generations; ни один ответ не становится context другого

#### Scenario: Evaluation is not a ninth conversation turn
- **WHEN** обе проверки завершены
- **THEN** progress остаётся 8/8, conversation counts прежние, results показываются как experiment output

### Requirement: Dashboard is a compact read-only comparison

Dashboard SHALL показывать три strategy cards с одинаковым порядком: ТЗ A N/11, ТЗ B M/11, retention A/B, actual response input/output, maintenance input/output, total known tokens с coverage, обязательные strategy-management actions и branch isolation для Branching. Bars/chips/короткие labels SHALL сохранять различие unavailable и zero. Opening/refresh dashboard SHALL не вызывать generation/extraction/count или автоматически завершать недостающие experiments. Pricing dates, model IDs, milliseconds, provider-source labels и длинные traces SHALL отсутствовать на основном dashboard. Persistent billing analytics и generic dashboard framework SHALL не требоваться.

Под cards SHALL быть короткие qualitative descriptions: «Sliding — простая стратегия для локального недавнего контекста», «Facts — удобна для устойчивых требований и договорённостей», «Branching — удобна для независимых альтернатив». Они SHALL не обозначаться objective numeric scores или заранее обещанным ranking.

Финальный comparison SHALL содержать только runs `day10-gpt4o-mini-n6-v3` для всех трёх strategies. Исторические Window success и Facts v1/v2 failures SHALL NOT подставляться в cards или token/action totals v3. Отдельный historical UI SHALL не требоваться; evidence хранится в прежнем namespace и документации. Version filtering SHALL быть read-only и не запускать missing experiments.

#### Scenario: Historical results do not populate the v3 dashboard
- **WHEN** сохранены v1/v2 outputs, а соответствующего v3 result ещё нет
- **THEN** v3 card остаётся unavailable и не использует v1/v2 quality/retention/tokens/actions, provider calls отсутствуют

#### Scenario: Missing results stay visibly missing
- **WHEN** Window evaluation завершена, Facts отсутствует, а Branch B failed
- **THEN** dashboard показывает available результаты отдельно от unavailable, не подставляет нули и не запускает missing calls

#### Scenario: Branch response tokens are counted once
- **WHEN** dashboard показывает Branching totals
- **THEN** обе ветки и evaluations входят в response usage, maintenance равен 0 и branch calls не прибавлены второй раз

### Requirement: Restore reconciles durable progress without automatic replay

Rotation и навигация SHALL сохранять независимые runs, prepared text, scroll/disclosures, activity/results и runtime receipts без повторных запросов. После process death SHALL read-only восстанавливаться сохранённые IDs, выбранная strategy/branch, backend confirmed scenario steps/revision, state и отдельные evaluation outputs. Локальный step integer SHALL не заменять backend confirmation. Потерянные runtime token/action observations SHALL обозначаться неполными/недоступными, не восстанавливаться как нули из пустых списков. Backend restart SHALL не стирать client selection.

При unknown HTTP outcome UI SHALL блокировать blind Send повторного step и читать durable state/revision. Подтверждённый step SHALL не повторяться; отсутствующий SHALL разрешать только новый explicit Send после завершения busy/reconciliation. Неопределённый evaluation outcome SHALL read-only искать output соответствующей попытки; его отсутствие SHALL не запускать новую evaluation. Missing/incompatible/corrupt run SHALL показывать explicit recovery/reset без автоматической замены.

#### Scenario: Response delivery is lost after commit
- **WHEN** Send завершился неизвестным transport outcome, а read вернул confirmed step/revision
- **THEN** UI восстанавливает подтверждённый progress и reply, не отправляя fixture повторно

#### Scenario: Process death loses accounting but preserves experiment output
- **WHEN** приложение перезапущено после сохранения evaluation results
- **THEN** quality/retention доступны из separate output, а полный token total помечен неполным при утрате receipts; никакой paid replay не выполняется

### Requirement: Lab controls remain usable across navigation and device configuration

Main/dashboard/inspectors SHALL сохранять читаемость и доступность на узком экране, landscape и large font без overlap системных панелей. Buttons SHALL иметь понятные Russian labels; длинные fixture values SHALL переноситься/прокручиваться. Back из dashboard/inspector SHALL возвращать к тому же Day 10 main, следующий Back — в каталог, без reset/cancellation/replay. Эти переходы SHALL работать при недоступном backend.

#### Scenario: Rotation preserves preparation and independent evaluations
- **WHEN** Activity пересоздаётся с prepared fixture либо running A/B evaluations
- **THEN** содержимое и состояние сохраняются, callbacks не дублируют Send/evaluation и ответы остаются у правильного run/variant
