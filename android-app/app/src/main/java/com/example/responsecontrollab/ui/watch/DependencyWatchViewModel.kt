package com.example.responsecontrollab.ui.watch

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class DependencyWatchUiState(
  val prompt: String = WATCH_CREATE_PROMPT,
  val operation: String = "create",
  val receipts: WatchReceipts = WatchReceipts(),
  val isLoading: Boolean = false,
  val result: WatchOperationDto? = null,
  val submittedRequest: WatchRequestDto? = null,
  val error: String? = null,
)

class DependencyWatchViewModel(
  private val repository: DependencyWatchRepository,
  private val receiptStore: WatchReceiptStore,
) : ViewModel() {
  private val state = MutableStateFlow(try {
    DependencyWatchUiState(receipts = receiptStore.load())
  } catch (_: Exception) { DependencyWatchUiState(error = "Не удалось прочитать сохранённые watches.") })
  val uiState = state.asStateFlow()

  fun editPrompt(value: String) { state.value = state.value.copy(prompt = value) }
  fun selectOperation(value: String) {
    require(value == "create" || value == "summary")
    if (state.value.isLoading) return
    state.value = state.value.copy(operation = value, result = null, submittedRequest = null, error = null,
      prompt = if (value == "create") WATCH_CREATE_PROMPT else WATCH_SUMMARY_PROMPT)
  }
  fun selectWatch(id: String) {
    val snapshot = state.value
    if (snapshot.isLoading || snapshot.receipts.watches.none { it.watch_id == id }) return
    val receipts = snapshot.receipts.copy(selectedId = id)
    state.value = snapshot.copy(receipts = receipts, result = null, submittedRequest = null, error = null)
    persist(receipts)
  }
  private fun persist(receipts: WatchReceipts) {
    try { receiptStore.save(receipts) }
    catch (_: Exception) { state.value = state.value.copy(error = "Не удалось сохранить watches на устройстве. ID доступны в Inspector.") }
  }

  fun send() {
    val snapshot = state.value
    if (snapshot.isLoading) return
    if (snapshot.prompt.isBlank() || (snapshot.operation == "summary" && snapshot.receipts.selectedId == null)) {
      state.value = snapshot.copy(result = null, submittedRequest = null, error = "Введите запрос и выберите watch для сводки.")
      return
    }
    // Synchronous guard precedes launch; rotation/process restore never calls send.
    state.value = snapshot.copy(isLoading = true, result = null, error = null)
    val request = WatchRequestDto(snapshot.prompt, snapshot.operation,
      if (snapshot.operation == "summary") snapshot.receipts.selectedId else null)
    state.value = state.value.copy(submittedRequest = request)
    viewModelScope.launch {
      try {
        val result = repository.run(request)
        val received = result.calls.mapNotNull { it.receipt ?: it.summary }
        val watches = snapshot.receipts.watches.associateBy { it.watch_id }.toMutableMap()
        received.forEach { watches[it.watch_id] = it }
        val selected = if (snapshot.operation == "create" && received.isNotEmpty()) received.first().watch_id
                       else snapshot.receipts.selectedId
        val receipts = WatchReceipts(watches.values.toList(), selected)
        state.value = state.value.copy(isLoading = false, result = result, receipts = receipts)
        if (received.isNotEmpty()) persist(receipts)
      } catch (cancelled: CancellationException) { throw cancelled }
      catch (_: Exception) {
        state.value = state.value.copy(isLoading = false, result = null,
          error = "Backend не вернул результат. Факт create неизвестен; повтор не выполнялся. Сохранённые watches не изменены.")
      }
    }
  }

  companion object {
    const val KEY = "day18"
    fun factory(repository: DependencyWatchRepository, store: WatchReceiptStore) = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T : ViewModel> create(modelClass: Class<T>): T = DependencyWatchViewModel(repository, store) as T
    }
  }
}
