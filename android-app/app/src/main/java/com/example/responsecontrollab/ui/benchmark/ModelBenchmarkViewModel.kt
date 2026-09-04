package com.example.responsecontrollab.ui.benchmark

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.ModelBenchmarkBatchDto
import com.example.responsecontrollab.data.ModelBenchmarkCatalogDto
import com.example.responsecontrollab.data.ModelBenchmarkRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ModelBenchmarkUiState(
  val catalog: ModelBenchmarkCatalogDto? = null,
  val catalogLoading: Boolean = false,
  val catalogError: String? = null,
  val selections: Map<String, String> = emptyMap(),
  val isLoading: Boolean = false,
  val latestBatch: ModelBenchmarkBatchDto? = null,
  val runError: String? = null,
)

class ModelBenchmarkViewModel(private val repository: ModelBenchmarkRepository) : ViewModel() {
  private val state = MutableStateFlow(ModelBenchmarkUiState())
  val uiState = state.asStateFlow()
  private var catalogAttempted = false

  fun onOpen() {
    if (!catalogAttempted) loadCatalog()
  }

  fun loadCatalog() {
    if (state.value.catalogLoading || state.value.isLoading) return
    catalogAttempted = true
    state.value = state.value.copy(catalogLoading = true, catalogError = null)
    viewModelScope.launch {
      try {
        val catalog = repository.catalog()
        val previous = state.value.selections
        state.value = state.value.copy(
          catalog = catalog, catalogLoading = false,
          selections = catalog.roles.associate { role ->
            role.id to (previous[role.id]?.takeIf { it in role.allowed_model_ids } ?: role.default_model_id)
          },
        )
      } catch (cancelled: CancellationException) {
        throw cancelled
      } catch (_: Exception) {
        state.value = state.value.copy(
          catalogLoading = false,
          catalogError = "Не удалось загрузить каталог моделей. Проверьте подключение к backend.",
        )
      }
    }
  }

  fun selectModel(roleId: String, modelId: String) {
    val snapshot = state.value
    if (snapshot.isLoading || snapshot.catalogLoading) return
    val role = snapshot.catalog?.roles?.find { it.id == roleId } ?: return
    if (modelId !in role.allowed_model_ids) return
    state.value = snapshot.copy(selections = snapshot.selections + (roleId to modelId))
  }

  fun runComparison() {
    val snapshot = state.value
    val catalog = snapshot.catalog ?: return
    if (snapshot.isLoading || snapshot.catalogLoading || snapshot.catalogError != null) return
    if (catalog.roles.any { snapshot.selections[it.id] !in it.allowed_model_ids }) return
    val submitted = snapshot.selections.toMap()
    state.value = snapshot.copy(isLoading = true, runError = null)
    viewModelScope.launch {
      try {
        val batch = repository.run(submitted)
        state.value = state.value.copy(isLoading = false, latestBatch = batch)
      } catch (cancelled: CancellationException) {
        throw cancelled
      } catch (_: Exception) {
        state.value = state.value.copy(
          isLoading = false,
          runError = "Нет ответа от backend. Результат неизвестен: сервер мог обработать запрос. " +
            "Новый запуск — отдельное оплачиваемое сравнение.",
        )
      }
    }
  }

  companion object {
    fun factory(repository: ModelBenchmarkRepository): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = ModelBenchmarkViewModel(repository) as T
      }
  }
}
