# Day 18 — основной live acceptance, 2026-09-23

## Результат

Один Android create request и одна отдельная Android summary operation выполнены.
Все шесть вердиктов ниже PASS для этого единственного прогона. Retry, regeneration,
repair и пробных OpenAI generations не было. Setup/readiness failures до запуска
backend не были model attempts. Пользователь подтвердил запись видео; finish-day ещё не выполнялся.

| Критерий | Вердикт | Фактическое основание |
| --- | --- | --- |
| MCP create mechanism | PASS | Один native MCP create call; actual arguments и receipt соответствуют запросу |
| Background scheduling | PASS | Три terminal executions на исходной 30-секундной сетке, три Google Maven HTTP 200 |
| Temporal independence | PASS | Все три запуска после Responses completion и остановки FastAPI/Android |
| Persistence | PASS | Watch/history/versions/aggregate сохранены в SQLite, Android receipt пережил force-stop |
| Aggregation correctness | PASS | Пересчёт persisted rows, aggregate_json и полный MCP summary совпадают |
| Model prose accuracy | PASS | Create explanation и summary соответствуют сохранённым фактам этого окна |

## Create и остановка клиентов

- Watch: `66d4ce61-bf97-4f22-8c3d-a1f538d1092c`.
- Model: `gpt-5.6`; native remote MCP через штатное `authorization`; Bearer redacted в evidence.
- Android click: `2026-09-23T18:11:11.8210612+00:00`.
- Backend operation start: `2026-09-23T18:11:11.950105+00:00`.
- Responses completion, зафиксированный backend после SDK return/normalization:
  `2026-09-23T18:11:19.478418+00:00`. Это локальная метка приёма результата, не server-side
  completion timestamp OpenAI и не момент Android render.
- Response ID: `resp_09791a4f3273d71e016ab416423cac87d2ba6341df089183cf`.
- MCP call ID: `mcp_09791a4f3273d71e016ab416449d2887d2b2468187b9057db9`.
- Actual model-generated arguments:
  `{"group_id":"androidx.core","artifact_id":"core-ktx","interval_seconds":30,"max_runs":3}`.
- Receipt: created `2026-09-23T18:11:17.233000+00:00`, active, runs_total=0,
  next_run_at=`2026-09-23T18:11:47.233000+00:00`, interval_seconds=30, max_runs=3.
- FastAPI PID 19452 остановлен в `2026-09-23T18:11:25.6677806+00:00`;
  Android force-stop выполнен в `2026-09-23T18:11:25.7960948+00:00`.
  Port 8000 закрыт, Android process отсутствует. Background window выдержан минимум
  до `2026-09-23T18:13:26.4112297+00:00`; в конце оба клиента оставались остановлены.
- Первый scheduled slot позже Responses completion на 27.754582 с; первый actual start
  позже на 28.370582 с и позже остановки обоих клиентов на 22.052906 с.
- Readiness clock evidence сохраняет local bounds вокруг SSH и server UTC,
  NTPSynchronized=yes. Интервал SSH менее секунды; запас до первого slot более 21 с
  относительно остановки клиентов. Timestamps не корректировались и не сдвигались.
- Первичный pre-stop receipt poll вернул false; после force-stop отдельное корректное
  чтение Android SharedPreferences подтвердило сохранённый watch ID. Исходный false
  оставлен в evidence, не заменён задним числом на точное время UI получения ответа.

## Execution history

Все часы в таблице — UTC, дата 2026-09-23.

| Run | Scheduled | Started | Completed | Outcome |
| --- | --- | --- | --- | --- |
| 1 | 18:11:47.233 | 18:11:47.849 | 18:11:47.889 | succeeded / found |
| 2 | 18:12:17.233 | 18:12:17.941 | 18:12:17.974 | succeeded / found |
| 3 | 18:12:47.233 | 18:12:48.014 | 18:12:48.048 | succeeded / found |

Три уникальных run IDs и lookup IDs связаны с SQLite и journal. Каждый GET направлен
на `https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml` и получил
HTTP 200. Duration upstream: 37/29/30 ms; в каждом снимке 130 версий. Полные версии,
per-execution aggregate_json и IDs сохранены в [VPS export](live-vps.json).

В journal за background window — три набора execution_started / google_maven_lookup /
execution_terminal и три HTTP GET к Google Maven. MCP/user/model requests в этом
окне не выполнялись. Проверенный deployed scheduler напрямую вызывает lookup без
OpenAI; manifest всех 19 файлов совпадает. Это evidence поведения приложения и его
журнала, не независимый packet capture всех сетевых процессов VPS.

Финальный watch: completed, runs_total=3, successful=3, failed=0, interrupted=0,
skipped_slots=0, next_run_at=null. Сравнимых снимков 3, first/last_version_count=130,
changes_detected=0, newly_seen_versions=[]. Содержимое списков версий одинаково.
Through execution: `798a0c33-11a0-4467-9b90-a602ce572c2f`.
Aggregate generated_at: `2026-09-23T18:12:48.048000+00:00`.
Отсутствие новых версий — нормальный результат наблюдения, не failure.

## Summary и ответ модели

- Start: `2026-09-23T18:21:50.811201+00:00`; completion: `2026-09-23T18:21:58.646744+00:00`.
- Response ID: `resp_05b5cf1d8aa02c03016ab418c0f4dc87d292d6dd8275ac8a93`.
- MCP call ID: `mcp_05b5cf1d8aa02c03016ab418c361e487d2a26fde543fad0020`.
- Один call `get_dependency_watch_summary`, actual arguments:
  `{"watch_id":"66d4ce61-bf97-4f22-8c3d-a1f538d1092c"}`.
- Read-only MCP result полностью совпал с persisted aggregate и history из SQLite,
  включая timestamps, counts, through_execution_id, final watch status и next_run_at.
  Typed DTO отличается только нормализованной записью UTC (`Z` вместо `+00:00`).
- Android durable selected receipt после summary: completed, 3/3; watch ID прежний.

Точный final response модели:

```text
Сводка watch для `androidx.core:core-ktx`:

- Выполнено **3 из 3** проверок, все успешны.
- Во всех сравнимых снимках найдено **130 версий**.
- Изменений не обнаружено: **новых версий нет**.
- Период проверок: **23 сентября 2026, 18:11:47–18:12:48 UTC**.
- Watch завершён; ошибок и пропущенных запусков не было.
```

Утверждение «новых версий нет» оценивается в контексте показанных трёх проверок,
не как глобальное обещание. Число 130 взято из фактических снимков этого прогона;
оно не hardcoded критерий. Overnight и физическое выключение ноутбука не проводились;
проверялась именно остановка FastAPI и Android, как в согласованном сценарии.

## Configuration и артефакты

Deployed release: `/opt/day18/releases/5b11f8d9e5a87a25`. Base commit:
`84832ec0a28180a473d4f2973346b89a15e66937` плюс uncommitted implementation;
точные hashes и packages — в [deployment/recovery evidence](deployment-checks.md).
Код/runtime dependencies/firewall/Caddy/systemd unit/SQLite schema во время live
не менялись. Единственное согласованное исключение: short-interval flag и restart.
После записи видео пользователь подтвердил возврат `DAY18_ALLOW_SHORT_INTERVALS=false`,
restart `day18-watch`, status=active и trusted HTTPS health `{"status":"ok"}`.
[Финальное подтверждение normal configuration](normal-interval-restoration.json) сохранено
отдельно от исторического live evidence; повторных model requests не было.

- [Create evidence: все MCP items, arguments, receipt и prose](live-create.json)
- [Local stop/window evidence](live-local-window.json)
- [Clock/readiness evidence без token](live-clock-readiness.json)
- [SQLite/history/versions/journal export](live-vps.json)
- [Summary evidence: все MCP items и prose](live-summary.json)
- [Android saved summary](live-android-summary.json)

Пользователь подтвердил запись видео после просмотра результата. Task 9.5 выполнена.
Normal interval configuration восстановлена; task 9.4 выполнена.
Все 34 implementation tasks завершены. Commit, push, archive и finish-day не выполнялись.
