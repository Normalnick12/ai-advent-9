# Implementation verification — 2026-09-04

## Offline checks

- Backend: `backend/.venv/Scripts/python.exe -m pytest` — 102 passed.
- Android: PowerShell 7 `scripts/dev.ps1 unit` — 30 JVM tests passed.
- Android: `scripts/dev.ps1 build` — debug APK assembled.
- Android: full `scripts/dev.ps1 ui` — 13 instrumentation tests passed on the existing Pixel 3a API 34 emulator.
- New tests cover exact canonical payload fingerprint, independent verifiers, nullable quality versus real 0/5, actual-usage Decimal pricing, request equality/concurrency/error isolation, catalog validation, Android payload/timeouts/session state and UI details/navigation.
- Visual check at 320 dp width and 130% system font: title, selectors, result metrics and expanded details wrap and scroll vertically within safe system insets. Original density 440 and font scale 1.0 restored.

## One live UI E2E

Backend started through `scripts/dev.ps1 backend` in a managed terminal. `status` and an HTTP `/health` request from the emulator succeeded before the run. One explicit UI tap used the three default selections. No live retries or additional benchmark runs were made.

Request id: `7150cb208983`; benchmark `day05-v1`; fingerprint:
`01914c54838704723619457331e4d787299a23d010fdb23b1e66f725947d755c`.

Common configuration: Responses API, medium, max output 6000, strict output, temperature/top_p omitted, max retries 0, store false, default tier. Backend logs recorded three starts and three finishes, one API call per slot, and HTTP 200 for the batch. Changing display density/font during the active run retained the same request and results.

| Model | Quality | Incorrect tasks | Completion | Latency | Input / Output / Reasoning / Total | Cost USD |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-5.6-luna | 4/5 | Task 5 | completed | 59.247 s | 953 / 4553 / 4444 / 5506 | 0.0056542 |
| gpt-5.6-terra | 4/5 | Task 5 | completed | 90.105 s | 953 / 4461 / 4352 / 5414 | 0.055438 |
| gpt-5.6-sol | 5/5 | — | completed | 94.278 s | 953 / 4451 / 4342 / 5404 | 0.092832 |

All resolved ids matched requested ids. Cached input and cache-write counts were 0 for all three. Costs shown in UI match `(input * input_rate + output * output_rate) / 1000000`; reasoning is part of output. Total estimated usage-based cost: 0.1539242 USD.

Actual Task 4 for all three models:

```json
{"final_array":[22,15,-10,-10,11,18,-28,-12],"checksum":-147}
```

Actual Task 5: Luna `{"count":25}`, Terra `{"count":20}`, Sol `{"count":24}`. The independent exhaustive verifier gives 24; UI displayed the incorrect actual answers next to this reference for Luna/Terra. Tasks 1–4 passed for all models.

This is an implementation E2E observation, not an extension of the benchmark or a stable ranking. The historical three probes remain separate observations in the Day README. No commit, push or archive was performed.
