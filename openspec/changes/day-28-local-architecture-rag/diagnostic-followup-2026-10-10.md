# Diagnostic follow-up with explicit preload — 2026-10-10

Separate authorized observation. Original Day 28 A/B timeouts (180.079 / 182.336 s)
and negative run remain unchanged in validation.md. No negative rerun, automatic
retry, model substitution, timeout increase, commit/push, archive or video.

## Method

Official local Ollama load-only: POST /api/chat with model=qwen3.5:9b-q4_K_M,
messages=[], stream=false, options.num_ctx=8192, keep_alive="5m".
The diagnostic wrapper imposed an asyncio total deadline of 60 seconds (including
connection and full response); no user answer was requested by this operation.

Runtime files were not edited. A temporary in-memory wrapper around the existing
generate call performed load-only and readiness checks immediately before chat.
For B, unchanged vector retrieval ran first, so embedding loading could not evict
an already confirmed generation runner between the preload check and chat.
Readiness required matching installed digest and context_length=8192 in /api/ps;
ollama ps was used to record PROCESSOR. No separate server was started or configured.

Generation payloads were verified against the original common-request SHA256
bc24177e3b98102f829e524c8f3ad626dbd95a3f93f4ddd4e7e7f29e66ee44eb.
A body: 5249 bytes / 0 chunks. B body: 7172 bytes / 4 chunks, identical document
content, IDs, coordinates and ranking to the original B. No omission or truncation.
Generation parameters unchanged: num_ctx=8192, num_predict=2048, think=false,
temperature=0, seed=28, keep_alive=0, stream=false, original JSON Schema/system prompt.
Generation HTTP timeouts unchanged; preload uses its separate 60-second deadline.

Generation model digest:
56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90.
Only the existing synthetic Kotlin and Markdown fixtures were used.

## Observed results

| Phase | Outcome | Wall seconds | Readiness / tokens |
|---|---|---:|---|
| Preload A | done=true, done_reason=load, empty answer | 5.064 | /api/ps and ollama ps confirmed model; CONTEXT 8192; PROCESSOR 100% GPU; runner llamacpp |
| Chat A | done=true, done_reason=stop; mechanical validation PASS; exit 0 | 14.479 | prompt 663, output 429 tokens |
| Preload B | total deadline expired, TimeoutError | 60.011 | readiness not confirmed; no successful load response |
| Chat B | NOT STARTED | — | no answer/token metrics |

A readiness size=5828646010 bytes, size_vram=5828646010 bytes (CLI size 5.8 GB).
These are readiness metadata, not peak process/system memory measurements.
The preload A response did not expose load_duration/total_duration/token counters;
5.064 s is measured wall time, not a fabricated provider loading metric.

A chat provider durations: total 14.477627 s, load 0.0057044 s,
prompt evaluation 0.225745 s, output evaluation 14.238788 s.
Whole A command including diagnostic preload/readiness: 19.685 s.
Whole attempted B command including retrieval and failed preload: 61.991 s, exit 1.
B diagnostic TimeoutError arose from the explicit total preload deadline;
it is not a generation timeout or a schema-validation failure.

The run stopped immediately after preload B failed. No B chat, preload retry,
negative generation, or subsequent inference was sent. Historical/runtime/task
files and the synthetic index were hash-checked unchanged at the end of the run.

## Interpretation and review status

Explicit readiness enabled A to complete with a negligible chat load_duration in
this observation. It did not eliminate the intermittent loading problem: B preload
still failed within the authorized 60-second bound. Its internal cause was not
investigated further in this follow-up, respecting the stop condition.

This is an incomplete diagnostic A/B pair, not evidence of RAG superiority or a
confirmed fix. Semantic comparison is unavailable without B; human review remains
pending. No completed OpenSpec task was inferred from A's mechanical PASS.
Full synthetic A output was displayed in the session only; no model transcript or
private content is stored in this report. Mac validation remains PENDING / NOT TESTED.
