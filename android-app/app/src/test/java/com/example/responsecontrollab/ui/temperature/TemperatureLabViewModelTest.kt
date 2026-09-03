package com.example.responsecontrollab.ui.temperature

import com.example.responsecontrollab.data.BenchmarkValidationDto
import com.example.responsecontrollab.data.CANONICAL_TEMPERATURE_PROMPT
import com.example.responsecontrollab.data.ErrorInfoDto
import com.example.responsecontrollab.data.TemperatureExperimentConfigDto
import com.example.responsecontrollab.data.TemperatureLabBatchResponseDto
import com.example.responsecontrollab.data.TemperatureLabRepository
import com.example.responsecontrollab.data.TemperatureResultDto
import com.example.responsecontrollab.data.TemperatureVariantDto
import com.example.responsecontrollab.data.TokenUsageDto
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TemperatureLabViewModelTest {
  @get:Rule val mainDispatcherRule = MainDispatcherRule()

  @Test
  fun initialStateUsesExactBenchmarkAndIsSessionEmpty() {
    val state = TemperatureLabViewModel(FakeTemperatureLabRepository()).uiState.value

    assertEquals(CANONICAL_TEMPERATURE_PROMPT, state.prompt)
    assertTrue(state.isBenchmarkPrompt)
    assertTrue(state.history.isEmpty())
    assertNull(state.latestBatch)
    assertEquals(listOf(0, 0, 0), state.uniqueNames.map { it.totalGenerated })
  }

  @Test
  fun oneRequestPerTapKeepsExactPromptAndBlocksDuplicateLaunch() = runTest {
    val gate = CompletableDeferred<Unit>()
    val repository = FakeTemperatureLabRepository(gate = gate)
    val viewModel = TemperatureLabViewModel(repository)

    viewModel.runComparison()
    viewModel.runComparison()
    runCurrent()

    assertEquals(listOf(CANONICAL_TEMPERATURE_PROMPT), repository.prompts)
    assertTrue(viewModel.uiState.value.isLoading)
    gate.complete(Unit)
    advanceUntilIdle()
    assertFalse(viewModel.uiState.value.isLoading)
  }

  @Test
  fun emptyInputDoesNotCallRepositoryAndRestoreIsExact() {
    val repository = FakeTemperatureLabRepository()
    val viewModel = TemperatureLabViewModel(repository)

    viewModel.editPrompt("")
    viewModel.runComparison()
    assertTrue(viewModel.uiState.value.errorMessage?.startsWith("Введите") == true)
    assertTrue(repository.prompts.isEmpty())

    viewModel.restoreBenchmark()
    assertEquals(CANONICAL_TEMPERATURE_PROMPT, viewModel.uiState.value.prompt)
  }

  @Test
  fun partialBatchRemainsVisible() = runTest {
    val batch = batchResponse("partial", partialFailure = true)
    val viewModel = TemperatureLabViewModel(FakeTemperatureLabRepository(responses = mutableListOf(batch)))

    viewModel.runComparison()
    advanceUntilIdle()

    val results = viewModel.uiState.value.latestBatch?.results.orEmpty()
    assertEquals(listOf("completed", "error", "completed"), results.map { it.status })
    assertEquals("openai_upstream_error", results[1].error?.code)
  }

  @Test
  fun historyIsNewestFirstLimitedAndScopedToExactPrompt() = runTest {
    val repository =
      FakeTemperatureLabRepository(
        responses = (1..5).map { batchResponse("run-$it") }.toMutableList()
      )
    val viewModel = TemperatureLabViewModel(repository)

    repeat(4) {
      viewModel.runComparison()
      advanceUntilIdle()
    }
    assertEquals(listOf("run-4", "run-3", "run-2"), viewModel.uiState.value.history.map { it.request_id })

    viewModel.editPrompt("Свободный запрос")
    assertTrue(viewModel.uiState.value.history.isEmpty())
    assertNull(viewModel.uiState.value.latestBatch)
    viewModel.runComparison()
    advanceUntilIdle()
    assertEquals(listOf("run-5"), viewModel.uiState.value.history.map { it.request_id })
  }

  @Test
  fun transportFailurePreservesCurrentPromptHistory() = runTest {
    val repository = FakeTemperatureLabRepository()
    val viewModel = TemperatureLabViewModel(repository)
    viewModel.runComparison()
    advanceUntilIdle()
    repository.failure = IllegalStateException("offline")

    viewModel.runComparison()
    advanceUntilIdle()

    assertEquals(1, viewModel.uiState.value.history.size)
    assertTrue(viewModel.uiState.value.errorMessage?.contains("backend") == true)
  }

  @Test
  fun benchmarkUniqueNamesOutliveHistoryAndAreIndependentByTemperature() = runTest {
    val repository = FakeTemperatureLabRepository()
    val viewModel = TemperatureLabViewModel(repository)

    repeat(4) {
      viewModel.runComparison()
      advanceUntilIdle()
    }

    val aggregates = viewModel.uiState.value.uniqueNames.associateBy { it.temperature }
    assertEquals(3, viewModel.uiState.value.history.size)
    assertEquals(1, aggregates.getValue(0.0).uniqueCount)
    assertEquals(4, aggregates.getValue(0.0).totalGenerated)
    assertEquals(1, aggregates.getValue(0.7).uniqueCount)
    assertEquals(4, aggregates.getValue(0.7).totalGenerated)
    assertEquals(1, aggregates.getValue(1.2).uniqueCount)
    assertEquals(4, aggregates.getValue(1.2).totalGenerated)
  }

  @Test
  fun freeModeDoesNotChangeBenchmarkAggregates() = runTest {
    val repository = FakeTemperatureLabRepository()
    val viewModel = TemperatureLabViewModel(repository)
    viewModel.runComparison()
    advanceUntilIdle()
    val before = viewModel.uiState.value.uniqueNames

    viewModel.editPrompt("Свободный запрос")
    repository.responses += batchResponse("free", mode = "free")
    viewModel.runComparison()
    advanceUntilIdle()

    assertFalse(viewModel.uiState.value.isBenchmarkPrompt)
    assertEquals(before, viewModel.uiState.value.uniqueNames)
  }
}

private class FakeTemperatureLabRepository(
  val responses: MutableList<TemperatureLabBatchResponseDto> = mutableListOf(),
  var failure: Throwable? = null,
  private val gate: CompletableDeferred<Unit>? = null,
) : TemperatureLabRepository {
  val prompts = mutableListOf<String>()
  private var counter = 0

  override suspend fun run(prompt: String): TemperatureLabBatchResponseDto {
    prompts += prompt
    gate?.await()
    failure?.let { throw it }
    return if (responses.isNotEmpty()) responses.removeAt(0) else batchResponse("run-${++counter}")
  }
}

private fun batchResponse(
  requestId: String,
  mode: String = "benchmark",
  partialFailure: Boolean = false,
): TemperatureLabBatchResponseDto {
  val usage = TokenUsageDto(10, 20, 0, 30)
  val temperatures = listOf(0.0, 0.7, 1.2)
  return TemperatureLabBatchResponseDto(
    request_id = requestId,
    mode = mode,
    mode_message = if (mode == "benchmark") "Benchmark-режим" else "Автопроверка недоступна",
    config =
      TemperatureExperimentConfigDto(
        model = "gpt-5.6",
        temperatures = temperatures,
        reasoning_effort = "none",
        reasoning_mode = "standard",
        max_output_tokens = 600,
        top_p = "default",
        prompt_cache_mode = "explicit",
        output_contract = if (mode == "benchmark") "strict_variants" else "text",
        temperature_only_variable = true,
      ),
    results =
      temperatures.mapIndexed { index, temperature ->
        val failed = partialFailure && index == 1
        TemperatureResultDto(
          temperature = temperature,
          status = if (failed) "error" else "completed",
          latency_ms = 100L + index,
          usage = if (failed) TokenUsageDto(0, 0, 0, 0) else usage,
          variants =
            if (mode == "benchmark" && !failed) {
              listOf(
                TemperatureVariantDto(
                  name = "Одинаковое имя",
                  slogan = "Короткий слоган",
                  normalized_name = "одинаковое имя",
                )
              )
            } else {
              null
            },
          content = "Свободный ответ".takeIf { mode == "free" && !failed },
          validation =
            BenchmarkValidationDto(5, 5, emptyList()).takeIf {
              mode == "benchmark" && !failed
            },
          error = ErrorInfoDto("openai_upstream_error", "OpenAI недоступен.").takeIf { failed },
        )
      },
  )
}
