package com.example.responsecontrollab.data

import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.POST
import retrofit2.http.Path

interface ChatApi {
  @POST("api/v1/agent/sessions")
  suspend fun create(@Body body: CreateChatSessionDto): Response<ChatSessionDto>

  @POST("api/v1/agent/sessions/{session_id}/messages")
  suspend fun send(@Path("session_id") sessionId: String, @Body body: ChatMessageRequestDto): Response<ChatTurnDto>

  @DELETE("api/v1/agent/sessions/{session_id}")
  suspend fun delete(@Path("session_id") sessionId: String): Response<Unit>
}

class ChatRequestException(val code: String, override val message: String) : Exception(message)

interface ChatRepository {
  suspend fun createSession(): ChatSessionDto
  suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto
  suspend fun deleteSession(sessionId: String)
}

class DefaultChatRepository(private val api: ChatApi) : ChatRepository {
  private val json = Json { ignoreUnknownKeys = true }

  private suspend fun <T> request(block: suspend () -> T): T = try {
    block()
  } catch (error: CancellationException) {
    throw error
  } catch (error: ChatRequestException) {
    throw error
  } catch (_: Exception) {
    throw ChatRequestException("unknown", "Не удалось подтвердить результат запроса.")
  }

  private fun <T> Response<T>.requireStatus(expected: Int): Response<T> {
    if (code() != expected) {
      val error = runCatching { json.decodeFromString<ChatHttpErrorDto>(errorBody()?.string().orEmpty()) }.getOrNull()
      val expectedCode = mapOf(404 to "session_not_found", 409 to "session_busy", 422 to "validation_error")[code()]
      if (error != null && error.error.code == expectedCode) {
        throw ChatRequestException(error.error.code, when (expectedCode) {
          "session_not_found" -> "Диалог потерян после перезапуска сервера. Начните новый диалог."
          "session_busy" -> "Диалог занят. Дождитесь завершения отправки."
          else -> "Некорректный запрос. Проверьте сообщение."
        })
      }
      throw ChatRequestException("unknown", "Не удалось подтвердить результат запроса.")
    }
    return this
  }

  override suspend fun createSession(): ChatSessionDto = request {
    val result = api.create(CreateChatSessionDto()).requireStatus(201).body()
    require(result != null && result.sessionId.isNotBlank() && result.historyTurnCount == 0)
    result
  }

  override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto = request {
    val result = api.send(sessionId, ChatMessageRequestDto(message)).requireStatus(200).body()
    require(result != null && result.sessionId == sessionId && result.requestId.isNotBlank() && result.historyTurnCount >= 0)
    if (result.status == "completed") {
      require(!result.reply.isNullOrBlank() && result.error == null && result.incompleteReason == null)
    } else {
      require(result.status in setOf("incomplete", "refused", "error") && result.reply == null && result.error != null)
    }
    result
  }

  override suspend fun deleteSession(sessionId: String): Unit = request {
    api.delete(sessionId).requireStatus(204)
    Unit
  }
}
