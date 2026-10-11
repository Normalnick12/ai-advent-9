# Model lifecycle experiment — 2026-10-10

Separate authorized diagnostic observation. Original results in validation.md and
diagnostic-followup-2026-10-10.md are preserved. Only synthetic fixtures were used.
No product configuration, runtime code, OpenSpec tasks or historical reports changed.

## Method and preparation

B vector retrieval completed before generation-model loading in 1.667 s.
The four chunks, their order, source coordinates and contents matched the prior
experiment. The original A/B request settings were checked against common-request
SHA256 bc24177e3b98102f829e524c8f3ad626dbd95a3f93f4ddd4e7e7f29e66ee44eb.

The only planned generation-request change was keep_alive from 0 to "5m", applied
to in-memory payloads. No generation request was ultimately sent.
Model=qwen3.5:9b-q4_K_M; num_ctx=8192; num_predict=2048; think=false;
temperature=0; seed=28; stream=false; original prompts and JSON Schema retained.
The installed generation model digest matched the prior experiment:
56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90.

| Prepared request | Original bytes | Experiment bytes | Markdown chunks |
|---|---:|---:|---:|
| A, retrieval none | 5249 | 5252 | 0 |
| B, retrieval vector | 7172 | 7175 | 4 |

Original serialized request SHA256:

- A: b8b3ebf711bb850bd9dc6d369276ec1469bee9bd1b4f2fab2b5752beac9cadd5
- B: 7e10edc694bb765f50eb2ba97af4cfe3ecc4b03a5ed3e75b9fa3f73f20e15d8a

Prepared request SHA256 with keep_alive="5m":

- A: ef85635b55b7c8c0d21715a4a799d8b19828a9c911efb1af98ad3213162ec2a0
- B: a83c24c455830bc641bd4d82e31770e1ead9827a7786615e9638e5ac0ea94ce1

B chunk IDs, in rank order:

1. b0bb20296059355b10f7abd06586ff3f9f7d3a6b1dddf120ea2d8debfa76a2ad
2. d976469719ed61e702ad877789bba84a3e6110c9c16cdf1935fbf82efc7b3f2c
3. 75fae67eafeedf18a58947896c96a46a7c2efcd2875d1c6dcae1202a603bf59e
4. aab11966297f308ecd65f63f48d6e27760936d4f1aeda7d98f117dddcaa54aa7

One local Ollama load-only POST /api/chat was attempted with messages=[],
model=qwen3.5:9b-q4_K_M, stream=false, options.num_ctx=8192, keep_alive="5m".
An asyncio total deadline limited this preload to 60 seconds. No user answer was
requested. On successful preload, readiness checks and sequential A/B would follow;
the stop-on-error condition prevented those steps.

## Observed result

| Stage | Outcome | Wall seconds | Readiness / token metrics |
|---|---|---:|---|
| Prepare B retrieval | PASS, identical selected chunks | 1.667 | 4 chunks |
| Initial load-only | TimeoutError at total deadline | 60.009 | no successful load response or provider duration counters |
| Runner readiness | NOT REACHED | — | actual CONTEXT and PROCESSOR not confirmed in this run |
| Chat A | NOT STARTED | — | no answer or token metrics |
| State before B / Chat B | NOT REACHED / NOT STARTED | — | no answer or token metrics |

The script stopped at phase=preload with retry=false. No second preload, A/B chat,
negative scenario or subsequent inference was sent. Hash verification confirmed
the pre-existing runtime, OpenSpec reports/tasks and synthetic index unchanged.

## Interpretation

This run did not reach the A-to-B lifecycle transition and cannot establish whether
keeping the generation model resident would prevent the previously observed second
load failure. The confirmed failure is expiration of the initial preload deadline;
the internal server stage and underlying cause were not established in this run.
No conclusion about memory exhaustion, queueing, cancellation completion or RAG
answer quality follows from this result. No answers exist for semantic review.

Further retries stopped as requested. No timeout increase, model substitution,
commit/push, archive or video. Human review and other pending validation remain pending.
