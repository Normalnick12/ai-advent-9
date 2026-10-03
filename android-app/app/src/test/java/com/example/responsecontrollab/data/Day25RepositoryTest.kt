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

class Day25RepositoryTest {
  private val requests = mutableListOf<Pair<String,String>>()
  private var status = 200
  private var body = ""
  private val client = createBackendHttpClient().newBuilder().addInterceptor { chain ->
    val request = chain.request(); val buffer = Buffer(); request.body?.writeTo(buffer)
    requests += "${request.method} ${request.url.encodedPath}" to buffer.readUtf8()
    Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(status).message("fixture")
      .body(body.toResponseBody("application/json".toMediaType())).build()
  }.build()
  private val repo = DefaultDay25Repository(Retrofit.Builder().baseUrl("http://test/").client(client)
    .addConverterFactory(Json.asConverterFactory("application/json".toMediaType())).build().create(Day25Api::class.java))
  private val id = "00000000-0000-0000-0000-000000000025"
  private val empty = Day25Snapshot(id,0,0,Day25Memory(),emptyList(),emptyList())

  @Test fun sendsOnlyCurrentMessageAndRevisionWithNoAutomaticRetries() = runTest {
    status = 201; body = Json.encodeToString(empty); repo.create()
    status = 200; repo.read(id)
    body = Json.encodeToString(Day25Result(id,"request","validation_failed",false,error=Day25Error("invalid_combined_payload","failed")))
    repo.send(id,Day25Message(" U1 ",0))
    status = 204; body = ""; repo.delete(id)
    assertEquals(listOf(
      "POST /api/v1/day25/sessions" to "{}",
      "GET /api/v1/day25/sessions/$id" to "",
      "POST /api/v1/day25/sessions/$id/messages" to """{"message":" U1 ","expected_revision":0}""",
      "DELETE /api/v1/day25/sessions/$id" to ""), requests)
    assertFalse(client.retryOnConnectionFailure)
  }

  @Test fun savedGroundedTurnMustMatchSentMessageAndRevision() = runTest {
    val grounded = Day25Grounded("answered","answer",listOf(Day25Source("doc.md","section","chunk")),listOf(Day25Citation("chunk","quote")))
    val turn = Day25Turn(1,"request","question",grounded,"unchanged")
    val snapshot = empty.copy(revision=1,history_turn_count=1,
      history=listOf(Day25History(0,"user","question"),Day25History(1,"assistant","answer")),turns=listOf(turn))
    body = Json.encodeToString(Day25Result(id,"request","accepted",true,grounded,"unchanged",snapshot))
    assertEquals(snapshot,repo.send(id,Day25Message("question",0)).state)
    assertEquals("unknown",(runCatching { repo.send(id,Day25Message("different",0)) }.exceptionOrNull() as Day25RequestException).code)
    assertEquals("unknown",(runCatching { repo.send(id,Day25Message("question",1)) }.exceptionOrNull() as Day25RequestException).code)
  }

  @Test fun malformedSnapshotAndNon204ResetCannotBecomeSuccess() = runTest {
    body = Json.encodeToString(empty.copy(history_turn_count=1))
    assertEquals("unknown",(runCatching { repo.read(id) }.exceptionOrNull() as Day25RequestException).code)
    body = ""
    assertEquals("unknown",(runCatching { repo.delete(id) }.exceptionOrNull() as Day25RequestException).code)
    status = 404
    assertEquals("session_not_found",(runCatching { repo.read(id) }.exceptionOrNull() as Day25RequestException).code)
    status = 409
    assertEquals("reconciliation_required",(runCatching { repo.read(id) }.exceptionOrNull() as Day25RequestException).code)
  }
}
