package com.example.responsecontrollab.data

import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import retrofit2.Response
import retrofit2.http.*

interface TokenLabApi {
  @POST("api/v1/token-lab/sessions")
  suspend fun create(@Body body: CreateChatSessionDto): Response<ChatSessionDto>
  @GET("api/v1/token-lab/sessions/{id}")
  suspend fun get(@Path("id") id: String): Response<ChatSessionDto>
  @DELETE("api/v1/token-lab/sessions/{id}")
  suspend fun delete(@Path("id") id: String): Response<Unit>
  @POST("api/v1/token-lab/sessions/{id}/messages")
  suspend fun send(@Path("id") id: String, @Body body: ChatMessageRequestDto): Response<TokenTurnDto>
  @POST("api/v1/token-lab/sessions/{id}/overflow/prepare")
  suspend fun prepare(@Path("id") id: String, @Body body: CreateChatSessionDto): Response<TokenTurnDto>
  @POST("api/v1/token-lab/sessions/{id}/overflow/execute")
  suspend fun execute(@Path("id") id: String, @Body body: OverflowExecuteDto): Response<TokenTurnDto>
}
interface TokenLabRepository {
  suspend fun create(): ChatSessionDto
  suspend fun get(id: String): ChatSessionDto
  suspend fun delete(id: String)
  suspend fun send(id: String, message: String): TokenTurnDto
  suspend fun prepare(id: String): TokenTurnDto
  suspend fun execute(id: String, preparationId: String): TokenTurnDto
}
class DefaultTokenLabRepository(private val api: TokenLabApi) : TokenLabRepository {
  private val json = Json { ignoreUnknownKeys = true }
  private suspend fun <T> request(block: suspend () -> T): T = try {
    block()
  } catch (e: CancellationException) { throw e
  } catch (e: ChatRequestException) { throw e
  } catch (_: Exception) {
    throw ChatRequestException("unknown", "Результат запроса неизвестен.")
  }
  private fun <T> Response<T>.checked(status: Int): Response<T> {
    if (code() != status) {
      val error = runCatching { json.decodeFromString<ChatHttpErrorDto>(errorBody()?.string().orEmpty()) }.getOrNull()
      val known = mapOf(404 to "session_not_found", 409 to "session_busy", 422 to "validation_error")[code()]
      if (known != null && error?.error?.code == known) {
        throw ChatRequestException(known, when (known) {
          "session_not_found" -> "Диалог недоступен. Начните новый диалог."
          "session_busy" -> "Диалог занят. Дождитесь завершения."
          else -> "Некорректный запрос."
        })
      }
      throw ChatRequestException("unknown", "Результат запроса неизвестен.")
    }
    return this
  }
  override suspend fun create() = request {
    requireNotNull(api.create(CreateChatSessionDto()).checked(201).body()).also {
      require(UUID.fromString(it.sessionId).toString() == it.sessionId && it.historyTurnCount == 0)
    }
  }
  override suspend fun get(id: String) = request {
    requireNotNull(api.get(id).checked(200).body()).also {
      require(it.sessionId == id && it.historyTurnCount >= 0)
    }
  }
  override suspend fun delete(id: String): Unit = request { api.delete(id).checked(204); Unit }
  private fun Response<TokenTurnDto>.turn(id: String, kind: String): TokenTurnDto =
    requireNotNull(checked(200).body()).also {
      require(it.sessionId == id && it.attemptId.isNotBlank() && it.requestId.isNotBlank() && it.historyTurnCount >= 0)
      require(it.status in setOf("completed", "prepared", "incomplete", "refused", "error"))
      if (it.committed) require(kind == "send" && it.status == "completed" && !it.reply.isNullOrBlank() &&
        it.error == null && it.generationAttempted)
      else require(it.reply == null && it.status != "completed")
      if (it.status == "prepared") require(kind == "prepare" && it.preparation != null && !it.generationAttempted && !it.committed)
      else if (!it.committed) require(it.error != null)
      if (kind == "prepare") require(!it.generationAttempted && !it.committed)
      if (kind == "execute") require(!it.committed)
    }
  override suspend fun send(id: String, message: String) = request {
    api.send(id, ChatMessageRequestDto(message)).turn(id, "send")
  }
  override suspend fun prepare(id: String) = request { api.prepare(id, CreateChatSessionDto()).turn(id, "prepare") }
  override suspend fun execute(id: String, preparationId: String) = request {
    api.execute(id, OverflowExecuteDto(preparationId, true)).turn(id, "execute")
  }
}
