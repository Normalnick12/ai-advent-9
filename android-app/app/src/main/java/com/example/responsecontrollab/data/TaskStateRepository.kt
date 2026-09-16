package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.*
import java.util.UUID

@Serializable data class TaskStateRecord(val task_id: String, val machine_id: String, val state_id: String,
  val status: String, val revision: Int) {
  fun valid() { require(UUID.fromString(task_id).toString()==task_id); require(machine_id.matches(Regex("[a-z][a-z0-9-]*-v[1-9][0-9]*")))
    require(state_id.matches(Regex("[A-Z][A-Z0-9_]*")) && status in listOf("ACTIVE","PAUSED") && revision>=0) }
}
@Serializable data class TaskStateView(val task_id: String, val machine_id: String, val state_id: String,
  val status: String, val revision: Int, val phase: String, val step: String, val expected_action: String,
  val is_terminal: Boolean, val allowed_events: List<String>) {
  fun record()=TaskStateRecord(task_id,machine_id,state_id,status,revision)
}
@Serializable data class TaskReadiness(val memory_ready: Boolean, val profile_ready: Boolean, val task_state_ready: Boolean)
@Serializable data class TaskTransition(val task_id: String, val event: String, val before: TaskStateRecord, val after: TaskStateRecord)
@Serializable data class TaskCurrent(val memory: MemoryStateDto?=null, val profiles: List<ProfileRecord> = emptyList(),
  val binding: ProfileBinding?=null, val task_state: TaskStateView?=null, val state_error: String?=null,
  val readiness: TaskReadiness, val ready: Boolean, val busy: Boolean=false, val generation_calls: Int=0,
  val preview: MemorySelection?=null, val last_transition: TaskTransition?=null) {
  fun active()=profiles.find { it.profile_id==binding?.active_profile_id }
  fun reference()=TaskReference(requireNotNull(memory).snapshot_id,memory.task_id,requireNotNull(task_state).revision)
  fun snapshot()=TaskRequestSnapshot(requireNotNull(memory).snapshot_id,memory.task_id,requireNotNull(task_state).revision,
    requireNotNull(active()).profile_id,requireNotNull(active()).revision,requireNotNull(binding).revision)
}
@Serializable data class TaskCatalog(val working: Map<String,String>, val profile: ProfileFields, val query: String, val execution_query: String)
@Serializable data class TaskReference(val snapshot_id: String, val task_id: String, val state_revision: Int)
@Serializable data class TaskInitialize(val snapshot_id: String, val task_id: String, val machine_id: String="checkout-v1")
@Serializable data class TaskEvent(val snapshot_id: String, val task_id: String, val state_revision: Int, val event: String) {
  constructor(r: TaskReference,event: String):this(r.snapshot_id,r.task_id,r.state_revision,event)
}
@Serializable data class TaskRequestSnapshot(val snapshot_id: String, val task_id: String, val state_revision: Int,
  val profile_id: String, val profile_revision: Int, val binding_revision: Int)
@Serializable data class TaskSend(val snapshot_id: String, val task_id: String, val state_revision: Int,
  val profile_id: String, val profile_revision: Int, val binding_revision: Int, val message: String) {
  constructor(s: TaskRequestSnapshot,message: String):this(s.snapshot_id,s.task_id,s.state_revision,s.profile_id,s.profile_revision,s.binding_revision,message)
  fun snapshot()=TaskRequestSnapshot(snapshot_id,task_id,state_revision,profile_id,profile_revision,binding_revision)
}
@Serializable data class TaskAdherence(val status: String, val detail: String)
@Serializable data class TaskObservation(val attempt_id: String, val mode: String, val memory: MemoryStateDto,
  val profile: ProfileRecord, val binding: ProfileBinding, val stored_state: TaskStateRecord, val selected_state: TaskStateView,
  val selection: MemorySelection, val profile_section: String, val state_section: String,
  val profile_template: String, val state_template: String, val request: ProfileRequestEvidence,
  val query: String, val outcome: ProfileOutcome, val conversation_committed: Boolean,
  val storage_checks: Map<String,ProfileCheck>, val selection_checks: Map<String,ProfileCheck>,
  val assembly_checks: Map<String,ProfileCheck>, val model_adherence: TaskAdherence)
@Serializable data class TaskOperation(val current: TaskCurrent, val observation: TaskObservation)
@Serializable data class TaskProfileSaved(val current: TaskCurrent, val profile: ProfileRecord)

interface TaskStateApi {
  @GET("api/v1/task-state/current") suspend fun current(): TaskCurrent
  @GET("api/v1/task-state/scenario") suspend fun catalog(): TaskCatalog
  @POST("api/v1/task-state/initialize") suspend fun initialize(@Body body: Map<String,String>): TaskCurrent
  @POST("api/v1/task-state/initialize-state") suspend fun initializeState(@Body body: TaskInitialize): TaskCurrent
  @POST("api/v1/task-state/profiles") suspend fun create(@Body body: ProfileCreate): TaskProfileSaved
  @POST("api/v1/task-state/profiles/{id}/select") suspend fun select(@Path("id") id: String,@Body body: ProfileSelect): TaskCurrent
  @POST("api/v1/task-state/memory") suspend fun mutate(@Body body: MemoryMutationRequest): TaskCurrent
  @POST("api/v1/task-state/lifecycle/{action}") suspend fun lifecycle(@Path("action") action: String,@Body body: MemorySnapshotRequest): TaskCurrent
  @POST("api/v1/task-state/events") suspend fun event(@Body body: TaskEvent): TaskCurrent
  @POST("api/v1/task-state/messages") suspend fun send(@Body body: TaskSend): TaskOperation
  @POST("api/v1/task-state/probe") suspend fun probe(@Body body: TaskRequestSnapshot): TaskOperation
}
interface TaskStateRepository {
  suspend fun current(): TaskCurrent
  suspend fun catalog(): TaskCatalog
  suspend fun initialize(): TaskCurrent
  suspend fun initializeState(body: TaskInitialize): TaskCurrent
  suspend fun create(body: ProfileCreate): TaskProfileSaved
  suspend fun select(id: String,body: ProfileSelect): TaskCurrent
  suspend fun mutate(body: MemoryMutationRequest): TaskCurrent
  suspend fun lifecycle(action: String,body: MemorySnapshotRequest): TaskCurrent
  suspend fun event(body: TaskEvent): TaskCurrent
  suspend fun send(body: TaskSend): TaskOperation
  suspend fun probe(body: TaskRequestSnapshot): TaskOperation
}
class DefaultTaskStateRepository(private val api: TaskStateApi): TaskStateRepository {
  private fun uuid(id: String) { require(UUID.fromString(id).toString()==id) }
  private fun TaskCurrent.valid()=apply {
    require(generation_calls>=0)
    memory?.let { m ->
      listOf(m.memory_owner_id,m.task_id,m.session_id).forEach(::uuid)
      require(m.snapshot_id.matches(Regex("[a-f0-9]{64}")) && m.revision>=0 && m.short_term.size%2==0)
      m.short_term.forEachIndexed { i,v -> require(v.position==i && v.role==if(i%2==0) "user" else "assistant") }
      profiles.forEach { uuid(it.profile_id); require(it.owner_id==m.memory_owner_id && it.revision>=0); it.fields() }
      require(profiles.map { it.profile_id }.distinct().size==profiles.size)
      require(binding?.owner_id==m.memory_owner_id && binding.revision>=0)
      require(binding.active_profile_id==null || active()!=null)
    } ?: require(profiles.isEmpty() && binding==null && task_state==null)
    task_state?.let { s ->
      s.record().valid(); require(s.task_id==memory?.task_id)
      require(listOf(s.phase,s.step,s.expected_action).all { it.matches(Regex("[a-z][a-z0-9_]*")) })
      require(s.allowed_events.distinct()==s.allowed_events && s.allowed_events.all { it.matches(Regex("[A-Z][A-Z0-9_]*")) })
      require(!s.is_terminal || (s.status=="ACTIVE" && s.allowed_events.isEmpty()))
      require(s.status!="PAUSED" || s.allowed_events==listOf("RESUME"))
    }
    require(readiness.memory_ready==(memory!=null) && readiness.profile_ready==(active()!=null))
    require(readiness.task_state_ready==(task_state!=null && state_error==null))
    require(ready==(readiness.memory_ready && readiness.profile_ready && readiness.task_state_ready))
    last_transition?.let { t -> t.before.valid(); t.after.valid()
      require(t.task_id==t.before.task_id && t.task_id==t.after.task_id && t.before.machine_id==t.after.machine_id)
      require(t.after.revision==t.before.revision+1) }
  }
  private fun TaskOperation.valid(s: TaskRequestSnapshot,probe: Boolean)=apply {
    current.valid(); val o=observation; o.stored_state.valid()
    require(o.memory.snapshot_id==s.snapshot_id && o.memory.task_id==s.task_id)
    require(o.stored_state.task_id==s.task_id && o.stored_state.revision==s.state_revision && o.selected_state.record()==o.stored_state)
    require(o.profile.profile_id==s.profile_id && o.profile.revision==s.profile_revision && o.profile.owner_id==o.memory.memory_owner_id)
    require(o.binding.active_profile_id==s.profile_id && o.binding.revision==s.binding_revision && o.binding.owner_id==o.profile.owner_id)
    require(current.task_state?.record()==o.stored_state && current.memory?.session_id==o.memory.session_id)
    if(probe) require(!o.conversation_committed && current.memory==o.memory)
    require(!o.conversation_committed || o.outcome.status=="completed")
  }
  override suspend fun current()=api.current().valid()
  override suspend fun catalog()=api.catalog()
  override suspend fun initialize()=api.initialize(emptyMap()).valid()
  override suspend fun initializeState(body: TaskInitialize)=api.initializeState(body).valid()
  override suspend fun create(body: ProfileCreate)=api.create(body).apply { current.valid(); require(profile in current.profiles) }
  override suspend fun select(id: String,body: ProfileSelect)=api.select(id,body).valid()
  override suspend fun mutate(body: MemoryMutationRequest)=api.mutate(body).valid()
  override suspend fun lifecycle(action: String,body: MemorySnapshotRequest)=api.lifecycle(action,body).valid()
  override suspend fun event(body: TaskEvent)=api.event(body).valid()
  override suspend fun send(body: TaskSend)=api.send(body).valid(body.snapshot(),false)
  override suspend fun probe(body: TaskRequestSnapshot)=api.probe(body).valid(body,true)
}
