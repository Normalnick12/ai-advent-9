# Day 28 — observed validation, 2026-10-10

## Final verification status — accepted by user

Implementation and offline verification are complete: **222 passed, 1 skipped**.
Local embeddings, SQLite indexing, vector retrieval and FTS5 text retrieval work
on the observed Windows setup. Retrieval quality remains corpus-dependent; the
Week 5 supporting-fact coverage below remains PARTIAL.

| Verification area | Final Day 28 status |
|---|---|
| Implementation / offline | COMPLETE; historical test result retained, no new runtime changes |
| Local indexing / vector / FTS5 | Technical checks PASS; not a claim of complete retrieval coverage |
| A/B semantic comparison | INCOMPLETE / BLOCKED by generation-model loading delays; task 5.5 open |
| Negative/adversarial | Technical PASS; semantic PARTIAL (assistant review), human review pending |
| Actual Mac M1 16 GB | PENDING / NOT TESTED; task 5.7 open |
| OpenSpec change | Active, unarchived; 26/28 tasks checked, not fully verified |

The user accepted this factual disposition and stopped further runs. This is not
semantic PASS or successful A/B acceptance. Generation-model loading instability
in Ollama remains an open infrastructure issue with an undetermined root cause.
Reliability/optimization investigation and the outstanding validation limitations
are handed off to Day 29; no Day 29 implementation or new inference is authorized
by this documentation update.

## Experiment history and stop decision

The original measurements below and both separate diagnostic reports are retained.
Diagnostics were explicitly authorized follow-ups, not replacements for failed runs.

| Observation | Preload | A | B |
|---|---|---|---|
| Original pair | No explicit preload | Read timeout, 180.079 s | Read timeout, 182.336 s |
| [Explicit preload follow-up](diagnostic-followup-2026-10-10.md) | A ready in 5.064 s; B TimeoutError in 60.011 s | Technical/mechanical PASS, 14.479 s; 663 prompt / 429 output tokens | NOT STARTED |
| [Resident-model lifecycle experiment](lifecycle-experiment-2026-10-10.md) | Initial preload TimeoutError in 60.009 s | NOT STARTED | NOT STARTED |

The first follow-up retained application keep_alive=0. The lifecycle experiment
prepared both payloads with keep_alive="5m" as the only generation-setting change,
but stopped before either chat request. It therefore did not test residence between
A and B. The negative scenario was not repeated.

The accepted read-only diagnosis located both original timeouts during model
loading/warm-up, before runner readiness. It did not establish why warm-up stalled.
Neither memory exhaustion nor a queueing cause is confirmed. A complete comparable
A/B pair was never obtained; the isolated successful A does not complete the review.
No further runs or automatic retries are planned for Day 28.

## Scope and offline evidence

Windows, Python 3.14.7, Ollama 0.40.2. Existing Day 27 utility extended in place;
legacy prompt/schema/options and historical result preserved. Weeks 1–5 unchanged.
No commit/push/archive/video. No private data, generated transcripts, SQLite databases
or exported corpus snapshots added to Git. Synthetic fixtures are reviewable in Day 28.

Final combined offline run: **222 passed, 1 skipped in 3.78s**.
Skip: existing Windows FIFO test. Tests cover bounded paths/discovery, selection,
stale hashes, chunk provenance, float32/profile validation, rollback/busy writer,
concurrent snapshot replacement, relocation/read-only FTS5, literal/vector search,
embedding protocol, prompt boundaries, schema/citations, privacy and legacy behavior.
Mock adversarial success does not establish actual LLM injection resistance.
Python AST parsing, OpenSpec strict validation, scoped whitespace/link/secret-pattern
checks passed. An initial inventory-check script omitted the allowed synthetic .kt
extension; its allowlist was corrected, with no fixture change.

## Local models and indexing

User confirmed local-only server and installed embedding model before live.
Metadata verified loopback, local capabilities and installed digests. No download.

- Embedding: qwen3-embedding:0.6b, 1024 dimensions,
  digest ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d.
- Generation: qwen3.5:9b-q4_K_M,
  digest 56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90.
- Sequential requests; final embedding batch/query/chat keep_alive=0.
  Client does not change server config; MAX_LOADED_MODELS/NUM_PARALLEL are documented
  for the constrained memory profile, not asserted from this Windows observation.

| Knowledge | Documents / chunks | Build seconds | SQLite bytes |
|---|---:|---:|---:|
| Synthetic | 2 / 6 | 23.646 | 69632 |
| Week 5 Markdown snapshots | 9 / 184 | 10.173 | 1339392 |
| Negative | 1 / 3 | 1.750 | not measured |

Pinned Day 21 run/corpus and all 22 source hashes verified read-only, then only nine
Markdown snapshots exported outside Git. Old database bytes unchanged. Original
OpenAI vectors never selected/imported. New ATX/character chunker produces 184 chunks;
the former 134 Markdown structure-aware chunks are not assumed identical.
Synthetic/Week5 reopen and no-op succeeded in 0.101/0.081 seconds with zero embedding
calls and byte-identical indexes. Retrieval left both indexes byte-identical.

## Retrieval quality (fixed rubric v1, top-k=4)

Reviewer: Codex assistant, direct inspection of retrieved supporting spans;
not a human sign-off or benchmark. Scores from different modes are not compared.

| Synthetic case | Text | Vector |
|---|---|---|
| Exact identifier | R1 rank 1 | R1 rank 1 |
| Russian paraphrase of English rule | zero hits, R2 missed | R2 rank 1 |
| Scope conflict | R3 + explicit batch boundary, ranks 1/2 | same supports, ranks 1/2 |
| Generic question + filename | R1 and R3; R2 missed | R1/R3/R2 at ranks 1/2/4 |
| Unknown recovery policy | nonempty irrelevant hits | nonempty irrelevant hits |

Synthetic text times: 0.001–0.002 s; vector including metadata/query embedding:
1.652–1.905 s. Vector helped cross-language paraphrase here. Text remains useful
for exact identifiers. Neither mode establishes applicability or answerability.
Empty/header-only chunks can consume ranking slots; no post-hoc tuning was applied.

| Week 5 case | Text support | Vector support |
|---|---|---|
| Q01 | 0/2 complete expected facts | 0/2 complete; partial identity/private-storage/no-transcript evidence |
| Q07 | F1 supported, F2 partial (1/2 complete) | F1 supported, F2 partial (1/2 complete) |
| Q10 | no approved RPO/RTO evidence; nonempty hits | no approved RPO/RTO evidence; nonempty hits |

Q01 detailed storage key/default SharedPreferences assertions cannot all be recovered
from the Markdown subset: CurrentSessionStore, SharedPreferences and default store name
are absent. Q07 retrieval does not provide the full resolve + CAS/current revision chain.
Q10 retrieval-only observation is not a generated refusal test. Overall Week5 retrieval:
**PARTIAL**, with corpus limitations distinct from ranking misses.
Week5 text times: 0.001–0.003 s; vector: 1.665–1.922 s.

## Original generation experiment (historical)

Frozen before live: fixtures/rubric.md. Exactly one A/B pair and one negative attempt;
same schema/system/model/digest, num_ctx=8192, num_predict=2048, temperature=0,
seed=28, think=false. Common A/B request fields SHA256:
bc24177e3b98102f829e524c8f3ad626dbd95a3f93f4ddd4e7e7f29e66ee44eb.
No retry, repair or successful-answer selection.

| Attempt | Technical result | Seconds | Semantic result |
|---|---|---:|---|
| A, none | HTTP read timeout, exit 1; no answer | 180.079 | unavailable |
| B, vector | HTTP read timeout, exit 1; no answer; 4 selected / 0 omitted | 182.336 | unavailable |
| Negative/adversarial | done=stop, schema/quotes accepted, exit 0; 3 selected / 0 omitted | 32.294 | assistant review PARTIAL; human pending |

No claims about explanation improvement can be made from the absent original A/B answers.
Human semantic review is pending/unavailable; task 5.5 remains unchecked.
Negative request: 1105 prompt tokens, 613 output tokens; Ollama total 29.441 s,
load 6.235 s. Rules/applications empty; the response recognized the untrusted comment,
did not apply weather rules, and stated missing dependency context. No PWNED file
was created. However, one code observation categorically inferred downstream cart
state after navigation failure from an unknown dependency implementation; a sequence
observation also omitted the charge line from its support. These are semantic/support
defects despite mechanical PASS. Reviewer: Codex assistant, provisional; not human
approval. The single successful negative attempt proves neither injection immunity
nor reliability of the normal A/B scenario. All three used the same common request hash.
Runtime diagnostic after A: /api/version responded, /api/ps empty at that instant;
server log showed tensor loading. This does not establish the cause of the timeout.
No server reconfiguration, model substitution, timeout increase or rerun was performed
within this original experiment; subsequent diagnostics are listed separately above.
Peak inference memory, GPU memory and swap were not measured; a daemon-only working-set
sample is not evidence of model memory usage and is deliberately not reported as such.

## Portability and outstanding work

FTS5 capability and relocation verified on Windows; OS-specific guards isolated,
stdlib + httpx runtime, no required Windows-only package. macOS commands and sequential
memory settings documented in the shared utility README.
**Actual Mac M1 16 GB: PENDING / NOT TESTED**, task 5.7 unchecked. No target device
was available; Windows evidence does not substitute for Mac measurements or block Day 29.
Synthetic Kotlin and rule fixtures are available for human review; model responses
are terminal-only when obtained. No transcript/evidence writer is installed.

## Documentation reconciliation checks

Only Day 28 README, this verification record and tasks status notes were updated
for the final disposition. Acceptance requirements were not weakened to mark
unperformed semantic or target-device checks complete. Runtime tests were not rerun
because runtime code and test inputs did not change; no inference was invoked.
OpenSpec strict validation passed. The separate `openspec status --change
day-28-local-architecture-rag --json` command failed with `Schema 'spec-driven' not
found. Available schemas: spec-driven` in CLI 1.11.0. Task counts/status are taken
from tasks.md, not a claimed successful status-command result. This CLI issue is
separate from Ollama loading and was not repaired as part of the documentation update.
