package com.example.responsecontrollab.data

import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import retrofit2.Response
import retrofit2.http.*

internal fun createCompressionHttpClient(): OkHttpClient = createBackendHttpClient().newBuilder()
  .readTimeout(220, TimeUnit.SECONDS).callTimeout(240, TimeUnit.SECONDS)
  .retryOnConnectionFailure(false).build()

interface CompressionLabApi {
  @POST("api/v1/compression-lab/sessions")
  suspend fun create(@Body body: CreateChatSessionDto): Response<CompressionSessionDto>
  @GET("api/v1/compression-lab/sessions/{id}")
  suspend fun get(@Path("id") id: String): Response<CompressionSessionDto>
  @GET("api/v1/compression-lab/sessions/{id}/summary")
  suspend fun summary(@Path("id") id: String): Response<CompressionSummaryResponseDto>
  @DELETE("api/v1/compression-lab/sessions/{id}")
  suspend fun delete(@Path("id") id: String): Response<Unit>
  @POST("api/v1/compression-lab/sessions/{id}/messages")
  suspend fun send(@Path("id") id: String, @Body body: ChatMessageRequestDto): Response<CompressionOperationDto>
  @POST("api/v1/compression-lab/sessions/{id}/compare")
  suspend fun compare(@Path("id") id: String, @Body body: CompressionCompareRequestDto): Response<CompressionOperationDto>
}
interface CompressionLabRepository {
  suspend fun create(): CompressionSessionDto
  suspend fun get(id: String): CompressionSessionDto
  suspend fun summary(id: String): CompressionSummaryDto?
  suspend fun delete(id: String)
  suspend fun send(id: String, message: String): CompressionOperationDto
  suspend fun compare(id: String, question: String, scenarioId: String?): CompressionOperationDto
}
class DefaultCompressionLabRepository(private val api: CompressionLabApi) : CompressionLabRepository {
  private val json = Json { ignoreUnknownKeys = true }
  private suspend fun <T> request(block: suspend () -> T): T = try { block()
  } catch (e: CancellationException) { throw e
  } catch (e: ChatRequestException) { throw e
  } catch (_: Exception) { throw ChatRequestException("unknown", "Результат запроса неизвестен.") }

  private fun <T> Response<T>.checked(status: Int): Response<T> {
    if (code() != status) {
      val error = runCatching { json.decodeFromString<ChatHttpErrorDto>(errorBody()?.string().orEmpty()) }.getOrNull()
      val known = mapOf(404 to "session_not_found", 409 to "session_busy", 422 to "validation_error")[code()]
      if (known != null && error?.error?.code == known) throw ChatRequestException(known, when (known) {
        "session_not_found" -> "Диалог недоступен. Начните новый диалог."
        "session_busy" -> "Диалог занят. Дождитесь завершения."
        else -> "Некорректный запрос."
      })
      if (code() == 500 && error?.error?.code in setOf("summary_state_invalid", "summary_config_mismatch"))
        throw ChatRequestException(requireNotNull(error?.error?.code), "Сводка повреждена или несовместима. Начните новый диалог.")
      throw ChatRequestException("unknown", "Результат запроса неизвестен.")
    }
    return this
  }
  private fun CompressionSessionDto.valid(id: String = sessionId): CompressionSessionDto = apply {
    require(UUID.fromString(sessionId).toString() == sessionId && sessionId == id)
    require(historyTurnCount >= 0 && configVersion == COMPRESSION_VERSION)
  }
  override suspend fun create() = request {
    requireNotNull(api.create(CreateChatSessionDto()).checked(201).body()).valid().also { require(it.historyTurnCount == 0) }
  }
  override suspend fun get(id: String) = request { requireNotNull(api.get(id).checked(200).body()).valid(id) }
  override suspend fun summary(id: String) = request {
    requireNotNull(api.summary(id).checked(200).body()).also { require(it.sessionId == id) }.summary?.also {
      require(it.sessionId == id && it.configVersion == COMPRESSION_VERSION && it.text.isNotBlank() && it.boundary >= 1 && it.boundary % 2 == 1)
    }
  }
  override suspend fun delete(id: String): Unit = request { api.delete(id).checked(204); Unit }
  private fun Response<CompressionOperationDto>.operation(id: String, kind: String) =
    requireNotNull(checked(200).body()).also {
      require(it.sessionId == id && it.kind == kind && it.historyTurnCount >= 0 && it.requestId.isNotBlank() && it.attemptId.isNotBlank())
      require(it.status in setOf("completed", "partial", "error", "incomplete", "refused"))
      if (it.committed) require(kind == "send" && it.status == "completed" && !it.reply.isNullOrBlank() && it.errorCode == null && it.responsePhase.generationAttempted)
      if (kind == "compare") require(!it.committed && it.reply == null)
      if (kind == "send" && !it.committed) require(it.reply == null && it.status != "completed")
    }
  override suspend fun send(id: String, message: String) = request { api.send(id, ChatMessageRequestDto(message)).operation(id, "send") }
  override suspend fun compare(id: String, question: String, scenarioId: String?) = request {
    api.compare(id, CompressionCompareRequestDto(question, scenarioId)).operation(id, "compare")
  }
}
