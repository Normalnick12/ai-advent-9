package com.example.responsecontrollab.ui.reasoning

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.ReasoningLabBatchResponseDto
import com.example.responsecontrollab.data.ReasoningLabRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface ReasoningLabUiState {
  data object Idle : ReasoningLabUiState

  data object Loading : ReasoningLabUiState

  data class Content(val batch: ReasoningLabBatchResponseDto) : ReasoningLabUiState

  data class Error(val message: String) : ReasoningLabUiState
}

class ReasoningLabViewModel(private val repository: ReasoningLabRepository) : ViewModel() {
  private val _uiState = MutableStateFlow<ReasoningLabUiState>(ReasoningLabUiState.Idle)
  val uiState: StateFlow<ReasoningLabUiState> = _uiState.asStateFlow()

  fun runAllStrategies() {
    if (_uiState.value is ReasoningLabUiState.Loading) return
    _uiState.value = ReasoningLabUiState.Loading
    viewModelScope.launch {
      _uiState.value =
        runCatching { repository.run() }
          .fold(
            onSuccess = ReasoningLabUiState::Content,
            onFailure = {
              ReasoningLabUiState.Error(
                "Не удалось получить результаты лаборатории. " +
                  "Проверьте локальный backend и повторите запуск."
              )
            },
          )
    }
  }

  companion object {
    fun factory(repository: ReasoningLabRepository): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
          ReasoningLabViewModel(repository) as T
      }
  }
}
