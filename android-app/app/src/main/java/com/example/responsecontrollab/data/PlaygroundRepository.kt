package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import retrofit2.HttpException
import retrofit2.http.*

@Serializable data class PlaygroundConfiguration(
  val version: String = "coding-setup-v1", val preset: String = "checkout",
  val profile_preset: String = "compact",
  val policy: CodingPolicyValues = CodingPolicyValues("MVI", "Compose", "CoroutinesFlow", true),
)
@Serializable data class PlaygroundPreset(val id: String, val name: String)
@Serializable data class PlaygroundCatalog(val task_title: String, val machine_id: String,
  val defaults: PlaygroundConfiguration, val profiles: List<PlaygroundPreset>,
  val policy_options: JsonObject, val nodes: Map<String,String>, val event_labels: Map<String,String>)
@Serializable data class PlaygroundSetup(val version: String, val machine_id: String,
  val configuration: PlaygroundConfiguration, val profile_fields: ProfileFields,
  val profile_version: String, val owner_id: String, val task_id: String, val session_id: String,
  val previous_snapshot: String? = null, val previous_profile_binding: ProfileBinding, val status: String)
@Serializable data class PlaygroundReference(val task_id: String, val session_id: String, val snapshot_id: String,
  val state_revision: Int, val profile_id: String, val profile_revision: Int, val binding_revision: Int,
  val policy_id: String, val policy_version: String, val policy_snapshot_id: String) {
  fun send(query: String) = PlaygroundSend(task_id, session_id, snapshot_id, state_revision, profile_id,
    profile_revision, binding_revision, policy_id, policy_version, policy_snapshot_id, query)
  fun event(event: String) = PlaygroundEvent(task_id, session_id, snapshot_id, state_revision, event)
  fun profile(preset: String) = PlaygroundProfileSelection(task_id, session_id, snapshot_id, state_revision,
    profile_id, profile_revision, binding_revision, policy_id, policy_version, policy_snapshot_id, preset)
}
@Serializable data class PlaygroundSend(val task_id: String, val session_id: String, val snapshot_id: String,
  val state_revision: Int, val profile_id: String, val profile_revision: Int, val binding_revision: Int,
  val policy_id: String, val policy_version: String, val policy_snapshot_id: String, val query: String)
@Serializable data class PlaygroundProfileSelection(val task_id: String, val session_id: String, val snapshot_id: String,
  val state_revision: Int, val profile_id: String, val profile_revision: Int, val binding_revision: Int,
  val policy_id: String, val policy_version: String, val policy_snapshot_id: String, val profile_preset: String)
@Serializable data class PlaygroundEvent(val task_id: String, val session_id: String, val snapshot_id: String,
  val state_revision: Int, val event: String)
@Serializable data class PlaygroundCreate(val configuration: PlaygroundConfiguration, val current: PlaygroundReference? = null)
@Serializable data class PlaygroundComplete(val task_id: String)
@Serializable data class PlaygroundAction(val event: String, val label: String)
@Serializable data class PlaygroundCurrent(val memory: MemoryStateDto? = null, val profile: ProfileRecord? = null,
  val binding: ProfileBinding? = null, val task_state: TaskStateView? = null, val policy: CodingPolicyRecord? = null,
  val setup: PlaygroundSetup? = null, val source_error: String? = null,
  val readiness: Map<String,Boolean> = emptyMap(), val ready: Boolean = false, val can_send: Boolean = false,
  val reference: PlaygroundReference? = null, val busy: Boolean = false,
  val reconciliation_required: Boolean = false, val generation_calls: Int = 0,
  val stage_label: String? = null, val next_action: String = "", val actions: List<PlaygroundAction> = emptyList(),
  val educational_event: String? = null)
@Serializable data class PlaygroundSources(val memory: MemoryStateDto, val profile: ProfileRecord,
  val binding: ProfileBinding, val state: TaskStateView, val policy: CodingPolicyRecord,
  val selection: MemorySelection, val rules: List<JsonObject>)
@Serializable data class PlaygroundReceipt(
  val attempt_id: String, val operation: String, val outcome: String,
  val provider_dispatch: String, val generation_calls: Int,
  val session_id: String? = null, val task_id: String? = null, val query: String? = null,
  val sources: PlaygroundSources? = null, val coverage: JsonObject? = null,
  val actual_request: JsonObject? = null, val profile_section: String? = null,
  val state_section: String? = null, val invariant_section: String? = null,
  val provider_outcome: JsonObject? = null, val raw_candidate: String? = null, val candidate: JsonObject? = null,
  val candidate_preparation: String? = null, val precheck_status: String? = null, val assembly_status: String? = null,
  val turn: InvariantTurn? = null, val pair_position: Int? = null,
  val event: String? = null, val error: String? = null, val before: TaskStateView? = null,
  val after: TaskStateView? = null, val persistence: String? = null,
  val conversation: String? = null, val conversation_commit: String? = null, val explanation: String? = null,
)
@Serializable data class PlaygroundOperation(val current: PlaygroundCurrent? = null, val receipt: PlaygroundReceipt)

interface PlaygroundApi {
  @GET("api/v1/agent-playground/catalog") suspend fun catalog(): PlaygroundCatalog
  @GET("api/v1/agent-playground/current") suspend fun current(): PlaygroundCurrent
  @POST("api/v1/agent-playground/create-task") suspend fun create(@Body body: PlaygroundCreate): PlaygroundCurrent
  @POST("api/v1/agent-playground/complete-setup") suspend fun complete(@Body body: PlaygroundComplete): PlaygroundCurrent
  @POST("api/v1/agent-playground/select-profile") suspend fun profile(@Body body: PlaygroundProfileSelection): PlaygroundCurrent
  @POST("api/v1/agent-playground/new-conversation") suspend fun conversation(@Body body: PlaygroundReference): PlaygroundCurrent
  @POST("api/v1/agent-playground/events") suspend fun event(@Body body: PlaygroundEvent): PlaygroundOperation
  @POST("api/v1/agent-playground/send") suspend fun send(@Body body: PlaygroundSend): PlaygroundOperation
}
interface PlaygroundRepository {
  suspend fun catalog(): PlaygroundCatalog
  suspend fun current(): PlaygroundCurrent
  suspend fun create(body: PlaygroundCreate): PlaygroundCurrent
  suspend fun complete(body: PlaygroundComplete): PlaygroundCurrent
  suspend fun profile(body: PlaygroundProfileSelection): PlaygroundCurrent
  suspend fun conversation(body: PlaygroundReference): PlaygroundCurrent
  suspend fun event(body: PlaygroundEvent): PlaygroundOperation
  suspend fun send(body: PlaygroundSend): PlaygroundOperation
}
class PlaygroundOperationException(val dispatch: String, val code: String): Exception(code)

class DefaultPlaygroundRepository(private val api: PlaygroundApi): PlaygroundRepository {
  private val json = Json { ignoreUnknownKeys = true }
  override suspend fun catalog() = api.catalog()
  override suspend fun current() = api.current()
  override suspend fun create(body: PlaygroundCreate) = api.create(body)
  override suspend fun complete(body: PlaygroundComplete) = api.complete(body)
  override suspend fun profile(body: PlaygroundProfileSelection) = api.profile(body)
  override suspend fun conversation(body: PlaygroundReference) = api.conversation(body)

  private suspend fun operation(call: suspend () -> PlaygroundOperation): PlaygroundOperation =
    try { call() } catch (e: HttpException) {
      val raw = e.response()?.errorBody()?.string()
      val result = raw?.let { runCatching { json.decodeFromString<PlaygroundOperation>(it) }.getOrNull() }
      result ?: run {
        val fields = runCatching { json.parseToJsonElement(raw ?: "{}").jsonObject }.getOrNull()
        throw PlaygroundOperationException(fields?.get("dispatch")?.jsonPrimitive?.content ?: "unknown",
          fields?.get("error")?.jsonPrimitive?.content ?: "operation_failed")
      }
    }

  override suspend fun send(body: PlaygroundSend): PlaygroundOperation {
    val result = operation { api.send(body) }
    val r = result.receipt
    val s = requireNotNull(r.sources)
    require(r.operation == "send" && r.session_id == body.session_id && r.query == body.query)
    require(s.memory.task_id == body.task_id && s.memory.session_id == body.session_id && s.memory.snapshot_id == body.snapshot_id)
    require(s.state.revision == body.state_revision && s.profile.profile_id == body.profile_id &&
      s.profile.revision == body.profile_revision && s.binding.revision == body.binding_revision)
    require(s.policy.policy_id == body.policy_id && s.policy.definition_version == body.policy_version &&
      s.policy.snapshot_id == body.policy_snapshot_id)
    require(r.generation_calls in 0..1 && r.provider_dispatch == if (r.generation_calls == 1) "dispatched" else "not_dispatched")
    require(r.generation_calls != 0 || (r.actual_request == null && r.candidate == null && r.raw_candidate == null))
    val turn = requireNotNull(r.turn)
    require((turn.commit_status == "committed") == (r.pair_position != null))
    require(turn.commit_status != "committed" || (turn.status == "completed" && turn.reply != null &&
      r.pair_position == s.memory.short_term.size))
    return result
  }

  override suspend fun event(body: PlaygroundEvent): PlaygroundOperation {
    val result = operation { api.event(body) }
    val r = result.receipt
    require(r.operation == "lifecycle" && r.task_id == body.task_id && r.event == body.event)
    require(r.before?.revision == body.state_revision && r.before.task_id == body.task_id)
    require(r.generation_calls == 0 && r.provider_dispatch == "not_required" && r.actual_request == null)
    require(r.conversation == "unchanged" && r.conversation_commit == "not_applicable")
    when (r.outcome) {
      "rejected" -> require(r.before == r.after && r.persistence == "not_attempted")
      "forward_applied", "recovery_applied", "pause_applied", "resume_applied" ->
        require(r.persistence == "committed" && r.after?.revision == body.state_revision + 1)
      "technical_error" -> require(r.persistence in listOf("unknown", "failed"))
      else -> error("Unknown lifecycle outcome")
    }
    return result
  }
}
