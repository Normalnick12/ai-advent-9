package com.example.responsecontrollab.data

import com.example.responsecontrollab.InvariantsFixture
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

class InvariantsRepositoryTest {
  private val json=Json { ignoreUnknownKeys=true }
  private fun repo(s: MockWebServer)=DefaultInvariantsRepository(Retrofit.Builder().baseUrl(s.url("/"))
    .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build().create(InvariantsApi::class.java))
  @Test fun catalogSourceReferencesAndZeroCallRefusal()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=InvariantsFixture()
      server.enqueue(MockResponse().setBody(json.encodeToString(f.catalog())))
      assertEquals(listOf("compatible-retry","conflicting-stack"),r.catalog().actions.map { it.action_id }); server.takeRequest()
      val req=f.value.proposal("conflicting-stack"); val op=f.propose(req)
      server.enqueue(MockResponse().setBody(json.encodeToString(op)))
      assertEquals(op,r.propose(req)); val sent=server.takeRequest()
      assertEquals("/api/v1/invariants/proposals",sent.path)
      assertEquals(req,json.decodeFromString<InvariantProposalRequest>(sent.body.readUtf8()))
      assertEquals("not_dispatched",op.observation.provider_dispatch); assertEquals("committed",op.observation.turn.commit_status)
      server.enqueue(MockResponse().setBody(json.encodeToString(op.copy(observation=op.observation.copy(policy=op.observation.policy.copy(snapshot_id="bad"))))))
      assertTrue(runCatching { r.propose(req) }.isFailure)
    }
  }
  @Test fun technicalHttpResponseRetainsReceiptAndNoRetry()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=InvariantsFixture(); f.technical=true
      val req=f.value.proposal("compatible-retry"); val op=f.propose(req)
      server.enqueue(MockResponse().setResponseCode(500).setBody(json.encodeToString(op)))
      assertEquals(op,r.propose(req)); assertEquals(1,server.requestCount)
      server.enqueue(MockResponse().setResponseCode(409).setBody("{\"error\":\"stale_policy\",\"dispatch\":\"not_dispatched\"}"))
      val e=runCatching { r.propose(req) }.exceptionOrNull() as InvariantsOperationException
      assertEquals("not_dispatched",e.dispatch); assertEquals(2,server.requestCount)
    }
  }
}
