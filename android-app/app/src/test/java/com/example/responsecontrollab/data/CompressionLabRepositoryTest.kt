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

class CompressionLabRepositoryTest {
  @Test fun timeoutsAreIsolatedAndRetriesDisabled() {
    val old=createBackendHttpClient(); val compression=createCompressionHttpClient()
    assertEquals(190000,old.callTimeoutMillis); assertEquals(180000,old.readTimeoutMillis)
    assertEquals(240000,compression.callTimeoutMillis); assertEquals(220000,compression.readTimeoutMillis)
    assertFalse(compression.retryOnConnectionFailure); assertEquals(old.connectTimeoutMillis,compression.connectTimeoutMillis)
  }
  @Test fun outboundContainsOnlyCurrentInputAndPartialDiagnosticsSurvive() = runTest {
    val requests=mutableListOf<String>(); val id="11111111-1111-4111-8111-111111111111"
    val json=Json { ignoreUnknownKeys=true }; var status=200; var body=""
    val http=createCompressionHttpClient().newBuilder().addInterceptor { chain ->
      val req=chain.request(); val buffer=Buffer(); req.body?.writeTo(buffer); requests+=buffer.readUtf8()
      assertTrue(req.url.encodedPath.startsWith("/api/v1/compression-lab/sessions"))
      Response.Builder().request(req).protocol(Protocol.HTTP_1_1).code(status).message("fixture")
        .body(body.toResponseBody("application/json".toMediaType())).build()
    }.build()
    val repo=DefaultCompressionLabRepository(Retrofit.Builder().baseUrl("http://test/").client(http)
      .addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build().create(CompressionLabApi::class.java))
    body=json.encodeToString(CompressionOperationDto(id,0,"r","a",status="error",errorCode="pair_storage_error",
      responsePhase=CompressionPhaseDto("completed",true,TokenLabUsageDto(inputTokens=0,outputTokens=null))))
    val result=repo.send(id," U\n ")
    assertEquals("""{"message":" U\n "}""",requests.last())
    assertEquals(0L,result.responsePhase.usage!!.inputTokens); assertNull(result.responsePhase.usage.outputTokens)
    body=json.encodeToString(result.copy(kind="compare",status="partial",full=CompressionBranchDto("error"),
      compressed=CompressionBranchDto("completed","answer",score=2)))
    val compared=repo.compare(id,"Q","three-facts-v1")
    assertEquals("""{"question":"Q","scenario_id":"three-facts-v1"}""",requests.last())
    assertEquals("answer",compared.compressed!!.reply); assertNull(compared.full!!.score)
    body=json.encodeToString(result.copy(kind="compare",committed=true))
    assertTrue(runCatching { repo.compare(id,"Q",null) }.exceptionOrNull() is ChatRequestException)
    assertEquals(3,requests.size)
  }
}
