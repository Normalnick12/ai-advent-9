# Day 17 forced live — 2026-09-22

**Verdict: failed_final_response_count_mismatch.** Ровно одна отправка из Android,
одна backend operation и один `AsyncOpenAI.responses.create`; provider вернул один
`mcp_list_tools` и один `mcp_call`. Remote tool и доставка результата в Android
работают, но успешный forced acceptance не пройден: модель сообщила **133** версии
при **129** элементах в tool result. Повтор, regeneration и repair не выполнялись.

## Deployment и подготовка

- Render: `https://android-dependency-mcp.onrender.com`; MCP: `https://android-dependency-mcp.onrender.com/mcp`.
- Deployed SHA: `ad1dae7b615072de7fa271a6e94e065373a747cb`, подтверждён пользователем; Auto-Deploy выключен. Последующие evidence/docs не меняют SHA этой попытки.
- Перед отправкой повторно проверены `/health` и `tools/list` официальным `mcp==2.2.0`, без `tools/call` и без Responses generation. [Readiness](evidence/forced-01/readiness.json).
- Backend запущен через `scripts/dev.ps1 backend` в отдельной управляемой сессии с `DAY17_MCP_SERVER_URL`. `/health` доступен с host и эмулятора (`10.0.2.2:8000`, HTTP 200). Первый некорректно сформированный диагностический HTTP health request дал 400; затем исправлен только синтаксис health probe, generation при этом не выполнялась.
- На работающий `emulator-5554` установлен уже проверенный debug APK; код, сборка и таймауты прежних Days не менялись. Day 17 использует собственные 75 s и `max_retries=0`.
- Пассивный локальный observer сохранил ASGI request/response и исходные SDK payload/response без заголовков/секретов. Он вызывает исходный SDK метод один раз, не меняет payload/result и не инициирует generation. Его [точный исходник](evidence/forced-01/sitecustomize.py) сохранён для аудита; production source не изменён.

## Одна явная отправка

На экране проверены default prompt и forced mode, затем выполнен один tap штатной
кнопки «Отправить». Координаты tool сформировала модель, backend их не подставлял.

> Получи опубликованные версии androidx.core:core-ktx из Google Maven. Укажи количество и три последних элемента в порядке источника. Не оценивай стабильность или совместимость.

Requested model: `gpt-5.6`; resolved model в фактическом response: `gpt-5.6-sol`.
`tool_choice`: `{"type":"mcp","server_label":"android_dependencies","name":"get_google_maven_versions"}`.
Allowlist — один tool; `require_approval="never"`, `store=false`.

| Evidence | Фактическое значение |
|---|---|
| Operation id | `ff7afd5a-634b-4f9c-a467-286105eb1a36` |
| Response id | `resp_06fba37e66c07c66016ab297f02ea087d2bc2f76fea51e5f9d` |
| Call id | `mcp_06fba37e66c07c66016ab297f3910887d2896e14c262773dc1` |
| Lookup id | `730a8685-51e8-4627-8c21-3a587b6d8b4f` |
| Actual arguments | `{"group_id":"androidx.core","artifact_id":"core-ktx"}` |
| Provider / call status | `completed` / `completed` |
| Operation outcome / invocation | `completed` / `observed` |
| Tool result | `found`, 129 версий |
| Source URL | `https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml` |
| Tool checked_at | `2026-09-22T15:00:04.251838Z` |

Raw `mcp_call.output` — JSON объекта результата; он полностью совпадает с
`parsed_result`, включая все 129 версий, координаты, URL, время и lookup id.
Все MCP items исходного provider response совпадают с items backend operation.
Android показал одну операцию, один вызов, 129 версий и исходный ответ модели;
Inspector показал настоящие operation/response ids и один imported tool.

Пользователь предоставил [строку Render Logs](evidence/forced-01/render-upstream.log).
По lookup id, координатам, URL и outcome она совпадает с result; HTTP 200,
`versions_count=129`, `elapsed_ms=431`. Источник строки — пользовательский экспорт
Render Logs, прямого доступа к control plane не было.

## Проверка final response

Модель ответила:

> Опубликовано версий: **133**.
>
> Три последних элемента в порядке источника:
> 1. `1.19.0-alpha02`
> 2. `1.19.0-rc01`
> 3. `1.19.0`

Последние три элемента совпадают с `versions[-3:]` в source order; количество
неверно (`len(versions)=129`). Рекомендаций stable/latest/compatibility нет.
`completed` означает завершение provider operation и не доказывает истинность
final prose. Полная MCP evidence-цепочка подтверждена. По согласованному уточнению
task 7.2 закрывается как выполненная проверка с сохранённым failure verdict;
полный forced acceptance остаётся непройденным. Результат не исправлялся и не перегенерировался.

Optional auto **not performed / не проводился**; по решению пользователя дополнительных
generation не будет. Видео Day 17 записано, подтверждено пользователем 2026-09-22.
При finish-day публикуются docs/evidence этой попытки, синхронизируются specs и
архивируется завершённый эксперимент. Это не меняет failed forced acceptance.

## Сохранённые артефакты

[Manifest](evidence/forced-01/manifest.json) содержит timestamps, ids, counters,
проверки фактов, verdict и SHA-256 файлов. В той же папке сохранены полные
Android request/response, SDK request/response, marker единственного Send,
readiness, исходный observer, UI XML и screenshots до отправки, результата и
Inspector. Это данные одной наблюдаемой попытки, не оценка устойчивости модели.
