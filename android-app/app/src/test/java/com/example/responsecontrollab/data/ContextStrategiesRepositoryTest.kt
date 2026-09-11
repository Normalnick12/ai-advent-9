package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.MediaType.Companion.toMediaType
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class ContextStrategiesRepositoryTest {
  @Test fun historicalMetadataCannotPopulateV3StateOrTriggerFallback() = runTest {
    val server = MockWebServer(); server.start()
    try {
      val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
      val repo = DefaultContextStrategiesRepository(Retrofit.Builder().baseUrl(server.url("/"))
        .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build().create(ContextStrategiesApi::class.java))
      val id = "11111111-1111-4111-8111-111111111111"
      listOf("day10-gpt4o-mini-n6-v1", "day10-gpt4o-mini-n6-v2").forEach { historicalVersion ->
      STRATEGIES.forEach { strategy ->
        val old = StrategyRun(id, strategy, config_version = historicalVersion, revision = 0)
        server.enqueue(MockResponse().setBody(json.encodeToString(old)))
        assertTrue(runCatching { repo.read(strategy, id) }.isFailure)
        assertEquals("/api/v1/context-strategies/$strategy/runs/$id", server.takeRequest().path)
      }
      }
      assertEquals(6, server.requestCount) // Read only: no migration/create/evaluation fallback.
    } finally { server.shutdown() }
  }

  @Test fun exactBodyAndIdentityValidationThroughHttp() = runTest {
    val server=MockWebServer(); server.start()
    try {
      val json=Json { ignoreUnknownKeys=true; encodeDefaults=true }
      val repo=DefaultContextStrategiesRepository(Retrofit.Builder().baseUrl(server.url("/"))
        .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build().create(ContextStrategiesApi::class.java))
      val id="11111111-1111-4111-8111-111111111111"; val attempt="22222222-2222-4222-8222-222222222222"
      val run=StrategyRun(id,"window",revision=0)
      val operation=StrategyOperation(StrategyReceipt(attempt,"error"),run)
      server.enqueue(MockResponse().setBody(json.encodeToString(operation)))
      repo.send(run,StrategySend(0,attempt,1,"root"," Raw exact\nтекст "))
      val req=server.takeRequest(); val body=json.parseToJsonElement(req.body.readUtf8()).jsonObject
      assertEquals("/api/v1/context-strategies/window/runs/$id/messages",req.path)
      assertEquals(setOf("expected_revision","attempt_id","step_id","target","message","config_version","scenario_version"),body.keys)
      assertEquals(" Raw exact\nтекст ",body.getValue("message").jsonPrimitive.content)
      assertEquals(STRATEGIES_VERSION,body.getValue("config_version").jsonPrimitive.content)
      server.enqueue(MockResponse().setBody(json.encodeToString(run.copy(strategy="facts"))))
      assertTrue(runCatching { repo.read("window",id) }.isFailure)
      assertFalse(createBackendHttpClient().retryOnConnectionFailure)
      assertEquals(2,server.requestCount)
    } finally { server.shutdown() }
  }
}
