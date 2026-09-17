package com.example.responsecontrollab.ui.invariants

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class InvariantsUi(val current: InvariantsCurrent?=null,val catalog: InvariantsCatalog?=null,
  val loaded: Boolean=false,val busy: Boolean=false,val recovery: Boolean=false,val error: String?=null,
  val page: String="main",val latest: InvariantObservation?=null)

class InvariantsViewModel(private val repository: InvariantsRepository): ViewModel() {
  private val state=MutableStateFlow(InvariantsUi())
  val uiState=state.asStateFlow()
  fun load() { if(!state.value.loaded && !state.value.busy) refresh() }
  private fun accept(c: InvariantsCurrent) {
    state.value=state.value.copy(current=c,recovery=c.busy || c.recovery_required)
  }
  fun refresh() {
    if(state.value.busy) return
    state.value=state.value.copy(busy=true)
    viewModelScope.launch {
      try {
        val catalog=state.value.catalog?:repository.catalog()
        accept(repository.current())
        state.value=state.value.copy(catalog=catalog,loaded=true,error=null)
      } catch(e: CancellationException) { throw e
      } catch(_: Exception) { state.value=state.value.copy(recovery=true,error="Не удалось прочитать backend. Действия не повторяются.")
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun action(block: suspend ()->Unit) {
    val u=state.value
    if(!u.loaded || u.busy || u.recovery || u.current?.busy==true) return
    state.value=u.copy(busy=true,error=null)
    viewModelScope.launch {
      try { block()
      } catch(e: CancellationException) { throw e
      } catch(e: Exception) {
        val detail=if((e as? InvariantsOperationException)?.dispatch=="not_dispatched") "Техническая ошибка до dispatch; provider не вызван." else "Техническая ошибка; исход неизвестен."
        state.value=state.value.copy(recovery=true,error="$detail Receipt этой операции недоступен.")
        try { accept(repository.current())
        } catch(e: CancellationException) { throw e
        } catch(_: Exception) { /* Explicit refresh remains available; never replay a mutation. */ }
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  fun initialize()=action { accept(repository.initialize()) }
  fun setup() {
    val c=state.value.current?:return
    if(c.memory==null) return
    action { accept(repository.setup(c.reference())) }
  }
  fun lifecycle(name: String) {
    val c=state.value.current?:return
    if(c.memory==null) return
    action { accept(repository.lifecycle(name,c.reference())) }
  }
  fun event(event: String) {
    val c=state.value.current?:return; val s=c.task_state?:return
    if(!c.ready || event !in s.allowed_events) return
    val r=c.reference()
    action { accept(repository.event(InvariantEvent(r.task_id,r.snapshot_id,s.revision,event))) }
  }
  fun propose(id: String) {
    val u=state.value; val c=u.current?.takeIf { it.can_propose }?:return
    if(u.catalog?.actions?.none { it.action_id==id }!=false) return
    action {
      val result=repository.propose(c.proposal(id))
      result.current?.let(::accept)
      state.value=state.value.copy(latest=result.observation,recovery=result.current==null || state.value.recovery,
        error=if(result.observation.turn.status=="error") "Техническая ошибка: ${result.observation.turn.error_code}. Проверьте receipt." else null)
    }
  }
  fun page(value: String) { state.value=state.value.copy(page=value) }
  companion object {
    fun factory(repo: InvariantsRepository)=object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST") override fun <T:ViewModel> create(modelClass: Class<T>): T=InvariantsViewModel(repo) as T
    }
  }
}
