# Offline verification — 2026-09-23

Локальная реализация завершена. Публичный deployment согласованно отложен до выбора
домена; временный hostname/tunnel не задан. VPS не изменялся. Live и подтверждение
видео остаются открытыми задачами 8–9, полный acceptance не заявляется.

## Проверки

| Проверка | Результат |
| --- | --- |
| Standalone service: `.venv/Scripts/python.exe -m pytest -q` из `day-18-dependency-watch` | 44 passed |
| Backend: Day 18 suites + `test_mcp_lab.py` + `test_agent_adapter.py` | 77 passed |
| `scripts/dev.ps1 unit -Test '*DependencyWatch*'` | 5 tests, 0 failures/errors |
| `DependencyWatchUiTest` | 2 passed |
| `DependencyWatchNarrowUiTest` | 1 passed; 320dp, font scale 1.5, IME, error Inspector |
| `DependencyWatchReceiptStoreTest` | 1 passed |
| `RootNavigationUiTest` | 9 passed, включая Day 17/18 без replay |
| `scripts/dev.ps1 build` | BUILD SUCCESSFUL, debug APK |
| Python AST, изменённый XML, README links, whitespace/secret review | passed |
| `git diff --check` | passed |
| `openspec validate day-18-dependency-watch --strict` | passed |

Android UI выполнялись последовательно через `scripts/dev.ps1` на Pixel 3a API 34,
без backend/OpenAI. Сверены Gradle success и JVM XML reports; процессные exit codes
не использовались как единственный признак успеха. Backend suite выдаёт существующее
предупреждение Starlette о будущем отказе от httpx в TestClient; тесты проходят.

## Ключевые доказательства

- Persisted succeeded + running → reopen/recovery → немедленный summary до tick:
  interrupted=1, runs_total=2, successful=1, failed=1; through_execution_id указывает
  на восстановленный execution. `aggregate_json` execution и watch согласованы.
  Проверены active/max_runs=3 с сохранённым due next slot и completed/max_runs=2/null.
- Failpoint откатывает execution, aggregate и watch вместе. Повторный startup после
  commit не удваивает counts; recovery не выполняет lookup. Отдельный lifespan test
  подтверждает recovery до readiness и запуска worker.
- Overlapping ticks дают один claimed slot/lookup. Coalescing и clock jumps сохраняют
  исходную сетку; пропущенные слоты не превращаются в фиктивные snapshots.
- Оба MCP tools проверены официальным SDK 2.2.0, включая structured/text wrappers.
  HTTP требует Bearer до dispatch; чужой Host/Origin отклоняется. Второй owner не
  допускается; worker failure снимает readiness и сообщает production supervisor.
- Установленный OpenAI SDK содержит native MCP `authorization`. Fixture tests
  подтверждают это поле в каждой операции, allowlist/forced choice, max_retries=0,
  все create calls, partial/refusal/unknown и rejected summary identity mismatch.
- Synthetic sentinel не попадает в prompts, Android DTO, evidence или logs.
  Redacted write-ahead attempt переживает отмену ожидания Responses; replay отсутствует.
  Typed facts проверяются отдельно от заведомо неверного model prose fixture.
- Android сохраняет все подтверждённые watch IDs и selection, показывает сведения
  как последние известные. Duplicate Send блокируется до coroutine launch. Новая
  ошибка не наследует прошлый successful evidence.

## Границы проверки deployment

systemd unit проверен как INI и по путям/permissions/restart settings; Caddy template
проверен статически. Native `caddy validate` и `systemd-analyze verify` недоступны
в текущем Windows окружении и должны быть выполнены на VPS после выбора hostname.
Это не TLS/firewall/boot verification. SQLite/environment вынесены из release tree.
Для сверки будущего deployed snapshot подготовлен `deploy/manifest.py`.

Не выполнялись SSH deployment, реальные Google Maven/OpenAI calls, service restart
и VPS reboot probes, остановка backend в live window или overnight. Поэтому механизм
на fixtures проверен, а реальная временная независимость VPS и точность live prose
пока не доказаны. Commit, push и archive не выполнялись.
