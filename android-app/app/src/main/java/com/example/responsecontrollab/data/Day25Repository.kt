package com.example.responsecontrollab.data

import kotlinx.coroutines.CancellationException
import kotlinx.serialization.Serializable
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.http.*
import java.util.UUID

@Serializable data class Day25MemoryItem(val id: String, val text: String, val source_user_turn: Int,
  val source_start: Int, val source_end: Int)
@Serializable data class Day25Memory(val goal: Day25MemoryItem? = null,
  val constraints: List<Day25MemoryItem> = emptyList(), val terms: List<Day25MemoryItem> = emptyList(),
  val clarifications: List<Day25MemoryItem> = emptyList())
@Serializable data class Day25Source(val source: String, val section: String, val chunk_id: String)
@Serializable data class Day25Citation(val chunk_id: String, val quote: String)
@Serializable data class Day25Grounded(val status: String, val answer: String,
  val sources: List<Day25Source>, val citations: List<Day25Citation>)
@Serializable data class Day25History(val position: Int, val role: String, val content: String)
@Serializable data class Day25Turn(val turn: Int, val turn_id: String, val user: String,
  val grounded: Day25Grounded, val memory_update_status: String)
@Serializable data class Day25Snapshot(val session_id: String, val revision: Int, val history_turn_count: Int,
  val memory: Day25Memory, val history: List<Day25History>, val turns: List<Day25Turn>)
@Serializable data class Day25Message(val message: String, val expected_revision: Int)
@Serializable data class Day25Error(val code: String, val message: String)
@Serializable data class Day25Result(val session_id: String, val request_id: String, val status: String,
  val committed: Boolean, val grounded: Day25Grounded? = null, val memory_update_status: String? = null,
  val state: Day25Snapshot? = null, val error: Day25Error? = null)

interface Day25Api {
  @POST("api/v1/day25/sessions") suspend fun create(@Body body: Map<String,String>): Day25Snapshot
  @GET("api/v1/day25/sessions/{id}") suspend fun read(@Path("id") id: String): Day25Snapshot
  @POST("api/v1/day25/sessions/{id}/messages") suspend fun send(@Path("id") id: String, @Body body: Day25Message): Day25Result
  @DELETE("api/v1/day25/sessions/{id}") suspend fun delete(@Path("id") id: String): Response<Unit>
}
interface Day25Repository {
  suspend fun create(): Day25Snapshot
  suspend fun read(id: String): Day25Snapshot
  suspend fun send(id: String, body: Day25Message): Day25Result
  suspend fun delete(id: String)
}
class Day25RequestException(val code: String): Exception(code)
fun validDay25Id(id: String) = runCatching { UUID.fromString(id).toString() == id }.getOrDefault(false)

class DefaultDay25Repository(private val api: Day25Api): Day25Repository {
  private suspend fun <T> call(block: suspend () -> T): T = try { block() }
    catch (e: CancellationException) { throw e }
    catch (e: HttpException) { throw Day25RequestException(when(e.code()) {
      404 -> "session_not_found"; 409 -> "reconciliation_required"; 422 -> "validation_error"; else -> "unknown"
    }) }
    catch (e: Exception) { throw Day25RequestException("unknown") }

  // Transport consistency only. Grounding and memory validation remain backend-owned.
  private fun Day25Snapshot.checked(id: String? = null) = apply {
    require(validDay25Id(session_id) && (id == null || id == session_id))
    require(revision >= 0 && history_turn_count == revision && history.size == revision * 2 && turns.size == revision)
    history.forEachIndexed { i, h -> require(h.position == i && h.role == if(i % 2 == 0) "user" else "assistant") }
    turns.forEachIndexed { i, t ->
      require(t.turn == i + 1 && t.user == history[i * 2].content && t.grounded.answer == history[i * 2 + 1].content)
    }
  }
  override suspend fun create() = call { api.create(emptyMap()).checked().apply { require(revision == 0) } }
  override suspend fun read(id: String) = call { api.read(id).checked(id) }
  override suspend fun send(id: String, body: Day25Message) = call {
    api.send(id, body).apply {
      require(session_id == id)
      if (committed) {
        require(status == "accepted" && error == null && grounded != null && memory_update_status != null)
        val snapshot = requireNotNull(state).checked(id)
        require(snapshot.revision == body.expected_revision + 1)
        require(snapshot.turns.last().let { it.turn_id == request_id && it.user == body.message &&
          it.grounded == grounded && it.memory_update_status == memory_update_status })
      } else require(status != "accepted" && state == null && grounded == null && memory_update_status == null && error != null)
    }
  }
  override suspend fun delete(id: String) = call {
    val response = api.delete(id)
    if (!response.isSuccessful) throw HttpException(response)
    require(response.code() == 204)
  }
}
