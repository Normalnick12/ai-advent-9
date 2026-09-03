package com.example.responsecontrollab.ui.temperature

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.CANONICAL_TEMPERATURE_PROMPT
import com.example.responsecontrollab.data.TemperatureLabBatchResponseDto
import com.example.responsecontrollab.data.TemperatureLabRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class UniqueNameAggregate(
  val temperature: Double,
  val uniqueCount: Int,
  val totalGenerated: Int,
)

data class TemperatureLabUiState(
  val prompt: String = CANONICAL_TEMPERATURE_PROMPT,
  val isLoading: Boolean = false,
  val latestBatch: TemperatureLabBatchResponseDto? = null,
  val errorMessage: String? = null,
  val history: List<TemperatureLabBatchResponseDto> = emptyList(),
  val uniqueNames: List<UniqueNameAggregate> = emptyAggregates(),
) {
  val isBenchmarkPrompt: Boolean
    get() = prompt == CANONICAL_TEMPERATURE_PROMPT
}

private data class MutableUniqueNames(
  val names: MutableSet<String> = linkedSetOf(),
  var totalGenerated: Int = 0,
)

class TemperatureLabViewModel(private val repository: TemperatureLabRepository) : ViewModel() {
  private val _uiState = MutableStateFlow(TemperatureLabUiState())
  val uiState: StateFlow<TemperatureLabUiState> = _uiState.asStateFlow()

  private var historyPrompt: String? = null
  private var history: List<TemperatureLabBatchResponseDto> = emptyList()
  private val uniqueByTemperature =
    linkedMapOf(
      0.0 to MutableUniqueNames(),
      0.7 to MutableUniqueNames(),
      1.2 to MutableUniqueNames(),
    )

  fun editPrompt(prompt: String) {
    val visibleHistory = history.takeIf { prompt == historyPrompt }.orEmpty()
    val latest = visibleHistory.firstOrNull()
    _uiState.value =
      _uiState.value.copy(
        prompt = prompt,
        latestBatch = latest,
        errorMessage = null,
        history = visibleHistory,
      )
  }

  fun restoreBenchmark() = editPrompt(CANONICAL_TEMPERATURE_PROMPT)

  fun runComparison() {
    val snapshot = _uiState.value
    if (snapshot.isLoading) return
    if (snapshot.prompt.isEmpty()) {
      _uiState.value = snapshot.copy(errorMessage = "Введите запрос для сравнения.")
      return
    }

    val submittedPrompt = snapshot.prompt
    _uiState.value = snapshot.copy(isLoading = true, errorMessage = null)
    viewModelScope.launch {
      runCatching { repository.run(submittedPrompt) }
        .onSuccess { batch -> acceptBatch(submittedPrompt, batch) }
        .onFailure {
          _uiState.value =
            _uiState.value.copy(
              isLoading = false,
              errorMessage =
                "Не удалось получить результаты. Проверьте локальный backend и повторите запуск.",
            )
        }
    }
  }

  private fun acceptBatch(prompt: String, batch: TemperatureLabBatchResponseDto) {
    if (historyPrompt != prompt) {
      historyPrompt = prompt
      history = emptyList()
    }
    history = (listOf(batch) + history).take(MAX_HISTORY_RUNS)
    if (batch.mode == BENCHMARK_MODE) {
      batch.results.forEach { result ->
        val accumulator = uniqueByTemperature[result.temperature] ?: return@forEach
        val variants = result.variants ?: return@forEach
        accumulator.totalGenerated += variants.size
        accumulator.names += variants.map { it.normalized_name }
      }
    }
    _uiState.value =
      _uiState.value.copy(
        isLoading = false,
        latestBatch = batch,
        errorMessage = null,
        history = history,
        uniqueNames = aggregateSnapshot(),
      )
  }

  private fun aggregateSnapshot(): List<UniqueNameAggregate> =
    uniqueByTemperature.map { (temperature, value) ->
      UniqueNameAggregate(
        temperature = temperature,
        uniqueCount = value.names.size,
        totalGenerated = value.totalGenerated,
      )
    }

  companion object {
    private const val MAX_HISTORY_RUNS = 3
    private const val BENCHMARK_MODE = "benchmark"

    fun factory(repository: TemperatureLabRepository): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
          TemperatureLabViewModel(repository) as T
      }
  }
}

private fun emptyAggregates(): List<UniqueNameAggregate> =
  listOf(0.0, 0.7, 1.2).map { UniqueNameAggregate(it, 0, 0) }
