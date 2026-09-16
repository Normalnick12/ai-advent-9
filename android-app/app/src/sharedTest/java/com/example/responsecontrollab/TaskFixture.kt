package com.example.responsecontrollab

import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.UUID

/** Test server stand-in; no production code uses this event handling. */
class TaskFixture: TaskStateRepository {
  private val owner=UUID.randomUUID().toString()
  private val task=UUID.randomUUID().toString()
  val fields=ProfileFields("Compact Engineer","ru","technical","concise",ProfileFormat("summary_bullets",3),ProfileConstraints(true,true,false))
  val profile=ProfileRecord(UUID.randomUUID().toString(),owner,0,fields.name,fields.language,fields.tone,fields.verbosity,fields.response_format,fields.constraints)
  var value=TaskCurrent(memory=MemoryStateDto(owner,task,UUID.randomUUID().toString(),0,"a".repeat(64),working=mapOf("task" to "Checkout","current_architecture" to "MVI")),
    profiles=listOf(profile),binding=ProfileBinding(owner,profile.profile_id,1),
    task_state=TaskStateView(task,"checkout-v1","EXECUTION_IMPLEMENT","ACTIVE",2,"execution","implement","continue_implementation",false,listOf("IMPLEMENTATION_READY","PAUSE")),
    readiness=TaskReadiness(true,true,true),ready=true)
  var reads=0; var sends=0; var events=0; var lifecycles=0; var writes=0; var probes=0
  var lose=false; var failRead=false; var gate: CompletableDeferred<Unit>?=null
  var eventFailure: Exception?=null
  var lastSend: TaskSend?=null
  override suspend fun current(): TaskCurrent { reads++; check(!failRead); return value }
  override suspend fun catalog()=TaskCatalog(mapOf("task" to "Checkout","current_architecture" to "MVI"),fields,"Что делать дальше?","Execution query")
  override suspend fun initialize(): TaskCurrent { writes++; return value }
  override suspend fun initializeState(body: TaskInitialize): TaskCurrent { writes++; return value }
  override suspend fun create(body: ProfileCreate): TaskProfileSaved { writes++; return TaskProfileSaved(value,profile) }
  override suspend fun select(id: String,body: ProfileSelect): TaskCurrent { writes++; return value }
  override suspend fun mutate(body: MemoryMutationRequest): TaskCurrent { writes++; return value }
  override suspend fun lifecycle(action: String,body: MemorySnapshotRequest): TaskCurrent {
    lifecycles++; val m=value.memory!!
    value=value.copy(memory=m.copy(session_id=UUID.randomUUID().toString(),short_term=emptyList(),snapshot_id="b".repeat(64),revision=m.revision+1))
    if(lose) error("Lost response")
    return value
  }
  override suspend fun event(body: TaskEvent): TaskCurrent {
    events++; eventFailure?.let { throw it }; gate?.await(); val s=value.task_state!!
    value=value.copy(task_state=when(body.event) {
      "PAUSE" -> s.copy(status="PAUSED",revision=s.revision+1,allowed_events=listOf("RESUME"))
      "RESUME" -> s.copy(status="ACTIVE",revision=s.revision+1,allowed_events=listOf("IMPLEMENTATION_READY","PAUSE"))
      else -> s.copy(state_id="DONE",phase="done",step="complete",expected_action="none",is_terminal=true,revision=s.revision+1,allowed_events=emptyList())
    })
    if(lose) error("Lost response")
    return value
  }
  override suspend fun send(body: TaskSend): TaskOperation { sends++; lastSend=body; gate?.await(); return result(body.message,true) }
  override suspend fun probe(body: TaskRequestSnapshot): TaskOperation { probes++; return result("Что делать дальше?",false) }
  private fun result(query: String,commit: Boolean): TaskOperation {
    val before=value; val m=before.memory!!; val s=before.task_state!!
    val checks=mapOf("check" to ProfileCheck("pass",true))
    val o=TaskObservation(UUID.randomUUID().toString(),if(commit) "send" else "probe",m,profile,before.binding!!,s.record(),s,
      MemorySelection(selected_working=m.working),"Profile section","TASK_STATE ${s.state_id} ${s.status}","profile-v1","state-v1",
      ProfileRequestEvidence(listOf(ProfileMessage("user",query)),buildJsonObject { put("instructions","actual ${s.status}") }),query,
      ProfileOutcome("completed","Reply $sends"),commit,checks,checks,checks,TaskAdherence("human_observation","Оцените ответ отдельно"))
    if(commit) value=value.copy(memory=m.copy(snapshot_id="c".repeat(64),revision=m.revision+1,short_term=m.short_term+
      listOf(MemoryMessageDto("user",query,m.short_term.size),MemoryMessageDto("assistant","Reply $sends",m.short_term.size+1))))
    value=value.copy(generation_calls=value.generation_calls+1)
    return TaskOperation(value,o)
  }
}
