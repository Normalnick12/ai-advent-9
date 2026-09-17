package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import retrofit2.HttpException
import retrofit2.http.*

@Serializable data class CodingPolicyValues(val required_architecture: String, val required_ui_toolkit: String,
  val required_async_model: String, val payment_confirmation_required: Boolean)
@Serializable data class CodingPolicyRecord(val task_id: String, val policy_id: String, val definition_version: String,
  val snapshot_id: String, val values: CodingPolicyValues)
@Serializable data class InvariantReadiness(val memory_ready: Boolean, val profile_ready: Boolean,
  val state_ready: Boolean, val policy_ready: Boolean, val consistent: Boolean)
@Serializable data class InvariantsCurrent(val memory: MemoryStateDto?=null, val profile: ProfileRecord?=null,
  val binding: ProfileBinding?=null, val task_state: TaskStateView?=null, val policy: CodingPolicyRecord?=null,
  val rules: List<JsonObject> = emptyList(), val readiness: InvariantReadiness,
  val ready: Boolean, val can_propose: Boolean, val source_error: String?=null, val busy: Boolean=false,
  val recovery_required: Boolean=false, val generation_calls: Int=0) {
  fun reference()=InvariantTaskReference(requireNotNull(memory).task_id,memory.snapshot_id)
  fun proposal(action: String): InvariantProposalRequest {
    val m=requireNotNull(memory); val p=requireNotNull(profile); val s=requireNotNull(task_state); val policy=requireNotNull(policy)
    return InvariantProposalRequest(m.task_id,m.snapshot_id,m.session_id,s.revision,p.profile_id,p.revision,
      requireNotNull(binding).revision,policy.policy_id,policy.definition_version,policy.snapshot_id,action)
  }
}
@Serializable data class InvariantAction(val action_id: String,val text: String)
@Serializable data class InvariantsCatalog(val working: Map<String,String>,val profile: ProfileFields,val policy: CodingPolicyValues,val actions: List<InvariantAction>)
@Serializable data class InvariantTaskReference(val task_id: String,val snapshot_id: String)
@Serializable data class InvariantEvent(val task_id: String,val snapshot_id: String,val state_revision: Int,val event: String)
@Serializable data class InvariantProposalRequest(val task_id: String,val snapshot_id: String,val session_id: String,
  val state_revision: Int,val profile_id: String,val profile_revision: Int,val binding_revision: Int,
  val policy_id: String,val policy_version: String,val policy_snapshot_id: String,val action_id: String)
@Serializable data class InvariantTurn(val status: String,val decision: String?=null,val precheck: JsonObject?=null,
  val validation: JsonObject?=null,val commit_status: String,val reply: String?=null,
  val error_code: String?=null,val error_stage: String?=null)
@Serializable data class InvariantObservation(val attempt_id: String,val action_id: String,val query: String,
  val memory: MemoryStateDto,val profile: ProfileRecord,val binding: ProfileBinding,val state: TaskStateView,
  val policy: CodingPolicyRecord,val intent: JsonObject,val selection: JsonObject,val rules: List<JsonObject>,
  val invariant_section: String,val profile_section: String?=null,val state_section: String?=null,
  val actual_request: JsonObject?=null,val provider_dispatch: String,val generation_calls: Int,
  val provider_outcome: JsonObject?=null,val raw_candidate: String?=null,val candidate: JsonObject?=null,
  val candidate_preparation: String,val turn: InvariantTurn,val storage_checks: JsonObject,
  val selection_checks: JsonObject,val assembly_checks: JsonObject,val model_adherence: String)
@Serializable data class InvariantOperation(val current: InvariantsCurrent?=null,val observation: InvariantObservation)

interface InvariantsApi {
  @GET("api/v1/invariants/current") suspend fun current(): InvariantsCurrent
  @GET("api/v1/invariants/scenario") suspend fun catalog(): InvariantsCatalog
  @POST("api/v1/invariants/initialize") suspend fun initialize(@Body body: Map<String,String>): InvariantsCurrent
  @POST("api/v1/invariants/setup") suspend fun setup(@Body body: InvariantTaskReference): InvariantsCurrent
  @POST("api/v1/invariants/events") suspend fun event(@Body body: InvariantEvent): InvariantsCurrent
  @POST("api/v1/invariants/lifecycle/{action}") suspend fun lifecycle(@Path("action") action: String,@Body body: InvariantTaskReference): InvariantsCurrent
  @POST("api/v1/invariants/proposals") suspend fun propose(@Body body: InvariantProposalRequest): InvariantOperation
}
interface InvariantsRepository {
  suspend fun current(): InvariantsCurrent
  suspend fun catalog(): InvariantsCatalog
  suspend fun initialize(): InvariantsCurrent
  suspend fun setup(body: InvariantTaskReference): InvariantsCurrent
  suspend fun event(body: InvariantEvent): InvariantsCurrent
  suspend fun lifecycle(action: String,body: InvariantTaskReference): InvariantsCurrent
  suspend fun propose(body: InvariantProposalRequest): InvariantOperation
}
class InvariantsOperationException(val dispatch: String): Exception("Operation receipt unavailable")

class DefaultInvariantsRepository(private val api: InvariantsApi): InvariantsRepository {
  private val json=Json { ignoreUnknownKeys=true }
  override suspend fun current()=api.current()
  override suspend fun catalog()=api.catalog()
  override suspend fun initialize()=api.initialize(emptyMap())
  override suspend fun setup(body: InvariantTaskReference)=api.setup(body)
  override suspend fun event(body: InvariantEvent)=api.event(body)
  override suspend fun lifecycle(action: String,body: InvariantTaskReference)=api.lifecycle(action,body)
  override suspend fun propose(body: InvariantProposalRequest): InvariantOperation {
    val result=try { api.propose(body) } catch(e: HttpException) {
      // Technical failures may still carry the original immutable attempt receipt.
      val raw=e.response()?.errorBody()?.string()
      val receipt=raw?.let { runCatching { json.decodeFromString<InvariantOperation>(it) }.getOrNull() }
      if(receipt==null) {
        val dispatch=runCatching { json.parseToJsonElement(raw?:"{}").jsonObject["dispatch"]?.jsonPrimitive?.content }.getOrNull()
        throw InvariantsOperationException(if(dispatch=="not_dispatched") dispatch else "unknown")
      } else receipt
    }
    val o=result.observation
    require(o.action_id==body.action_id && o.memory.task_id==body.task_id && o.memory.session_id==body.session_id)
    require(o.memory.snapshot_id==body.snapshot_id && o.state.revision==body.state_revision)
    require(o.profile.profile_id==body.profile_id && o.profile.revision==body.profile_revision && o.binding.revision==body.binding_revision)
    require(o.policy.policy_id==body.policy_id && o.policy.definition_version==body.policy_version && o.policy.snapshot_id==body.policy_snapshot_id)
    require(o.generation_calls in 0..1 && o.provider_dispatch==if(o.generation_calls==0) "not_dispatched" else "dispatched")
    require(o.generation_calls!=0 || (o.actual_request==null && o.raw_candidate==null && o.candidate==null))
    require(o.turn.commit_status!="committed" || (o.turn.status=="completed" && o.turn.reply!=null))
    return result
  }
}
