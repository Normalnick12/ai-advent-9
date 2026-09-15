package com.example.responsecontrollab.data

import com.example.responsecontrollab.ProfileFixture
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class PersonalizationRepositoryTest {
  private val json=Json { ignoreUnknownKeys=true }
  @Test fun typedFormatSerializesRequiredZeroRevisionsAndCompatibleFlags() {
    val f=ProfileFixture().mentor.copy(constraints=ProfileConstraints(true,true,true))
    val encoded=json.encodeToString(ProfileEdit("owner",f,0))
    assertTrue(encoded.contains("\"expected_revision\":0")); assertFalse(encoded.contains("max_bullets"))
    val decoded=json.decodeFromString<ProfileEdit>(encoded)
    assertTrue(decoded.fields.constraints.skip_basic_explanations && decoded.fields.constraints.explain_unfamiliar_terms)
    for(bad in listOf("{\"kind\":\"teaching_sections\",\"max_bullets\":3}","{\"kind\":\"summary_bullets\",\"max_bullets\":6}")) {
      assertTrue(runCatching { json.decodeFromString<ProfileFormat>(bad) }.isFailure)
    }
  }
  private fun repository(server: MockWebServer)=DefaultPersonalizationRepository(Retrofit.Builder().baseUrl(server.url("/"))
    .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build().create(PersonalizationApi::class.java))
  @Test fun authoritativeReadRejectsForeignOwnerBindingAndDoesNotRetry()=runTest {
    MockWebServer().use { server ->
      val fixture=ProfileFixture().apply { prepared() }; val repo=repository(server)
      server.enqueue(MockResponse().setBody(json.encodeToString(fixture.value)))
      assertEquals(fixture.value,repo.current())
      server.enqueue(MockResponse().setBody(json.encodeToString(fixture.value.copy(binding=fixture.value.binding!!.copy(owner_id="wrong")))))
      assertTrue(runCatching { repo.current() }.isFailure)
      assertEquals(2,server.requestCount)
    }
  }
  @Test fun probeChecksActualUsedSnapshotAndRequestBody()=runTest {
    MockWebServer().use { server ->
      val fixture=ProfileFixture().apply { prepared() }; val repo=repository(server)
      val req=ProfileProbe(fixture.value.snapshot(),fixture.value.comparison!!.comparison_id,"A")
      val response=fixture.probe(req)
      server.enqueue(MockResponse().setBody(json.encodeToString(response)))
      assertEquals(response,repo.probe(req))
      val recorded=server.takeRequest()
      assertEquals("/api/v1/profile-personalization/probe",recorded.path)
      assertEquals(req,json.decodeFromString<ProfileProbe>(recorded.body.readUtf8()))
      server.enqueue(MockResponse().setBody(json.encodeToString(response.copy(observation=response.observation.copy(memory=response.observation.memory.copy(snapshot_id="f".repeat(64)))))))
      assertTrue(runCatching { repo.probe(req) }.isFailure)
      assertEquals(2,server.requestCount)
    }
  }
}
