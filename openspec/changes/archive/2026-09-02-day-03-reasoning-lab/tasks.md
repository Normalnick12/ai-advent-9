## 1. Backend domain and contracts

- [x] 1.1 Add immutable Day 03 benchmark data plus canonical task rendering, and verify a unit test sees all eight features, four constraints and the 15-point limit.
- [x] 1.2 Implement exhaustive `2^8` solver and deterministic verifier, and verify unit tests cover the unique A+C+F+G optimum, every constraint, suboptimal sets, duplicates, unknown ids and mismatched reported totals.
- [x] 1.3 Add strict Pydantic request/response models for experiment config, solution, verification, usage, per-strategy result and batch response, and verify model tests reject extra fields and serialize all required metrics.

## 2. OpenAI strategy execution

- [x] 2.1 Add the shared `gpt-5.6` Responses API envelope, common strict solution JSON Schema and isolated meta-prompt schema, and verify mocked SDK tests assert medium effort, 1200 token limit, standard mode, disabled storage/cache, 75-second timeout and zero retries.
- [x] 2.2 Implement DIRECT, STEP_BY_STEP and single-call role-prompted EXPERT_PANEL builders/execution, and verify tests prove identical canonical task/schema plus only the intended strategy instruction and `api_call_count=1`.
- [x] 2.3 Implement two-call META_PROMPT execution without `previous_response_id`, and verify tests prove the generated instruction is used with the unchanged canonical task, exposed in the result, and both calls use the fixed envelope.
- [x] 2.4 Normalize completed, incomplete, parse, timeout and upstream responses into safe per-strategy results, and verify tests cover token breakdown, verification reasons and prompt/secret-free errors.
- [x] 2.5 Run four strategy pipelines concurrently with sequential META_PROMPT calls and aggregate monotonic latency, usage and actual call count, and verify a partial-failure test preserves the other three results in stable order.

## 3. FastAPI integration

- [x] 3.1 Add `POST /api/v1/reasoning-lab/run` with dependency-injected service and request id handling while leaving `/api/v1/generate` unchanged, and verify API tests cover successful and partial-failure batch contracts plus the existing Day 02 endpoint regression.
- [x] 3.2 Add safe structured logging for batch/strategy start, duration and status without prompts or credentials, and verify captured logs contain request/strategy ids but no canonical or generated prompt text.

## 4. Android data and state

- [x] 4.1 Add kotlinx.serialization DTOs, Retrofit endpoint and Reasoning Lab repository while sharing the existing Retrofit/OkHttp instance in `AppContainer`, and verify serialization/repository tests parse all four strategy results and never define an API-key field.
- [x] 4.2 Add a constructor-injected Reasoning Lab ViewModel with explicit idle/loading/content/error state, and verify coroutine tests cover one batch request per tap, disabled duplicate launch, successful content, transport error and partial strategy errors.

## 5. Android Material 3 UI

- [x] 5.1 Add simple root navigation between the existing response-control screen and «Лаборатория рассуждений» without a new Android module or navigation dependency, and verify both destinations render and the existing Day 02 ViewModel tests still pass.
- [x] 5.2 Build the vertically scrollable Reasoning Lab screen with the fixed-task summary, full-width «Запустить все стратегии» button, loading state and cards named «Прямой ответ», «Пошаговое решение», «Мета-промпт» and «Группа экспертов», and verify all user-facing labels and messages are Russian.
- [x] 5.3 Render solution, latency, token usage, API call count and prominent «Правильно»/«Неправильно» status per card, and verify a Compose/manual phone-size check keeps all fields readable and preserves successful cards during a partial failure.
- [x] 5.4 Add expandable selectable generated-prompt content only to the «Мета-промпт» card, and verify expand/collapse behavior with a UI test or documented emulator smoke check.

## 6. Documentation and verification

- [x] 6.1 Create `day-03-reasoning-strategies/README.md` with goal, fixed configuration, expected optimum, architecture, environment setup, run commands, API example and checks; update relevant root/backend/Android README links and verify no real secret is present.
- [x] 6.2 Run the complete backend test suite and verify `python -m pytest` passes with no live OpenAI dependency.
- [x] 6.3 Run Android unit tests and debug assembly and verify `gradlew.bat testDebugUnitTest assembleDebug` succeeds with the existing single `app` module.
- [x] 6.4 With a locally supplied `OPENAI_API_KEY`, run one end-to-end emulator batch and verify four localized cards, deterministic correctness, META_PROMPT call count 2 and generated-prompt expansion; if the key is unavailable, record that only mocked integration was executed.
- [x] 6.5 Review `git diff`/`git status`, verify Day 01 files and Day 02 public behavior remain intact, scan changed files for secrets/local artifacts, and leave commit/push to an explicit completion request.
