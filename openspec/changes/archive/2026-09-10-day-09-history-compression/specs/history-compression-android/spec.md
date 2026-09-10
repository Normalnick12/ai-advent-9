## Purpose

Определяет лёгкую Android-лабораторию Day 09 с отдельными chat/details экранами, прозрачными измерениями compression и стоимости и явным сравнением сохранения фактов без управления историей со стороны клиента.

## ADDED Requirements

### Requirement: Compression chat has a compact main screen

Day 09 SHALL показывать обычный chat, compact context card, кнопку «Статистика и сравнение» и composer. Card SHALL показывать compression enabled, summarized messages, fixed raw-tail limit 4 и actual raw-tail count, FULL/COMPRESSED input и signed delta percent. Все числовые поля card SHALL относиться к одному immutable pre-turn snapshot и иметь подпись «Контекст последнего запроса»; после cold start без measurements SHALL показываться «ещё не измерено», а не вычисление из bubbles. Full summary text, длинные diagnostics и таблицы SHALL NOT размещаться под chat на main screen. Synthetic summary SHALL NOT отображаться bubble.

Для positive token_delta UI SHALL показывать «Экономия: N токенов (X%)», для negative — «Дополнительный расход: N токенов (+X%)», для zero — «Без изменения». Unknown SHALL отличаться от zero. Draft и fixed N SHALL NOT становиться model tuning controls; ordinary Send SHALL делать только normal compressed turn, без hidden compare.

#### Scenario: Signed delta is honestly labeled
- **WHEN** backend вернул full=100 и compressed=120
- **THEN** card показывает «Дополнительный расход: 20 токенов (+20%)», а не экономию и не ноль

#### Scenario: Main stays compact after multiple turns
- **WHEN** chat накопил messages, summary и operation observations
- **THEN** main содержит bubbles/composer и compact card, а большие metrics и summary доступны через details

### Requirement: Details separates context, overhead and comparison

Вложенный экран «Статистика и сравнение» SHALL показывать FULL/COMPRESSED exact counts, delta/percent, standalone summary size и её measurement meaning, boundary/count/tail, latest и observed-current-run summary usage/cost, response usage, runtime totals и отдельный compare-preparation overhead. Current durable summary SHALL раскрываться явно; summary использованная в compare SHALL иметь отдельные label/boundary и не подменять durable text. Read-only открытие/раскрытие SHALL NOT выполнять count/summarization/generation.

Details SHALL предоставлять comparison question и явное действие сравнения с пояснением двух response calls и возможного дополнительного summary call. FULL/COMPRESSED replies SHALL отображаться вместе с независимыми status/usage/cost и exact-fact N/3 либо reason unavailable/not applicable. На узком экране results SHALL идти вертикально, side-by-side SHALL использоваться только при достаточной ширине. Result SHALL быть привязан к своему question/snapshot; после normal commit SHALL помечаться относящимся к предыдущему snapshot, без автоматического rerun. Changing compare draft SHALL NOT переименовывать уже полученный result под новый question.

#### Scenario: Local compare summary is not presented as persisted
- **WHEN** compare использовал local catch-up с boundary 3 при durable boundary 1
- **THEN** details отдельно показывает обе summary и compare-preparation cost, а возврат на main не меняет durable metadata

#### Scenario: Partial failure keeps the successful answer
- **WHEN** FULL failed, а COMPRESSED completed
- **THEN** COMPRESSED reply и её metrics остаются видны, FULL показывает ошибку без fake score 0/3

### Requirement: Runtime observations belong only to the current Android process

Единое состояние Day 09 SHALL хранить operation observations и cumulative known totals в памяти текущего Android process, с dedup по attempt_id. Backend SHALL возвращать только operation metrics; runtime_id/backend accounting и persistent billing journal SHALL отсутствовать. Navigation и Activity recreation SHALL сохранять эти observations, а process death SHALL очищать их. Totals SHALL называться измерениями, полученными в текущем запуске приложения, а не lifetime billing session; они SHALL разделять maintenance summary, normal responses и diagnostic compare (catch-up и обе responses). Известная сумма SHALL сопровождаться unknown/partial coverage, если есть attempted phases без usage/cost или потерянные HTTP responses. Пропуск phase SHALL отличаться от неизвестной стоимости.

Если список observations ограничен последними записями, cumulative totals SHALL сохранять вклад всех наблюдённых операций текущего запуска, а не только видимых строк. Повторный read/переход SHALL NOT повторно добавлять observation. Backend restart сам по себе SHALL NOT обнулять уже полученные Android measurements; новая невидимая операция SHALL NOT выдумываться. Reset завершает показанный experiment и очищает его observations вместе с Day 09 UI state. Тексты break-even SHALL обозначать theoretical estimate с uncached assumption и не обещать фактическую экономию счёта.

#### Scenario: Rotation does not double-count usage
- **WHEN** после response пользователь открывает details, поворачивает устройство и возвращается
- **THEN** одна operation учтена один раз, суммы и draft/results сохранены без provider request

#### Scenario: Process death clears only UI measurements
- **WHEN** Android process завершён и приложение открыто заново
- **THEN** runtime observations/bubbles отсутствуют, а собственный ID восстанавливает backend identity/count/summary metadata без платных calls
- **AND** UI не показывает нулевую lifetime стоимость и не считает restored conversation новым пустым диалогом

### Requirement: Day 09 identity and operation state are isolated

Day 09 SHALL иметь отдельный saved session ID с config namespace, независимый от Day 06–08. ID SHALL сохраняться до первого send. Без ID только явный Send SHALL создавать session; compare SHALL требовать существующую session. Restore SHALL получать metadata read-only, не создавать замену и не выполнять replay. Busy SHALL запрещать повторную отправку/compare/reset, но не навигацию. Operation state SHALL явно различать restoring, sending, comparing и resetting без утверждения о точной server phase, если transport её ещё не сообщил.

При unknown normal send outcome UI SHALL сохранять draft и требовать явного восстановления безопасного состояния/нового диалога по существующему принципу без автоматического resend. Unknown compare SHALL сохранять conversation identity, помечать measurement неизвестным и разрешать только явный read-only refresh перед новым платным действием. Read-only refresh SHALL NOT повторять compare. Успешный DELETE SHALL очищать ID/UI без немедленного create; reset failure SHALL NOT изображаться успехом. Отдельный конечный Day 09 HTTP budget SHALL быть больше согласованного backend deadline без изменения старых clients и без retries.

#### Scenario: Unknown compare never mutates or replays history
- **WHEN** connection потеряна во время compare
- **THEN** UI показывает неизвестный результат/расход, не добавляет bubbles и не повторяет запрос; read-only refresh проверяет доступность session

#### Scenario: Reset is isolated
- **WHEN** пользователь успешно сбрасывает Day 09
- **THEN** только Day 09 ID, draft, results и observations очищаются; Day 06–08 state не меняется и новая session пока не создаётся

### Requirement: Visible scenario messages require explicit sends

Day 09 SHALL предоставлять видимые учебные drafts для четырёх turns scenario ORBIT-7319/37/Мира и контрольного question. Вставка fixture SHALL только менять draft без отправки и без добавления synthetic history/assistant replies. Пользователь SHALL видеть содержимое, иметь возможность прочитать длинный текст и явно отправлять каждое сообщение. Scenario action SHALL применять scored compare только для пригодного backend-validated snapshot; при contamination SHALL объяснять необходимость чистого прогона и не обещать summary retention. Manual changes SHALL NOT приводить к ложной стандартной оценке.

#### Scenario: Fixture insertion is not a model call
- **WHEN** пользователь выбирает следующий учебный текст
- **THEN** текст виден в draft, ни session create, ни send, ни synthetic exchange не выполняются

#### Scenario: Contaminated tail has no misleading score
- **WHEN** backend возвращает scenario_not_applicable из-за раннего значения в recent raw tail
- **THEN** details сообщает причину и предлагает чистый прогон либо отдельный обычный compare без factual score

### Requirement: Nested navigation preserves the experiment

Toolbar и system Back при закрытой клавиатуре SHALL вести Details → Chat → каталог Days. Chat и Details SHALL разделять одно состояние Day 09 и сохранять собственные scroll positions, draft, current operation, results и раскрытые неизменившиеся blocks при переходах/rotation. Navigation SHALL NOT отменять, повторять или автоматически запускать generation/compare/summary, удалять session или смешивать её с другим Day. Возврат с текущей operation SHALL показывать актуальное состояние той же попытки.

#### Scenario: Both back actions traverse the nested screen
- **WHEN** пользователь нажимает toolbar Back либо system Back на Details, затем на Chat
- **THEN** сначала видит прежний Chat, затем каталог без повторных network calls и потери Day 09 state
