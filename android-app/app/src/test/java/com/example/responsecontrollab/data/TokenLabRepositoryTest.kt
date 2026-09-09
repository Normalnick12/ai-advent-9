package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class TokenLabRepositoryTest {
  @Test fun wireContainsOnlyNewMessageOrExplicitPermissionAndNullableUsageSurvives() = runTest {
    val requests = mutableListOf<Pair<String, String>>()
    val id = "11111111-1111-4111-8111-111111111111"
    var body = ""
    var status = 200
    val http = createBackendHttpClient().newBuilder().addInterceptor { chain ->
      val req = chain.request(); val buffer = Buffer(); req.body?.writeTo(buffer)
      requests += req.url.encodedPath to buffer.readUtf8()
      Response.Builder().request(req).protocol(Protocol.HTTP_1_1).code(status).message("fixture")
        .body(body.toResponseBody("application/json".toMediaType())).build()
    }.build()
    val json = Json { ignoreUnknownKeys = true }
    val repo = DefaultTokenLabRepository(Retrofit.Builder().baseUrl("http://test/").client(http)
      .addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build().create(TokenLabApi::class.java))
    body = json.encodeToString(ChatSessionDto(id, 0)); status = 201
    repo.create(); status = 200; repo.get(id)
    val response = TokenTurnDto(id, 1, "r", "a", "completed", "A", generationAttempted = true, committed = true,
      usage = TokenLabUsageDto(inputTokens = 0, cachedInputTokens = null, outputTokens = null),
      diagnostics = TokenDiagnosticsDto(preflightInputTokens = 139, contextWindow = 128000,
        reservedOutputTokens = 1200, countCalls = 2))
    body = json.encodeToString(response)
    val turn = repo.send(id, " U\n ")
    assertEquals(0L, turn.usage!!.inputTokens)
    assertNull(turn.usage.outputTokens)
    assertNull(turn.usage.cachedInputTokens)
    assertEquals(139L, turn.diagnostics!!.preflightInputTokens)
    body = json.encodeToString(response.copy(status = "error", committed = false, reply = null,
      historyTurnCount = 0, usage = null, error = ChatErrorDto("context_limit_exceeded", "Ошибка")))
    assertNull(repo.execute(id, "p").usage)
    assertEquals("""{"preparation_id":"p","confirm":true}""", requests.last().second)
    assertEquals("""{"message":" U\n "}""", requests[2].second)
    assertTrue(requests.all { it.first.startsWith("/api/v1/token-lab/sessions") })
    assertFalse(http.retryOnConnectionFailure)
    assertEquals(4, requests.size)
    body = json.encodeToString(response.copy(committed = true))
    assertTrue(runCatching { repo.execute(id, "p2") }.exceptionOrNull() is ChatRequestException)
    assertEquals(5, requests.size)
  }
}
