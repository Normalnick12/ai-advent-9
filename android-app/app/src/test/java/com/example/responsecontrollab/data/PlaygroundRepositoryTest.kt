package com.example.responsecontrollab.data

import com.example.responsecontrollab.PlaygroundFixture
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class PlaygroundRepositoryTest {
  private val json=Json { ignoreUnknownKeys=true }
  private fun repo(server: MockWebServer)=DefaultPlaygroundRepository(Retrofit.Builder().baseUrl(server.url("/"))
    .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build().create(PlaygroundApi::class.java))
  @Test fun lifecycle409IsExpectedResultAndRecoveryIsSuccess()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=PlaygroundFixture(); f.node("PLANNING_APPROVAL")
      val invalid=f.value.reference!!.event("IMPLEMENTATION_READY"); val rejection=f.event(invalid)
      server.enqueue(MockResponse().setResponseCode(409).setBody(json.encodeToString(rejection)))
      assertEquals(rejection,r.event(invalid))
      assertEquals(invalid,json.decodeFromString<PlaygroundEvent>(server.takeRequest().body.readUtf8()))
      val request=f.value.reference!!.event("REQUIREMENTS_REVISION_REQUIRED"); val recovered=f.event(request)
      server.enqueue(MockResponse().setBody(json.encodeToString(recovered)))
      assertEquals("recovery_applied",r.event(request).receipt.outcome); assertEquals(2,server.requestCount)
      server.enqueue(MockResponse().setBody(json.encodeToString(recovered.copy(receipt=recovered.receipt.copy(generation_calls=1)))))
      assertTrue(runCatching { r.event(request) }.isFailure)
    }
  }
  @Test fun sendValidatesRefsAndTechnicalReceiptWithoutRetry()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=PlaygroundFixture()
      val request=f.value.reference!!.send("query"); val op=f.send(request)
      server.enqueue(MockResponse().setBody(json.encodeToString(op)))
      assertEquals(op,r.send(request)); assertEquals(request,json.decodeFromString<PlaygroundSend>(server.takeRequest().body.readUtf8()))
      server.enqueue(MockResponse().setBody(json.encodeToString(op.copy(receipt=op.receipt.copy(pair_position=null)))))
      assertTrue(runCatching { r.send(request) }.isFailure); server.takeRequest()
      server.enqueue(MockResponse().setBody(json.encodeToString(op.copy(receipt=op.receipt.copy(
        sources=op.receipt.sources!!.copy(policy=op.receipt.sources!!.policy.copy(snapshot_id="bad")))))))
      assertTrue(runCatching { r.send(request) }.isFailure); server.takeRequest()
      f.technical=true; val technicalRequest=f.value.reference!!.send("next"); val technical=f.send(technicalRequest)
      server.enqueue(MockResponse().setResponseCode(500).setBody(json.encodeToString(technical)))
      assertEquals(technical,r.send(technicalRequest)); server.takeRequest()
      server.enqueue(MockResponse().setResponseCode(409).setBody("{\"error\":\"stale_task_state\",\"dispatch\":\"not_dispatched\",\"receipt\":null}"))
      val error=runCatching { r.send(technicalRequest) }.exceptionOrNull() as PlaygroundOperationException
      assertEquals("not_dispatched",error.dispatch); assertEquals(5,server.requestCount)
    }
  }
  @Test fun reviewedTypedConfigurationPreservesFalseAndAlternateValues()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=PlaygroundFixture(empty=true)
      val request=PlaygroundCreate(PlaygroundConfiguration(profile_preset="mentor",
        policy=CodingPolicyValues("MVVM","Views","RxJava",false)))
      server.enqueue(MockResponse().setBody(json.encodeToString(f.create(request))))
      assertFalse(r.create(request).policy!!.values.payment_confirmation_required)
      val sent=server.takeRequest()
      assertEquals("/api/v1/agent-playground/create-task",sent.path)
      assertEquals(request,json.decodeFromString<PlaygroundCreate>(sent.body.readUtf8()))
    }
  }
}
