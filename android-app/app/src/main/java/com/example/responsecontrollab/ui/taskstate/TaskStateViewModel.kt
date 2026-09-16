package com.example.responsecontrollab.ui.taskstate

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import retrofit2.HttpException

data class TaskStateUi(val current: TaskCurrent?=null,val catalog: TaskCatalog?=null,val loaded: Boolean=false,
  val busy: Boolean=false,val recovery: Boolean=false,val error: String?=null,val dispatch: String?=null,
  val page: String="main",val message: String="",val latest: TaskObservation?=null,val note: String="")

class TaskStateViewModel(private val repository: TaskStateRepository): ViewModel() {
  private val state=MutableStateFlow(TaskStateUi())
  val uiState=state.asStateFlow()
  fun load() { if(!state.value.loaded && !state.value.busy) refresh() }
  fun refresh() {
    if(state.value.busy) return
    state.value=state.value.copy(busy=true)
    viewModelScope.launch {
      try {
        val catalog=state.value.catalog?:repository.catalog()
        val current=repository.current()
        state.value=state.value.copy(current=current,catalog=catalog,loaded=true,recovery=current.busy,
          error=if(current.busy) "Backend занят. Прочитайте состояние позже." else null)
      } catch(e: CancellationException) { throw e
      } catch(_: Exception) { state.value=state.value.copy(recovery=true,error="Не удалось прочитать backend.")
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun action(block: suspend ()->Unit) {
    if(!state.value.loaded || state.value.busy || state.value.recovery || state.value.current?.busy==true) return
    state.value=state.value.copy(busy=true,error=null,dispatch=null)
    viewModelScope.launch {
      try { block()
      } catch(e: CancellationException) { throw e
      } catch(e: Exception) {
        val body=runCatching { (e as? HttpException)?.response()?.errorBody()?.string()?.let { Json.parseToJsonElement(it).jsonObject } }.getOrNull()
        val dispatch=body?.get("dispatch")?.jsonPrimitive?.content?:"unavailable"
        val detail=if(dispatch=="not_dispatched") "Запрос отклонён до dispatch: ${body?.get("error")?.jsonPrimitive?.content}." else "Исход действия неизвестен; actual receipt unavailable."
        state.value=state.value.copy(recovery=true,error=detail,dispatch=dispatch)
        try {
          val current=repository.current()
          state.value=state.value.copy(current=current,recovery=current.busy,error="$detail Состояние перечитано без повтора действия.")
        } catch(cancel: CancellationException) { throw cancel
        } catch(_: Exception) { state.value=state.value.copy(error="$detail Нажмите «Прочитать backend».") }
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun current(c: TaskCurrent) { state.value=state.value.copy(current=c) }
  fun initialize()=action { current(repository.initialize()) }
  fun initializeState() {
    val m=state.value.current?.memory?:return
    action { current(repository.initializeState(TaskInitialize(m.snapshot_id,m.task_id))) }
  }
  fun createProfile() {
    val owner=state.value.current?.memory?.memory_owner_id?:return
    val fields=state.value.catalog?.profile?:return
    action { current(repository.create(ProfileCreate(owner,fields)).current) }
  }
  fun select(p: ProfileRecord) {
    val c=state.value.current?:return
    action { current(repository.select(p.profile_id,ProfileSelect(requireNotNull(c.memory).memory_owner_id,p.revision,requireNotNull(c.binding).revision))) }
  }
  fun write(key: String,value: String) {
    val m=state.value.current?.memory?:return
    action { current(repository.mutate(MemoryMutationRequest(m.snapshot_id,"WORKING",key,"set",value))) }
  }
  fun lifecycle(name: String) {
    val m=state.value.current?.memory?:return
    action { current(repository.lifecycle(name,MemorySnapshotRequest(m.snapshot_id))) }
  }
  fun event(event: String) {
    val c=state.value.current?.takeIf { it.ready && event in (it.task_state?.allowed_events?:emptyList()) }?:return
    action { current(repository.event(TaskEvent(c.reference(),event))) }
  }
  private fun publish(result: TaskOperation) { state.value=state.value.copy(current=result.current,latest=result.observation,note="",dispatch="dispatched") }
  fun send() {
    val u=state.value; val c=u.current?.takeIf { it.ready }?:return
    if(u.message.isBlank()) return
    action { publish(repository.send(TaskSend(c.snapshot(),u.message))); state.value=state.value.copy(message="") }
  }
  fun probe() {
    val c=state.value.current?.takeIf { it.ready }?:return
    action { publish(repository.probe(c.snapshot())) }
  }
  fun message(value: String) { state.value=state.value.copy(message=value) }
  fun page(value: String) { state.value=state.value.copy(page=value) }
  fun note(value: String) { state.value=state.value.copy(note=value) }
  companion object {
    fun factory(repo: TaskStateRepository)=object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST") override fun <T:ViewModel> create(modelClass: Class<T>): T=TaskStateViewModel(repo) as T
    }
  }
}
