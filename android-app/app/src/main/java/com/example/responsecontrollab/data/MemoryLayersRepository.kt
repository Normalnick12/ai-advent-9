package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.*
import java.util.UUID

@Serializable data class MemoryMessageDto(val role: String, val content: String, val position: Int)
@Serializable data class InactiveSessionDto(val session_id: String, val task_id: String)
@Serializable data class MemoryStateDto(
  val memory_owner_id: String, val task_id: String, val session_id: String,
  val revision: Int, val snapshot_id: String,
  val working: Map<String,String> = emptyMap(), val long_term: Map<String,String> = emptyMap(),
  val short_term: List<MemoryMessageDto> = emptyList(),
  val inactive_tasks: List<String> = emptyList(), val inactive_sessions: List<InactiveSessionDto> = emptyList(),
)
@Serializable data class MemoryExcluded(val layer: String, val key: String, val value: String, val reason: String)
@Serializable data class MemorySelection(
  val selected_working: Map<String,String> = emptyMap(), val selected_long_term: Map<String,String> = emptyMap(),
  val selected_sources: List<JsonObject> = emptyList(), val excluded: List<MemoryExcluded> = emptyList(),
  val inactive_tasks: List<String> = emptyList(), val inactive_sessions: List<InactiveSessionDto> = emptyList(),
)
@Serializable data class MemoryCurrent(
  val state: MemoryStateDto? = null, val busy: Boolean = false,
  val applicable_stages: List<String> = emptyList(), val preview: MemorySelection? = null,
  val transition: JsonObject? = null,
)
@Serializable data class MemoryCheck(
  val status: String, val correct: Boolean? = null, val expected: String? = null,
  val actual: String? = null, val values: List<String> = emptyList(),
)
@Serializable data class MemoryObservation(
  val attempt_id: String, val snapshot_id: String, val stored: MemoryStateDto,
  val selection: MemorySelection, val request: JsonObject, val status: String,
  val reply: String? = null, val error: String? = null, val stage: String? = null,
  val input_checks: Map<String,MemoryCheck> = emptyMap(),
  val output_checks: Map<String,MemoryCheck> = emptyMap(),
  val parsed: JsonObject? = null, val committed: Boolean = false,
)
@Serializable data class MemoryOperation(val current: MemoryCurrent, val observation: MemoryObservation)
@Serializable data class MemoryCatalog(val seed: String, val query: String, val working: Map<String,String>, val long_term: Map<String,String>)
@Serializable data class MemorySnapshotRequest(val snapshot_id: String)
@Serializable data class MemoryMutationRequest(
  val snapshot_id: String, val layer: String, val key: String, val operation: String, val value: String? = null,
)
@Serializable data class MemorySendRequest(val snapshot_id: String, val message: String)

interface MemoryLayersApi {
  @GET("api/v1/memory-layers/current") suspend fun current(): MemoryCurrent
  @GET("api/v1/memory-layers/scenario") suspend fun catalog(): MemoryCatalog
  @POST("api/v1/memory-layers/initialize") suspend fun initialize(@Body body: Map<String,String> = emptyMap()): MemoryCurrent
  @POST("api/v1/memory-layers/memory") suspend fun mutate(@Body body: MemoryMutationRequest): MemoryCurrent
  @POST("api/v1/memory-layers/lifecycle/{action}") suspend fun transition(@Path("action") action: String, @Body body: MemorySnapshotRequest): MemoryCurrent
  @POST("api/v1/memory-layers/messages") suspend fun send(@Body body: MemorySendRequest): MemoryOperation
  @POST("api/v1/memory-layers/verify/{stage}") suspend fun verify(@Path("stage") stage: String, @Body body: MemorySnapshotRequest): MemoryOperation
}

interface MemoryLayersRepository {
  suspend fun current(): MemoryCurrent
  suspend fun catalog(): MemoryCatalog
  suspend fun initialize(): MemoryCurrent
  suspend fun mutate(body: MemoryMutationRequest): MemoryCurrent
  suspend fun transition(action: String, body: MemorySnapshotRequest): MemoryCurrent
  suspend fun send(body: MemorySendRequest): MemoryOperation
  suspend fun verify(stage: String, body: MemorySnapshotRequest): MemoryOperation
}

class DefaultMemoryLayersRepository(private val api: MemoryLayersApi) : MemoryLayersRepository {
  private fun MemoryCurrent.valid() = apply {
    require(applicable_stages.all { it in listOf("A","B","C","D","E") })
    state?.let { s ->
      listOf(s.memory_owner_id,s.task_id,s.session_id).forEach { require(UUID.fromString(it).toString() == it) }
      require(setOf(s.memory_owner_id,s.task_id,s.session_id).size == 3)
      require(s.snapshot_id.matches(Regex("[a-f0-9]{64}")) && s.revision >= 0)
      require(s.working.keys.all { it in listOf("task","current_architecture","release_marker") })
      require(s.long_term.keys.all { it in listOf("project_code","preferred_architecture") })
      require((s.working.values+s.long_term.values).all { it.isNotBlank() && it.length<=256 })
      require(s.short_term.size%2 == 0)
      s.short_term.forEachIndexed { i,m -> require(m.position==i && m.role==if(i%2==0) "user" else "assistant") }
    }
  }
  private fun MemoryOperation.valid(snapshot: String, probe: Boolean) = apply {
    current.valid()
    require(observation.snapshot_id == snapshot && observation.stored.snapshot_id == snapshot)
    if(probe) require(!observation.committed && current.state?.snapshot_id == snapshot)
  }
  override suspend fun current() = api.current().valid()
  override suspend fun catalog() = api.catalog()
  override suspend fun initialize() = api.initialize().valid()
  override suspend fun mutate(body: MemoryMutationRequest) = api.mutate(body).valid()
  override suspend fun transition(action: String,body: MemorySnapshotRequest) = api.transition(action,body).valid()
  override suspend fun send(body: MemorySendRequest) = api.send(body).valid(body.snapshot_id,false)
  override suspend fun verify(stage: String,body: MemorySnapshotRequest) = api.verify(stage,body).valid(body.snapshot_id,true)
}
