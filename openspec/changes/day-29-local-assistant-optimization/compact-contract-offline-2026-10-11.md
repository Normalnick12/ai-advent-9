# Day 29 — compact-evidence-v1: offline checkpoint, 2026-10-11

Подготовлен отдельный opt-in контракт в существующем synthetic driver. Новых обращений к Ollama, preload, inference, downloads или GPU preflight не было. Live S4/S6 — **NOT RUN** до отдельного review. Это эксперимент schema + необходимых инструкций формата, не чистое сравнение одного параметра. Качество и практическая польза **NOT TESTED**, модель не выбрана.

Пользователь принял исторический explain-evidence-v1: S4 technical FAIL (`done_reason=length`, повтор предложения 38 раз, незавершённый JSON), S6 NOT RUN. Дальнейшие prompt-коррекции прекращены. Эти результаты и прежние FAIL/PARTIAL не заменяются. Исторический бюджет остаётся 12/32 load/chat attempts, 205.174 s записанного bounded client wall; новых attempts 0. Mac M1 и Q4/Q8 — NOT TESTED.

## Контракт

Точная JSON Schema — `SCHEMA` в [compact_contract.py](../../../day-29-local-assistant-optimization/compact_contract.py); offline preview driver выводит её вместе с identity. Ниже форма ответа, с поясняющими заполнителями, а не эталонным ответом сценария:

```json
{
  "code_observations": [
    {"text": "Объяснение наблюдаемого поведения", "lines": [1, 2]}
  ],
  "documented_applications": [
    {
      "rule": "Документированное правило",
      "text": "Интерпретация применения правила к указанным строкам",
      "lines": [2],
      "citations": [
        {"chunk_id": "ID из переданного контекста", "quote": "Точная непрерывная цитата"}
      ]
    }
  ],
  "assumptions": [],
  "limitations": ["Недостающие сведения"]
}
```

Все показанные поля обязательны, дополнительные поля запрещены на каждом уровне. `text`, `rule`, `chunk_id`, `quote` — непустые строки; parser также отклоняет whitespace-only. `lines` — непустой массив уникальных integer 1..N, bool не допустим. `citations` — непустой массив точных ссылок. Quote ≤400 символов, должна буквально входить именно в указанный selected chunk; повтор одной пары chunk/quote внутри объекта запрещён. Источник, section и Markdown span renderer берёт из authoritative selected chunks, не из ответа.

`documented_applications: []` допустим и требует непустых `limitations`. При runtime status `not_requested` / `no_candidates` документальные применения запрещены; при `candidates_provided` их релевантность не гарантирована. При отсутствии observations ограничения тоже обязательны. Наличие непустого списка и точных цитат не подтверждает смысловую корректность.

| Обязанность | Исходный extended контракт | compact-evidence-v1 |
|---|---|---|
| Kotlin | Модель выдаёт id, text, lines | Модель выдаёт text, lines |
| Markdown | Отдельные rules с ID и citations | rule и citations в объекте применения |
| Применение | observation_ids / rule_ids связывают списки | text и прямые Kotlin lines рядом с rule/citations |
| Нумерация | ID модели | Python enumerate при отображении |
| Knowledge status | Модель повторяет runtime status | Только runtime после строгой validation |
| Проверка источников | Строки, выбранные chunks, точные quotes | Те же границы, без перекрёстных model IDs |

Валидатор принимает только `done=true`, `done_reason=stop` и полный JSON указанного формата. Даже синтаксически полный ответ с `length` отклоняется. Недопустимые поля, ссылки, ID/status модели и malformed JSON не исправляются. Python не подбирает цитаты к готовым утверждениям, не меняет chunk и не создаёт семантические связи за модель.

## Минимальная реализация и идентичность

- [driver.py](../../../day-29-local-assistant-optimization/driver.py): один `contract_variant=compact-evidence-v1`, допустимый только для baseline Coder chat S4/S6; несовместим с `prompt_variant`. Отдельный журнал/identity, порядок S4→S6, запрет повторов и stop-on-error. Compact rows не входят в baseline candidate selection. CLI-опция `--contract-variant compact-evidence-v1` доступна только в offline preview.
- Helper содержит schema, parser и renderer. Использованы существующие pack, frozen fixtures, settings, транспорт, metrics и bounded child. RAG, SQLite, Workspace, обычные schema/parser/renderer/prompt не изменены.
- Инструкция взята из baseline: изменены только описания полей, прямых Kotlin ссылок и runtime-owned status; `text` назван объяснением. Сохранены исходные ограничения scope, distrust и неизвестных реализаций. Нет explain-evidence-v1, новых API-подсказок, названий сценариев или эталонных ответов.
- Контекст пользователя, Kotlin, вопрос, Markdown chunks и порядок, модель, sampling, `num_ctx=8192`, `num_predict=2048`, `temperature=0`, `seed=28`, `keep_alive=5m` не меняются. Разница payload только в `format` и system message.

[Pinned manifest](../../../day-29-local-assistant-optimization/compact-contract-manifest.json):

| Поле | SHA-256 |
|---|---|
| Parent frozen manifest | `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4` |
| Parent prompt | `eb36c4a194ec44b548aaf0a6156ddf41d431f037c1990cd180d6e1c39386c3f6` |
| Parent schema | `478fcb753a8957c49815b62951f64b445a7a18301f8cb86425d05a540efac87c` |
| Compact prompt | `7cf8f554d62d6372392bf56617ea40f1c7dfd3acc17b834106b86c3b00410177` |
| Compact schema | `f9a7bf9822f9e2ee1319e03fbd927f99cba412420c150b0f5b13fdb46f0a8ad8` |

## Проверки

- Первый focused прогон: **193 passed**. После него добавлены три проверки exact quote 400/401, привязки цитаты к конкретному chunk и обязательных limitations при отсутствии observations.
- Итоговая полная relevant offline suite Day 27–29: **349 passed / 1 skipped**, 4.84 s. Новое покрытие compact — 78 cases. Первый вызов полного набора из корня без пути Day 27 остановился на collection (8 ModuleNotFoundError); повтор с корректным import path прошёл. Приложение ради этого не изменялось.
- Все вызовы модели в тестах — `httpx.MockTransport`; no inference. Проверены worker→validator→renderer, content-free metrics/journal при success/length, отсутствие пользовательских sentinel code/question/document/answer/reasoning в журнале, запрет смешивания профилей, порядок и отсутствие retries. Недоверенная Markdown-инструкция остаётся в user data, не становится ролью/system instruction. Это проверка границы ввода, не доказательство иммунитета модели к prompt injection.
- Все **12** baseline payloads (две модели × S1–S6) побайтно совпали с хэшами до изменений. **57** защищённых файлов Day 27–28, их OpenSpec, исторических Day 29 reports и manifests не изменились.
- AST syntax checks изменённых Python: PASS. OpenSpec `validate day-29-local-assistant-optimization --strict`: PASS. Root README Day 29 link сохранён.
- OpenSpec: **22/33**, задачи 7.1–7.2 завершены; 7.3 pending. Исторические checkpoint counts не переписаны.

Воспроизведение полной offline-проверки из корня, без изменения окружения сервера:

```powershell
@'
import sys
sys.path.insert(0, 'day-27-local-architecture-assistant')
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider',
    'day-27-local-architecture-assistant/tests',
    'day-29-local-assistant-optimization/tests']))
'@ | py -3 -X utf8 -B -
```

## Отдельный review до live

После нового разрешения: один preflight с local-only/digest/cleanup и действующим GPU criterion v2 (6 измерений через 5 s, median <15%, нет двух подряд ≥30%, free VRAM ≥9000 MiB каждый раз). Только прежний Coder digest/profile и frozen settings. Затем один S4 и, только при technical PASS, один S6 с deadline 180 s; без дополнительных preload, retries, repair или правки prompt. Любая техническая ошибка останавливает серию, неуспех сохраняется. Общий исторический бюджет учитывать до новой попытки, отдельный журнал не обнуляет его.

Review по прежней rubric: S4 — никаких выдуманных RPO/RTO и применения weather-rule; допустимы пустые documentary applications и честное незнание. S6 — UI state, StateFlow, lifecycle collection, LaunchedEffect keys/cancellation/re-entry и разделение обязанностей с обозначением неизвестного. Число элементов, компактность JSON и technical PASS сами по себе не улучшение. Риск зацикливания/копирования/ошибочного scope остаётся, schema не может проверить смысл. После двух попыток либо первого technical failure остановиться для совместного review, без окончательного выбора модели.

Commit/push, archive и видео не выполнялись.
