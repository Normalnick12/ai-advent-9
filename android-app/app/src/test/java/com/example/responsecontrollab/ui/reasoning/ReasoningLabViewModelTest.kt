package com.example.responsecontrollab.ui.reasoning

import com.example.responsecontrollab.data.ErrorInfoDto
import com.example.responsecontrollab.data.OptimizationSolutionDto
import com.example.responsecontrollab.data.ReasoningExperimentConfigDto
import com.example.responsecontrollab.data.ReasoningLabBatchResponseDto
import com.example.responsecontrollab.data.ReasoningLabRepository
import com.example.responsecontrollab.data.StrategyResultDto
import com.example.responsecontrollab.data.TokenUsageDto
import com.example.responsecontrollab.data.VerificationDetailsDto
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ReasoningLabViewModelTest {
  @get:Rule val mainDispatcherRule = MainDispatcherRule()

  @Test
  fun initialStateIsIdle() {
    val viewModel = ReasoningLabViewModel(FakeReasoningLabRepository())

    assertTrue(viewModel.uiState.value is ReasoningLabUiState.Idle)
  }

  @Test
  fun oneBatchPerTapAndDuplicateLaunchIsBlockedWhileLoading() = runTest {
    val gate = CompletableDeferred<Unit>()
    val repository = FakeReasoningLabRepository(gate = gate)
    val viewModel = ReasoningLabViewModel(repository)

    viewModel.runAllStrategies()
    viewModel.runAllStrategies()
    runCurrent()

    assertEquals(1, repository.callCount)
    assertTrue(viewModel.uiState.value is ReasoningLabUiState.Loading)

    gate.complete(Unit)
    advanceUntilIdle()
    assertTrue(viewModel.uiState.value is ReasoningLabUiState.Content)
  }

  @Test
  fun successfulBatchBecomesContent() = runTest {
    val viewModel = ReasoningLabViewModel(FakeReasoningLabRepository())

    viewModel.runAllStrategies()
    advanceUntilIdle()

    val state = viewModel.uiState.value as ReasoningLabUiState.Content
    assertEquals(4, state.batch.results.size)
  }

  @Test
  fun transportFailureBecomesRussianErrorState() = runTest {
    val viewModel =
      ReasoningLabViewModel(
        FakeReasoningLabRepository(failure = IllegalStateException("Backend недоступен."))
      )

    viewModel.runAllStrategies()
    advanceUntilIdle()

    val state = viewModel.uiState.value as ReasoningLabUiState.Error
    assertEquals(
      "Не удалось получить результаты лаборатории. " +
        "Проверьте локальный backend и повторите запуск.",
      state.message,
    )
  }

  @Test
  fun partialStrategyErrorPreservesSuccessfulCardsInContent() = runTest {
    val partial = batchResponse(partialFailure = true)
    val viewModel = ReasoningLabViewModel(FakeReasoningLabRepository(response = partial))

    viewModel.runAllStrategies()
    advanceUntilIdle()

    val state = viewModel.uiState.value as ReasoningLabUiState.Content
    assertEquals(3, state.batch.results.count(StrategyResultDto::correct))
    assertEquals(
      "openai_upstream_error",
      state.batch.results.single { !it.correct }.error?.code,
    )
  }
}

private class FakeReasoningLabRepository(
  private val response: ReasoningLabBatchResponseDto = batchResponse(),
  private val failure: Throwable? = null,
  private val gate: CompletableDeferred<Unit>? = null,
) : ReasoningLabRepository {
  var callCount = 0

  override suspend fun run(): ReasoningLabBatchResponseDto {
    callCount += 1
    gate?.await()
    failure?.let { throw it }
    return response
  }
}

private fun batchResponse(partialFailure: Boolean = false): ReasoningLabBatchResponseDto {
  val solution =
    OptimizationSolutionDto(
      selected_features = listOf("A", "C", "F", "G"),
      total_cost = 15,
      total_value = 29,
      explanation = "Проверено.",
    )
  val validVerification =
    VerificationDetailsDto(
      feasible = true,
      optimal = true,
      totals_match = true,
      calculated_cost = 15,
      calculated_value = 29,
      violations = emptyList(),
    )
  val usage = TokenUsageDto(10, 8, 3, 18)
  val strategyNames =
    listOf(
      "DIRECT" to "Прямой ответ",
      "STEP_BY_STEP" to "Пошаговое решение",
      "META_PROMPT" to "Мета-промпт",
      "EXPERT_PANEL" to "Группа экспертов",
    )
  return ReasoningLabBatchResponseDto(
    request_id = "request-1",
    config =
      ReasoningExperimentConfigDto(
        model = "gpt-5.6",
        reasoning_effort = "medium",
        reasoning_mode = "standard",
        max_output_tokens = 1200,
        prompt_cache_mode = "explicit",
        story_point_limit = 15,
      ),
    reference_solution = solution,
    results =
      strategyNames.mapIndexed { index, (strategy, name) ->
        val failed = partialFailure && index == 1
        StrategyResultDto(
          strategy = strategy,
          display_name = name,
          correct = !failed,
          latency_ms = 100,
          usage = usage,
          api_call_count = if (strategy == "META_PROMPT") 2 else 1,
          solution = solution.takeUnless { failed },
          verification =
            if (failed) {
              VerificationDetailsDto(false, false, false, 0, 0, listOf("Ошибка стратегии."))
            } else {
              validVerification
            },
          error =
            if (failed) {
              ErrorInfoDto("openai_upstream_error", "OpenAI временно недоступен.")
            } else {
              null
            },
          generated_prompt =
            "Проверь полный перебор.".takeIf { strategy == "META_PROMPT" },
        )
      },
  )
}
