package com.example.responsecontrollab.data

import java.io.IOException
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class ChatRepositoryTest {
  private val requests = mutableListOf<Pair<String, String>>()
  private var status = 200
  private var body = ""
  private var offline = false
  private val client = createBackendHttpClient().newBuilder().addInterceptor { chain ->
    val request = chain.request()
    val buffer = Buffer()
    request.body?.writeTo(buffer)
    requests += "${request.method} ${request.url.encodedPath}" to buffer.readUtf8()
    if (offline) throw IOException("private")
    Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(status).message("fixture")
      .body(body.toResponseBody("application/json".toMediaType())).build()
  }.build()
  private val repo = DefaultChatRepository(Retrofit.Builder().baseUrl("http://test/").client(client)
    .addConverterFactory(Json.asConverterFactory("application/json".toMediaType())).build().create(ChatApi::class.java))

  @Test fun actualRetrofitRequestsContainOnlyMessageAndSessionId() = runTest {
    status = 201; body = """{"session_id":"s1","history_turn_count":0}"""
    assertEquals("s1", repo.createSession().sessionId)
    status = 200; body = """{"session_id":"s1","history_turn_count":4}"""
    assertEquals(4, repo.getSession("s1").historyTurnCount)
    status = 200; body = turn()
    assertEquals("Ответ", repo.sendMessage("s1", " U1 ").reply)
    status = 204; body = ""
    repo.deleteSession("s1")
    assertEquals(listOf(
      "POST /api/v1/agent/sessions" to "{}",
      "GET /api/v1/agent/sessions/s1" to "",
      "POST /api/v1/agent/sessions/s1/messages" to """{"message":" U1 "}""",
      "DELETE /api/v1/agent/sessions/s1" to "",
    ), requests)
    assertFalse(client.retryOnConnectionFailure)
    assertEquals(190000, client.callTimeoutMillis)
  }

  @Test fun mapsTrustworthyHttpErrorsAndUnknownTransport() = runTest {
    for ((http, code) in mapOf(404 to "session_not_found", 409 to "session_busy", 422 to "validation_error", 500 to "internal_error")) {
      status = http; body = """{"request_id":"r","error":{"code":"$code","message":"private"}}"""
      val error = runCatching { repo.sendMessage("s1", "U") }.exceptionOrNull() as ChatRequestException
      assertEquals(if (http == 500) "unknown" else code, error.code)
      assertFalse(error.message.contains("private"))
    }
    offline = true
    assertEquals("unknown", (runCatching { repo.sendMessage("s1", "U") }.exceptionOrNull() as ChatRequestException).code)
    assertEquals(5, requests.size)
  }

  @Test fun invalidResponseIsUnknownAndOutcomesPreserveNullReply() = runTest {
    for (outcome in listOf("incomplete", "refused", "error")) {
      body = """{"session_id":"s1","request_id":"r","status":"$outcome","reply":null,"history_turn_count":0,"incomplete_reason":null,"error":{"code":"llm_$outcome","message":"Ошибка"}}"""
      assertEquals(outcome, repo.sendMessage("s1", "U").status)
    }
    for (invalid in listOf("{}", turn().replace("Ответ", " "), turn().replace("s1", "another"))) {
      body = invalid
      assertEquals("unknown", (runCatching { repo.sendMessage("s1", "U") }.exceptionOrNull() as ChatRequestException).code)
    }
  }

  @Test fun metadataValidatesIdentityCountAndSafeErrorsWithoutRetries() = runTest {
    for (invalid in listOf("{}", """{"session_id":"other","history_turn_count":0}""", """{"session_id":"s1","history_turn_count":-1}""")) {
      body = invalid
      assertEquals("unknown", (runCatching { repo.getSession("s1") }.exceptionOrNull() as ChatRequestException).code)
    }
    for ((http, code) in mapOf(404 to "session_not_found", 409 to "session_busy", 422 to "validation_error", 500 to "internal_error")) {
      status = http; body = """{"request_id":"r","error":{"code":"$code","message":"private"}}"""
      val error = runCatching { repo.getSession("s1") }.exceptionOrNull() as ChatRequestException
      assertEquals(if (http == 500) "unknown" else code, error.code)
      assertFalse(error.message.contains("private"))
    }
    assertEquals(7, requests.size)
    assertTrue(requests.all { it.first == "GET /api/v1/agent/sessions/s1" && it.second.isEmpty() })
  }

  private fun turn() = """{"session_id":"s1","request_id":"r","status":"completed","reply":"Ответ","history_turn_count":1,"incomplete_reason":null,"error":null}"""
}
