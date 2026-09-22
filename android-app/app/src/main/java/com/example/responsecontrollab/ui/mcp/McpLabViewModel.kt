package com.example.responsecontrollab.ui.mcp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.MCP_DEFAULT_PROMPT
import com.example.responsecontrollab.data.McpLabOperationDto
import com.example.responsecontrollab.data.McpLabRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class McpLabUiState(
  val prompt: String = MCP_DEFAULT_PROMPT,
  val mode: String = "forced",
  val isLoading: Boolean = false,
  val submittedPrompt: String? = null,
  val submittedMode: String? = null,
  val result: McpLabOperationDto? = null,
  val error: String? = null,
)

class McpLabViewModel(private val repository: McpLabRepository) : ViewModel() {
  private val state = MutableStateFlow(McpLabUiState())
  val uiState = state.asStateFlow()

  fun editPrompt(value: String) { state.value = state.value.copy(prompt = value) }
  fun selectMode(value: String) {
    require(value == "forced" || value == "auto")
    state.value = state.value.copy(mode = value)
  }

  fun send() {
    val snapshot = state.value
    if (snapshot.isLoading) return
    if (snapshot.prompt.isBlank()) {
      state.value = snapshot.copy(result = null, submittedPrompt = snapshot.prompt,
        submittedMode = snapshot.mode, error = "Введите запрос.")
      return
    }
    state.value = snapshot.copy(isLoading = true, submittedPrompt = snapshot.prompt,
      submittedMode = snapshot.mode, result = null, error = null)
    viewModelScope.launch {
      try {
        val result = repository.run(snapshot.prompt, snapshot.mode)
        state.value = state.value.copy(isLoading = false, result = result)
      } catch (cancelled: CancellationException) {
        throw cancelled
      } catch (_: Exception) {
        state.value = state.value.copy(isLoading = false, result = null,
          error = "Backend не вернул результат. Факт MCP-вызова неизвестен; повтор не выполнялся.")
      }
    }
  }

  companion object {
    const val KEY = "day17"
    fun factory(repository: McpLabRepository): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T : ViewModel> create(modelClass: Class<T>): T = McpLabViewModel(repository) as T
    }
  }
}
