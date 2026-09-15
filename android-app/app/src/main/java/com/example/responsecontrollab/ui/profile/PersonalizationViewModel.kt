package com.example.responsecontrollab.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException
import kotlinx.serialization.json.*

data class ProfileDraft(val id: String? = null,val revision: Int = 0,val name: String = "",
  val language: String = "ru",val tone: String = "technical",val verbosity: String = "concise",
  val format: String = "summary_bullets",val maxBullets: Int = 3,val noEmoji: Boolean = true,
  val skipBasics: Boolean = false,val explainTerms: Boolean = false) {
  fun fields()=ProfileFields(name.trim(),language,tone,verbosity,
    ProfileFormat(format,if(format=="summary_bullets") maxBullets else null),ProfileConstraints(noEmoji,skipBasics,explainTerms))
  companion object {
    fun from(f: ProfileFields,id: String?=null,revision: Int=0)=ProfileDraft(id,revision,f.name,f.language,f.tone,f.verbosity,
      f.response_format.kind,f.response_format.max_bullets?:3,f.constraints.no_emoji,f.constraints.skip_basic_explanations,f.constraints.explain_unfamiliar_terms)
  }
}
data class PersonalizationUi(val current: PersonalizationCurrent?=null,val catalog: ProfileCatalog?=null,
  val initialized: Boolean=false,val busy: Boolean=false,val recovery: Boolean=false,val error: String?=null,
  val page: String="main",val editorKey: Int=0,val draft: ProfileDraft=ProfileDraft(),val message: String="",
  val slots: Map<String,String> = emptyMap(),val seedReviewed: Boolean=false,
  val latest: ProfileObservation?=null,val results: Map<String,ProfileObservation> = emptyMap(),
  val inspected: ProfileObservation?=null,val notes: Map<String,String> = emptyMap())

class PersonalizationViewModel(private val repository: PersonalizationRepository): ViewModel() {
  private val state=MutableStateFlow(PersonalizationUi())
  val uiState=state.asStateFlow()
  fun load() { if(!state.value.initialized && !state.value.busy) refresh() }
  fun refresh() {
    if(state.value.busy) return
    state.value=state.value.copy(busy=true)
    viewModelScope.launch {
      try {
        val catalog=state.value.catalog?:repository.catalog()
        val current=repository.current()
        state.value=state.value.copy(current=current,catalog=catalog,initialized=true,recovery=current.busy,
          error=if(current.busy) "Операция выполняется. Прочитайте состояние позже." else null)
      } catch(e: CancellationException) { throw e
      } catch(_: Exception) { state.value=state.value.copy(recovery=true,error="Не удалось прочитать состояние.")
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun action(block: suspend ()->Unit) {
    if(state.value.busy || state.value.recovery || state.value.current?.busy==true) return
    state.value=state.value.copy(busy=true,error=null)
    viewModelScope.launch {
      try { block()
      } catch(e: CancellationException) { throw e
      } catch(failure: Exception) {
        val failureBody=runCatching { (failure as? HttpException)?.response()?.errorBody()?.string()?.let { Json.parseToJsonElement(it).jsonObject } }.getOrNull()
        val dispatch=failureBody?.get("dispatch")?.jsonPrimitive?.content
        val explanation=if(dispatch=="not_dispatched") "Assembly: not_dispatched. Backend отклонил запрос: ${failureBody?.get("error")?.jsonPrimitive?.content}." else "Исход действия неизвестен; actual receipt отсутствует."
        state.value=state.value.copy(recovery=true,error=explanation)
        try {
          val current=repository.current()
          state.value=state.value.copy(current=current,recovery=current.busy,
            error="$explanation Состояние перечитано без повтора. Проверьте изменения перед следующим действием.")
        } catch(e: CancellationException) { throw e
        } catch(_: Exception) { state.value=state.value.copy(error="Нужно повторно прочитать backend.") }
      } finally { state.value=state.value.copy(busy=false) }
    }
  }
  private fun current(c: PersonalizationCurrent) { state.value=state.value.copy(current=c) }
  fun initialize()=action { current(repository.initialize()) }
  fun page(value: String) { state.value=state.value.copy(page=value) }
  fun edit(p: ProfileRecord?=null,template: ProfileFields?=null) {
    if(state.value.busy) return
    state.value=state.value.copy(page="editor",editorKey=state.value.editorKey+1,draft=when {
      p!=null -> ProfileDraft.from(p.fields(),p.profile_id,p.revision)
      template!=null -> ProfileDraft.from(template)
      else -> ProfileDraft()
    })
  }
  fun draft(d: ProfileDraft) { if(!state.value.busy) state.value=state.value.copy(draft=d) }
  fun save() {
    val owner=state.value.current?.memory?.memory_owner_id?:return
    val draft=state.value.draft
    val fields=runCatching { draft.fields() }.getOrElse { state.value=state.value.copy(error="Имя: 1–80 символов."); return }
    action {
      val result=if(draft.id==null) repository.create(ProfileCreate(owner,fields))
        else repository.edit(draft.id,ProfileEdit(owner,fields,draft.revision))
      state.value=state.value.copy(current=result.current,page="main",draft=ProfileDraft.from(result.profile.fields(),result.profile.profile_id,result.profile.revision))
    }
  }
  fun select(p: ProfileRecord) {
    val c=state.value.current?:return
    action { current(repository.select(p.profile_id,ProfileSelect(requireNotNull(c.memory).memory_owner_id,p.revision,requireNotNull(c.binding).revision))) }
  }
  fun slot(slot: String,p: ProfileRecord) { if(!state.value.busy) state.value=state.value.copy(slots=state.value.slots+(slot to p.profile_id)) }
  fun seedReviewed(value: Boolean) { state.value=state.value.copy(seedReviewed=value) }
  fun write(layer: String,key: String,value: String) {
    val id=state.value.current?.memory?.snapshot_id?:return
    action { current(repository.mutate(MemoryMutationRequest(id,layer,key,"set",value))) }
  }
  fun transition(name: String) {
    val id=state.value.current?.memory?.snapshot_id?:return
    action { current(repository.transition(name,MemorySnapshotRequest(id))); state.value=state.value.copy(seedReviewed=false) }
  }
  private fun publish(op: ProfileOperation) {
    state.value=state.value.copy(current=op.current,latest=op.observation,
      results=op.observation.slot?.let { state.value.results+(it to op.observation) }?:state.value.results)
  }
  fun seed() {
    val s=state.value.current?.takeIf { it.active()!=null }?.snapshot()?:return
    action { publish(repository.seed(s)); state.value=state.value.copy(seedReviewed=false) }
  }
  fun freeze() {
    val u=state.value; val c=u.current?:return
    val a=c.profiles.find { it.profile_id==u.slots["A"] }?:return
    val b=c.profiles.find { it.profile_id==u.slots["B"] }?:return
    if(!u.seedReviewed || c.active()==null) return
    action { current(repository.freeze(ProfileFreeze(c.snapshot(),a,b))) }
  }
  fun probe(slot: String) {
    val c=state.value.current?:return
    val comparison=c.comparison?:return
    if(!comparison.valid || c.active()!=comparison.profiles[slot]) return
    action { publish(repository.probe(ProfileProbe(c.snapshot(),comparison.comparison_id,slot))) }
  }
  fun message(value: String) { state.value=state.value.copy(message=value) }
  fun send() {
    val u=state.value; val c=u.current?:return
    if(u.message.isBlank() || c.active()==null) return
    action { publish(repository.send(ProfileSend(c.snapshot(),u.message))); state.value=state.value.copy(message="") }
  }
  fun inspect(o: ProfileObservation) { state.value=state.value.copy(inspected=o,page="inspector") }
  fun note(id: String,value: String) { state.value=state.value.copy(notes=state.value.notes+(id to value)) }
  companion object {
    const val KEY="day12"
    fun factory(repo: PersonalizationRepository)=object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST") override fun <T:ViewModel> create(modelClass: Class<T>): T=PersonalizationViewModel(repo) as T
    }
  }
}
