package com.example.responsecontrollab.ui.main

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.BACKEND_CALL_TIMEOUT_SECONDS
import com.example.responsecontrollab.data.GenerateResponseDto
import com.example.responsecontrollab.data.GenerationControlsDto
import com.example.responsecontrollab.data.ResponseRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.io.InterruptedIOException
import java.net.SocketTimeoutException

enum class ResponseMode { FREE, CONTROLLED, COMPARE }

data class ResponseControlUiState(
  val prompt: String = "Составь рецепт греческого салата.",
  val mode: ResponseMode = ResponseMode.COMPARE,
  val structuredOutput: Boolean = true,
  val lengthLimit: Boolean = true,
  val maxOutputTokens: String = "600",
  val finishInstruction: Boolean = true,
  val isLoading: Boolean = false,
  val errorMessage: String? = null,
  val freeResult: GenerateResponseDto? = null,
  val controlledResult: GenerateResponseDto? = null,
)

class ResponseControlViewModel(private val repository: ResponseRepository) : ViewModel() {
  private val _uiState = MutableStateFlow(ResponseControlUiState())
  val uiState: StateFlow<ResponseControlUiState> = _uiState.asStateFlow()

  fun setPrompt(value: String) = update { copy(prompt = value) }
  fun setMode(value: ResponseMode) = update { copy(mode = value) }
  fun setStructuredOutput(value: Boolean) = update { copy(structuredOutput = value) }
  fun setLengthLimit(value: Boolean) = update { copy(lengthLimit = value) }
  fun setFinishInstruction(value: Boolean) = update { copy(finishInstruction = value) }

  fun setMaxOutputTokens(value: String) {
    if (value.all(Char::isDigit)) update { copy(maxOutputTokens = value) }
  }

  fun generate() {
    val snapshot = _uiState.value
    val prompt = snapshot.prompt
    if (prompt.isBlank()) {
      update { copy(errorMessage = "Введите запрос.") }
      return
    }
    val maxTokens =
      if (snapshot.lengthLimit) snapshot.maxOutputTokens.toIntOrNull() else null
    if (snapshot.lengthLimit && (maxTokens == null || maxTokens <= 0)) {
      update { copy(errorMessage = "max_output_tokens должен быть положительным числом.") }
      return
    }

    val controlled =
      GenerationControlsDto(
        structured_output = snapshot.structuredOutput,
        max_output_tokens = maxTokens,
        finish_instruction = snapshot.finishInstruction,
      )
    val free = GenerationControlsDto()

    viewModelScope.launch {
      update {
        copy(
          isLoading = true,
          errorMessage = null,
          freeResult = null,
          controlledResult = null,
        )
      }
      when (snapshot.mode) {
        ResponseMode.FREE -> {
          val result = runCatching { repository.generate(prompt, free) }
          finish(freeResult = result.getOrNull(), errors = listOfNotNull(result.exceptionOrNull()))
        }
        ResponseMode.CONTROLLED -> {
          val result = runCatching { repository.generate(prompt, controlled) }
          finish(
            controlledResult = result.getOrNull(),
            errors = listOfNotNull(result.exceptionOrNull()),
          )
        }
        ResponseMode.COMPARE ->
          supervisorScope {
            // Both calls deliberately receive the exact same immutable prompt snapshot.
            val freeRequest = async { runCatching { repository.generate(prompt, free) } }
            val controlledRequest = async { runCatching { repository.generate(prompt, controlled) } }
            val freeResult = freeRequest.await()
            val controlledResult = controlledRequest.await()
            finish(
              freeResult = freeResult.getOrNull(),
              controlledResult = controlledResult.getOrNull(),
              errors =
                listOfNotNull(
                  freeResult.exceptionOrNull(),
                  controlledResult.exceptionOrNull(),
                ),
            )
          }
      }
    }
  }

  private fun finish(
    freeResult: GenerateResponseDto? = null,
    controlledResult: GenerateResponseDto? = null,
    errors: List<Throwable>,
  ) {
    update {
      copy(
        isLoading = false,
        freeResult = freeResult,
        controlledResult = controlledResult,
        errorMessage = errors.takeIf { it.isNotEmpty() }?.joinToString("\n") { errorMessage(it) },
      )
    }
  }

  private fun update(block: ResponseControlUiState.() -> ResponseControlUiState) {
    _uiState.update(block)
  }

  companion object {
    fun factory(repository: ResponseRepository): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
          ResponseControlViewModel(repository) as T
      }
  }
}

private fun errorMessage(error: Throwable): String =
  when {
    error is SocketTimeoutException ||
      (error is InterruptedIOException &&
        error.message?.contains("timeout", ignoreCase = true) == true) ->
      "Время ожидания Android истекло: сервер не ответил за $BACKEND_CALL_TIMEOUT_SECONDS с. " +
        "Проверьте логи FastAPI: запрос мог продолжить выполняться на сервере."
    else -> error.message?.takeIf(String::isNotBlank) ?: error::class.java.simpleName
  }
