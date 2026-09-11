# Day 10 implementation verification

Этот раздел и первоначальные числа ниже — исторический отчёт apply v1.
Последующие apply v2/v3 и live evidence v1/v2 зафиксированы отдельно ниже;
прежние deterministic passes не являются доказательством live behavior v3.

## Scope and evidence

Implementation uses one `SimpleAgent`, opt-in strict output formats, concrete
Day 10 preparation and a separate SQLite run/topology store. Window uses six
confirmed messages. Facts patches and conversation pairs commit together.
Checkpoint creates only A/B, and evaluation outputs never become conversation
sources. Android provides independent scenario-first runs, read-only facts,
explicit evaluation slots and a read-only comparison dashboard.

The eight fixture bodies are checked byte-for-byte against the experiment spec.
The tests exercise strict values, actual selected sources, extraction/response
failure, SQLite COMMIT rollback, restart, branch isolation and parallel slots.
Runtime receipt totals are separate from preflight and durable experiment outputs.

Covered deltas: `context-strategies-experiment`, `context-strategies-android`,
`first-agent-conversation`, `learning-days-navigation`, `learning-days-presentation`.
No architecture/behavior contract was waived. Adding the ninth catalog card exposed
a header-overlap problem in the catalog scroll viewport; the viewport now starts
below the header. The Day 07 navigation test additionally asserts the actual chat
screen after the same touch click.

## Deterministic verification

- Backend: `python -m pytest -q` from `backend`: **309 passed**.
- Day 10 backend subset: **31 passed**; fake generation only.
- Android `scripts/dev.ps1 unit`: **70 passed**, no failures/errors.
- Android `scripts/dev.ps1 build`: debug build successful.
- Targeted Day 10 UI: preparation, disclosure, branches, inspector, restore and
  evaluations passed. The full suite also exercised the added 320×480 dp ordinary
  small-screen flow.
- Day 07 targeted UI after the catalog viewport fix: **4 passed**.
- Day 09 targeted UI: **3 passed** without changing its implementation or tests.
- Final full UI regression after the Android guest reboot: **35 passed**, zero
  failures/skips. `scripts/dev.ps1 ui` completed successfully; task 11.3 is closed.
- Strict OpenSpec validation passed; Markdown structure/local links and new Python
  syntax passed. Sections 1–11 are complete: **51/56 tasks**; Section 12 is separate.

Earlier full UI attempts encountered an Espresso main-looper idle hang in existing
Day 09 tests. A JDWP stack showed `Espresso.onIdle` / `Interrogator.interrogateQueueState`,
not a backend wait. Only the owned test application was stopped to release those
runs; their resulting “Process crashed” reports are interrupted runs, not passes.
Quick Boot did not eliminate the issue; a full Android guest reboot was performed
without clearing data. Animation settings were already zero and were not changed.

No dedicated large-font test was added or run. Existing Day 08/09 accessibility
cases remain in the normal full UI suite. No tests were removed or skipped to
obtain a successful result.

## Separate manual acceptance

At the end of the original v1 apply, Section 12 remained unchecked and no live
OpenAI scenario, model-quality result, live token total, video, archive, commit or
push had been performed by that apply. Subsequent user-run v1 evidence follows.
Fake tests establish contracts, not actual model behavior or a winning strategy.


## V1 live evidence (historical; not repaired)

Configuration `day10-gpt4o-mini-n6-v1`, Facts run
`9e7bb82e-ef7d-45e3-bd6b-a567f8d462a9`: progress 3/8, revision 3.
Turn 2 omitted deadline_weeks=8 and pilot_users=37; its raw extraction output was
not retained, so omission is established from durable state/lifecycle, not a saved
provider JSON. Three diagnostic Turn 4 attempts returned the same erroneous
replace shared.offline_schedule=true with evidence email_reminders=true.
Validator correctly rejected index 0 with assertion_not_found; the valid adjacent
style change was also rejected atomically. This is an extractor failure, not a
validator bug. Exact patches and all three attempt IDs are in
[design evidence](design.md#v1-live-evidence-and-v2-scope).
User-confirmed successful Window v1 remains historical evidence; its metrics are
not imported into the final v2 dashboard. No missing historical token totals or
model outputs have been invented.

## V2 implementation and deterministic verification

Implemented `day10-gpt4o-mini-n6-v2`: exact design extraction instructions and
backend/Android namespace constants. Scenario meeting-rooms-v1, facts-v1,
meeting-spec-v1, gpt-4o-mini, N=6 and all validator/atomicity/strategy contracts
remain unchanged. Config comparison against the pre-change baseline found only
version metadata changes in response/evaluation, and instructions plus version
in extraction. No other backend production file changed in this delta.
Android uses its separate v2 SharedPreferences file; the existing adapter has a
small internal opener constructor for JVM tests, with unchanged Context wiring.
No navigation/layout changes or migration/import UI were introduced.

- Targeted backend v2/diagnostics: **18 passed**.
- Targeted Android Repository/ViewModel/preferences: **8 passed**, via
  `pwsh -File scripts/dev.ps1 unit -Test '*ContextStrategies*Test'`.
- One final full backend deterministic regression: **327 passed**, including
  Day 02–09 payload/call-count and Day 10 window/facts/branches/evaluation tests.
  One existing Starlette/httpx deprecation warning; no test failures.
- One final Android JVM regression via `scripts/dev.ps1 unit`: **72 passed**,
  zero failures/errors/skips.
- Temporary v1/v2 stores tested separate creation, cross-version rejection,
  no fallback, reset/reopen and unchanged historical bytes. Actual live v1 SQLite
  SHA-256 matches the pre-apply baseline; Facts remains revision 3.
- No full UI suite, dedicated large-font smoke, emulator scenario, provider calls,
  backend restart, video, commit, push or archive was performed in this delta.
  No v2 debug APK was installed; the JVM task compiled the changed Android code.

At completion of the v2 apply, live v2 was still pending and the planned comparison
required fresh v2 runs. Subsequent user-run v2 evidence follows; it supersedes
that pending status without rewriting the historical deterministic results.

Final v2 closure: **56/61 tasks complete**, only 11.6–11.10 closed in this delta.
Strict `openspec validate day-10-context-strategies --strict --no-interactive`
passed; changed Python syntax and Markdown/local links passed. No additional
full suites were run after documentation-only edits.


## V2 live evidence (historical; not repaired)

Configuration `day10-gpt4o-mini-n6-v2`, Facts run
`7a18fc6f-6b0d-460d-afb8-b40a21138b49`: confirmed progress 7/8.
The user reported three consecutive explicit Turn 8 retries returning equivalent
`replace B.payment=link` and `replace B.confirmation=admin` changes with correct
scope, values and evidence. These B identities did not exist; A identities do not
establish B identities. The validator correctly rejected the whole patch with
`extraction_replace_missing / replace_missing`; confirmed state was not corrupted.
The supplied diagnostic identifies client attempt
`dc032dbe-0604-4307-bcd8-ec69deaf62e9` / server attempt
`20125efa-af5d-436d-9075-57ddd595ef6c`. No missing attempt IDs or usage were invented.
No recovery conversion, partial save or further v2 retry is part of v3.

## V3 implementation and deterministic verification

Implemented config `day10-gpt4o-mini-n6-v3`, extraction schema `facts-v2`, exact
v3 design prompt and current_user-only extractor input. The model receives no
previous state/history/assistant/evaluation/verifier data and emits no storage op.
Whole semantic validation precedes a narrow reducer using actual previous state:
set adds/reactivates, updates a different typed value, or preserves the whole
record on no-op; clear creates a tombstone, preserves an existing tombstone, or
rejects a never-existing identity. Wrong values and omissions are not repaired.
Candidate facts still commit with pair/step/revision only after successful response.

Only backend production files `context_strategies_models.py` and `fact_extractor.py`
changed against this apply's pre-change baseline. Response/evaluation settings
changed only in version metadata; extraction changed instructions/version/format.
Durable Fact schema, scenario fixtures, verifier values, N=6, gpt-4o-mini,
meeting-rooms-v1, meeting-spec-v1, Sliding/Branching/evaluation/metrics/accounting
and shared Day 02–09 production code were unchanged in this delta.
Android production changed only STRATEGIES_VERSION; its separate preferences
start without v1/v2 IDs, while historical preference files remain untouched.

- Targeted backend extractor/reducer/config/isolation/diagnostics: **45 passed**.
- Targeted Android Repository/ViewModel/version preferences via
  `scripts/dev.ps1 unit -Test '*ContextStrategies*Test'`: **8 passed**.
- One final full backend regression via `python -m pytest -q`: **353 passed**,
  with one existing Starlette/httpx deprecation warning. Includes Day 02–09 exact
  payload/call-count tests and Day 10 Sliding/Branching/evaluation/atomicity tests.
- One final Android JVM regression via `scripts/dev.ps1 unit`: **72 passed**,
  zero failures/errors/skips. Both JVM runs used PowerShell 7 and the project script.
- Temporary v1/v2/v3 store tests cover cross-version rejection, no fallback,
  no migration, historical reopen and unchanged historical bytes. Actual live v1
  and v2 SQLite SHA-256 hashes match the pre-apply baseline. No actual v3 store/run
  was created; all automated runs used temporary stores and fake/mock providers.
- Semantic tests cover scoped B creation independently of A, typed update/no-op,
  preserved provenance, clear/reactivation, unknown clear, legacy op rejection,
  all required schema fields and semantic rejection before reducer. Lifecycle
  tests cover candidate response context, failure without response, atomic
  rollback/reopen and confirmed no-op turns without rewriting fact provenance.
- No UI/layout code changed, so no additional UI matrix, dedicated font-scale
  smoke or new accessibility test was needed. No debug APK build/install or
  backend restart was performed; JVM tasks compiled the changed Android code.

At the end of the v3 apply, live acceptance had not been performed. The planned comparison required fresh
Window v3, Facts v3 and Branching v3 only; successful Window v1 and failed Facts
v1/v2 remain isolated historical evidence. Fake tests establish contracts, not
proof that gpt-4o-mini will extract every fact correctly in a live run.
No OpenAI/provider calls, manual emulator scenario, real run/reset, retries,
video, archive, commit or push were performed in this apply.

V3 implementation closure: **61/66 tasks complete**, only 11.11–11.15 closed in this delta;
12.1–12.5 remain unchecked for separately authorized manual acceptance.
Strict `openspec validate day-10-context-strategies --strict --no-interactive`,
changed Python syntax and Markdown/local links passed. Full suites were not
repeated for documentation-only edits.


## Final v3 controlled live acceptance (user-confirmed)

The user confirmed completion of the controlled experiment and recorded video,
then explicitly confirmed manual task 12.3. This section records their supplied
observations, separately from automated fake-provider results above. Configuration
was `day10-gpt4o-mini-n6-v3`, using only new Window/Facts/Branching v3 runs.
No v1/v2 outputs enter this final comparison. No new provider calls were made to
write this report or finish the Day. Raw final JSON and v3 run/attempt IDs were
not supplied in this acceptance message and are not reconstructed here.

Each strategy completed **8/8 committed Sends and 2/2 explicit A/B evaluations**.
Evaluations were separate experiment operations, not ninth/tenth conversation turns.

| Observation | Window v3 | Facts v3 | Branching v3 |
| --- | --- | --- | --- |
| ТЗ A | 3/11 | 11/11 | 2/11 |
| ТЗ B | 3/11 | 4/11 | 11/11 |
| Retention A | 3/11 | 11/11 | 11/11 |
| Retention B | 3/11 | 11/11 | 11/11 |
| Response input / output | 4259 / 150 | 7451 / 163 | 5245 / 157 |
| Maintenance input / output | 0 / 0 | 4652 / 535 | 0 / 0 |
| Total known tokens | 4409 | 12801 | 5402 |
| Coverage | incomplete / unknown | incomplete / unknown | complete for observed operations |
| Unknown outcomes | 2 | 3 | not separately supplied |
| Last context/preflight shown in UI | 692 | 918 | 621 |
| Mandatory memory-management actions | 0 | 0 | 1 checkpoint, 3 branch switches |

The preflight values are context measurements, **not actual generation usage**.
Window and Facts required explicit user retries; unknown outcomes stay unknown,
not zero. Their totals are minimum observed known usage, not exact full-run costs.
Branching has complete observed coverage at 5402. Facts has substantially higher
known usage in this run, including **5187 known maintenance tokens**; no universal
cost ranking follows. In particular, Window cannot be declared definitively
cheaper than Branching given Window's incomplete coverage.

### Final strategy state

- Window: N=6; 6 active messages and 10 out-of-window messages. Only 3/11 relevant
  requirements remained available for each evaluation; no maintenance calls or
  mandatory memory-management actions.
- Facts: raw tail=6; **13 active facts** in the final state. A/B facts coexisted:
  `A.payment=on_site`, `A.confirmation=immediate`, `B.payment=link`,
  `B.confirmation=admin`. Both variants retained 11/11 required values; A answered
  11/11 but B only 4/11. Inspector actions are optional, not mandatory management.
- Branching: shared prefix **12 messages / 6 turns**, one explicit checkpoint,
  A local **2 messages**, B local **2 messages**. Isolation: **выполнено**.
  Both variants retained 11/11; A answered 2/11 and B 11/11. Low A quality is a
  generation result, not evidence of context loss or opposite-branch leakage.

### Interpretation and limits

Retention != response quality. Context assembly makes information available, but
stochastic generation need not use every available requirement correctly. Facts B
(11/11 retained, 4/11 answered) and Branching A (11/11 retained, 2/11 answered)
make this distinction visible. Facts does not guarantee better answer quality.

Sliding is simple for local recent context but loses early requirements. Facts
supports stable requirements without mandatory memory management, with extraction
overhead and an additional failure surface. Branching fits independent alternatives,
without LLM maintenance overhead but with checkpoint/switch actions. There is no
universal winner; these are observations from **one controlled run per strategy**.

Historical Facts evolution is engineering evidence, not extra final benchmark runs:
v1 semantic identity/evidence failure -> v2 storage-operation classification failure
-> v3 semantic extraction by LLM plus deterministic backend state transitions.
Ordinary code should own deterministic decisions it can make exactly. Strict
semantic validation still rejects wrong values; backend does not repair omissions.

### Manual evidence and task closure

- **12.1:** User-confirmed completed live runs demonstrate operational backend and
  Android connectivity in the live environment. No fresh environment command or
  `/health` response is claimed here as provider evidence.
- **12.2:** Exact final v3 observations are recorded above; only fresh v3 runs used.
- **12.3:** Explicit user manual confirmation: after restart, v3 durable Facts,
  Branching checkpoint/topology and saved evaluation outputs restored correctly;
  A/B independence was confirmed by the live acceptance and isolation result.
  Restore caused no provider replay/generation. Whole-run reset succeeded and
  remained deleted after restart. Runtime-only token coverage behaved as designed,
  honestly representing coverage loss after process death. No further free checks
  are required for this task based on that confirmation.
- **12.4:** User confirmed the Day 10 video was recorded and demonstrates the
  implemented experiment and final results; no video URL/file was supplied.
- **12.5:** Day README and this report now reflect the supplied observations,
  incomplete coverage and single-run limits, keeping v1/v2 historical evidence apart.

All **66/66 tasks** are complete. Finalization may now validate, sync/archive and
commit/push the scoped Day 10 work under the user-authorized finish-day workflow.


## Finish-day verification record

The user authorized finish after confirming the final live experiment, video and
manual restart/restore/reset checks. Documentation-only changes reuse the concrete
v3 apply evidence: backend 353 passed, Android JVM 72 passed, and the unchanged
UI area's earlier debug build/full UI regression (35 passed). No full UI/font-scale
matrix or new provider call is necessary for recording these observations.
The only test-code adjustment allows two tests to find canonical spec/design after
archive; their assertions and production code are unchanged.

Strict change validation was run successfully before archive. All five capability
deltas were synchronized and compared with main specs, preserving unrelated old
requirements/scenarios; strict specs validation: 16 passed. The OpenSpec CLI archived
the completed change to `2026-09-11-day-10-context-strategies` with spec update skipped
only because the inline sync had already completed and been verified.


Finalization checks run: the two archive-aware backend test files passed **15 tests**;
Python syntax and Markdown structure/local links passed (35 local links checked).
The intended 52-file Day 10 scope passed forbidden-path and secret-pattern checks;
local SQLite databases, virtual environments and Android build outputs are ignored.
`git diff --check` passed. No new live/provider call or dedicated large-font test
was performed during finalization. Backend/Android production behavior is unchanged
from the verified v3 implementation.
