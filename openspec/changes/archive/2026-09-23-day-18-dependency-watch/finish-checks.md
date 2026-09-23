# Day 18 finish checks — 2026-09-23

## Scope and result

Day 18 service, local backend integration, Android lab, focused tests, deployment
helpers, documentation and OpenSpec evidence. All 34 tasks were complete before
archiving. Main specs received three new capabilities and the Day 18 navigation
requirement; existing navigation requirements were preserved.

The Day README was reduced to the experiment and observed results. Archive links
and the design's API route were corrected. Public deployment settings were renamed
from `deploy/public.env` to `deploy/public.conf`; the bootstrap reference was updated.
The file contains only the public hostname/URL. The deployed snapshot and historical
manifests retain their original filename. All 19 recorded contents matched the
local snapshot before final whitespace cleanup (with that filename mapped). The
staged whitespace check then found one redundant blank line at the end of
`storage.py`; it was removed without changing executable code. VPS runtime and data
were not changed.

## Checks

| Mode | Check | Result |
| --- | --- | --- |
| run | `openspec validate day-18-dependency-watch --type change --strict --no-interactive` before archive | passed |
| run | Four delta/main comparisons, including preservation of existing navigation | matched |
| run | `openspec validate --specs --strict --no-interactive` | 37 passed, 0 failed; informational long-requirement notices only |
| run | `openspec archive day-18-dependency-watch --skip-specs --yes` after verified inline sync | archived; non-blocking recommendation to split large changes |
| run | Python AST, JSON parsing, changed Android XML, Markdown links and root Day index | passed |
| run | `bash -n day-18-dependency-watch/deploy/bootstrap.sh` after public config rename | passed |
| run | Read-only comparison of saved create/summary/VPS/window/recovery evidence and deployed SHA256 manifest | passed; one create, one summary, three successful terminal executions, matching aggregate/history, both recovery probes passed |
| reused | Standalone `.venv/Scripts/python.exe -m pytest -q` in Day 18 | 44 passed |
| reused | Backend Day 18 suites plus `test_mcp_lab.py` and `test_agent_adapter.py` | 77 passed |
| reused | `scripts/dev.ps1 unit -Test '*DependencyWatch*'` | 5 passed |
| reused | Targeted DependencyWatch UI, narrow/IME, receipt persistence and RootNavigation UI checks | 13 passed |
| reused | `scripts/dev.ps1 build` | debug build successful |
| reused | Offline launcher checks: repeated preflight evidence, existing-attempt guard, safe SSH diagnostics, PowerShell 7 discovery | passed; no model calls |
| reused | Main Android create/background/summary acceptance and restart/reboot probes | passed; detailed evidence in this archive |
| reused | User-provided normal-interval restoration output | short intervals disabled, service active, trusted HTTPS health OK |

Reused results cover unchanged application behavior from this working session;
`offline-checks.md` is the historical pre-deployment checkpoint, while
`deployment-checks.md` and `live-report.md` record the later completed stages.
No new generation, create, summary, remote mutation or runtime probe was performed
by finish-day. Final Git whitespace, forbidden-file and secret checks are also run
against the staged snapshot before commit. Local environments, credentials, caches,
SQLite data and Android build output remain ignored.
