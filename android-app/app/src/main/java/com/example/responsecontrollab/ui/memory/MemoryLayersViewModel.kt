package com.example.responsecontrollab.ui.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MemoryUi(
  val current: MemoryCurrent? = null, val catalog: MemoryCatalog? = null,
  val initialized: Boolean = false, val busy: Boolean = false, val recovery: Boolean = false,
  val error: String? = null, val latest: MemoryObservation? = null,
  val results: Map<String,MemoryObservation> = emptyMap(),
)

class MemoryLayersViewModel(private val repository: MemoryLayersRepository) : ViewModel() {
  private val state = MutableStateFlow(MemoryUi())
  val uiState = state.asStateFlow()
  fun load() { if(!state.value.initialized && !state.value.busy) refresh() }
  fun refresh() {
    if(state.value.busy) return
    state.value=state.value.copy(busy=true)
    viewModelScope.launch {
      try {
        val catalog=state.value.catalog ?: repository.catalog()
        val current=repository.current()
        state.value=state.value.copy(current=current,catalog=catalog,initialized=true,
          recovery=current.busy,error=if(current.busy) "Операция ещё выполняется. Прочитайте состояние позже." else null)
      } catch(e: CancellationException) { throw e
      } catch(_: Exception) { state.value=state.value.copy(recovery=true,error="Не удалось прочитать память. Повторите чтение.")
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun action(block: suspend () -> Unit) {
    if(state.value.busy || state.value.recovery || state.value.current?.busy==true) return
    state.value=state.value.copy(busy=true,error=null)
    viewModelScope.launch {
      try { block()
      } catch(e: CancellationException) { throw e
      } catch(_: Exception) {
        state.value=state.value.copy(recovery=true,error="Исход действия не подтверждён. Читаем память без повтора.")
        try {
          val current=repository.current()
          state.value=state.value.copy(current=current,recovery=current.busy,
            error="Состояние перечитано. Результат операции неизвестен; повтор возможен только явно.")
        } catch(e: CancellationException) { throw e
        } catch(_: Exception) { state.value=state.value.copy(error="Не удалось прочитать память. Повторите чтение.") }
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  fun initialize() = action { state.value=state.value.copy(current=repository.initialize()) }
  fun write(layer: String,key: String,value: String) {
    val snapshot=state.value.current?.state?.snapshot_id ?: return
    action { state.value=state.value.copy(current=repository.mutate(MemoryMutationRequest(snapshot,layer,key,"set",value))) }
  }
  fun removeArchitecture() {
    val snapshot=state.value.current?.state?.snapshot_id ?: return
    action { state.value=state.value.copy(current=repository.mutate(MemoryMutationRequest(snapshot,"WORKING","current_architecture","remove"))) }
  }
  fun transition(actionName: String) {
    val snapshot=state.value.current?.state?.snapshot_id ?: return
    action { state.value=state.value.copy(current=repository.transition(actionName,MemorySnapshotRequest(snapshot))) }
  }
  fun seed() {
    val snapshot=state.value.current?.state?.snapshot_id ?: return
    val text=state.value.catalog?.seed ?: return
    action { publish(repository.send(MemorySendRequest(snapshot,text))) }
  }
  fun verify(stage: String) {
    val snapshot=state.value.current?.state?.snapshot_id ?: return
    if(stage !in state.value.current!!.applicable_stages) return
    action { publish(repository.verify(stage,MemorySnapshotRequest(snapshot))) }
  }
  private fun publish(op: MemoryOperation) {
    state.value=state.value.copy(current=op.current,latest=op.observation,
      results=op.observation.stage?.let { state.value.results+(it to op.observation) } ?: state.value.results,
      error=op.observation.error?.let { "Ответ не завершён: $it" })
  }
  fun clearObservations() { if(!state.value.busy) state.value=state.value.copy(latest=null,results=emptyMap()) }
  companion object {
    const val KEY="day11"
    fun factory(repository: MemoryLayersRepository) = object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T:ViewModel> create(modelClass: Class<T>): T = MemoryLayersViewModel(repository) as T
    }
  }
}
