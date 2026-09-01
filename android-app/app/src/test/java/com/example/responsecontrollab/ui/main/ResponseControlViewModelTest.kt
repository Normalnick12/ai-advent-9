package com.example.responsecontrollab.ui.main

import com.example.responsecontrollab.data.GenerateResponseDto
import com.example.responsecontrollab.data.GenerationControlsDto
import com.example.responsecontrollab.data.ResponseRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import java.net.SocketTimeoutException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ResponseControlViewModelTest {
  @get:Rule val mainDispatcherRule = MainDispatcherRule()

  @Test
  fun compareUsesTheExactSamePromptAndFreeHasNoControls() = runTest {
    val repository = RecordingRepository()
    val viewModel = ResponseControlViewModel(repository)
    viewModel.setMode(ResponseMode.COMPARE)
    viewModel.setPrompt("Один и тот же prompt")

    viewModel.generate()
    advanceUntilIdle()

    assertEquals(2, repository.requests.size)
    assertTrue(repository.requests.all { it.first == "Один и тот же prompt" })
    val freeControls = repository.requests.map { it.second }.first { !it.structured_output }
    assertEquals(GenerationControlsDto(), freeControls)
    assertTrue(viewModel.uiState.value.freeResult != null)
    assertTrue(viewModel.uiState.value.controlledResult != null)
    assertEquals(2, repository.maxActiveRequests)
  }

  @Test
  fun timeoutHasASeparateActionableMessage() = runTest {
    val viewModel =
      ResponseControlViewModel(
        object : ResponseRepository {
          override suspend fun generate(
            prompt: String,
            controls: GenerationControlsDto,
          ): GenerateResponseDto = throw SocketTimeoutException("timeout")
        }
      )
    viewModel.setMode(ResponseMode.FREE)

    viewModel.generate()
    advanceUntilIdle()

    val error = viewModel.uiState.value.errorMessage.orEmpty()
    assertTrue(error.startsWith("Android timeout:"))
    assertTrue(error.contains("190"))
    assertTrue(error.contains("FastAPI"))
  }

  @Test
  fun freeControlledAndCompareCanRunRepeatedly() = runTest {
    val repository = RecordingRepository()
    val viewModel = ResponseControlViewModel(repository)

    repeat(3) {
      for (mode in ResponseMode.entries) {
        viewModel.setMode(mode)
        viewModel.generate()
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value.errorMessage == null)
      }
    }

    assertEquals(12, repository.requests.size)
  }
}

private class RecordingRepository : ResponseRepository {
  val requests = mutableListOf<Pair<String, GenerationControlsDto>>()
  var activeRequests = 0
  var maxActiveRequests = 0

  override suspend fun generate(
    prompt: String,
    controls: GenerationControlsDto,
  ): GenerateResponseDto {
    requests += prompt to controls
    activeRequests += 1
    maxActiveRequests = maxOf(maxActiveRequests, activeRequests)
    delay(1)
    activeRequests -= 1
    return GenerateResponseDto(content = "ok", status = "completed", controls = controls)
  }
}
