package com.example.responsecontrollab.data

import com.example.responsecontrollab.TaskFixture
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

class TaskStateRepositoryTest {
  private val json=Json { ignoreUnknownKeys=true }
  private fun repo(s: MockWebServer)=DefaultTaskStateRepository(Retrofit.Builder().baseUrl(s.url("/"))
    .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build().create(TaskStateApi::class.java))
  @Test fun rejectsForeignTaskBadStatusRevisionReadinessAndPausedEvents()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val c=TaskFixture().value; val s=c.task_state!!
      server.enqueue(MockResponse().setBody(json.encodeToString(c))); assertEquals(c,r.current())
      for(bad in listOf(c.copy(task_state=s.copy(task_id=c.memory!!.session_id)),c.copy(task_state=s.copy(status="UNKNOWN")),
        c.copy(task_state=s.copy(revision=-1)),c.copy(ready=false),c.copy(task_state=s.copy(status="PAUSED")))) {
        server.enqueue(MockResponse().setBody(json.encodeToString(bad))); assertTrue(runCatching { r.current() }.isFailure)
      }
      val partial=c.copy(task_state=null,readiness=TaskReadiness(true,true,false),ready=false)
      server.enqueue(MockResponse().setBody(json.encodeToString(partial))); assertEquals(partial,r.current())
      assertEquals(7,server.requestCount)
    }
  }
  @Test fun actualReceiptChecksSourceRevisionsAndEventBodyCannotSetState()=runTest {
    MockWebServer().use { server ->
      val r=repo(server); val f=TaskFixture(); val snapshot=f.value.snapshot(); val response=f.probe(snapshot)
      server.enqueue(MockResponse().setBody(json.encodeToString(response))); assertEquals(response,r.probe(snapshot))
      assertEquals(snapshot,json.decodeFromString<TaskRequestSnapshot>(server.takeRequest().body.readUtf8()))
      val bad=response.copy(observation=response.observation.copy(stored_state=response.observation.stored_state.copy(revision=99)))
      server.enqueue(MockResponse().setBody(json.encodeToString(bad))); assertTrue(runCatching { r.probe(snapshot) }.isFailure)
      server.takeRequest()
      val event=TaskEvent(f.value.reference(),"PAUSE")
      server.enqueue(MockResponse().setBody(json.encodeToString(f.value))); r.event(event)
      val raw=server.takeRequest().body.readUtf8(); assertFalse(raw.contains("state_id")); assertEquals(event,json.decodeFromString<TaskEvent>(raw))
      server.enqueue(MockResponse().setResponseCode(409).setBody("{\"error\":\"stale_task_state\",\"dispatch\":\"not_dispatched\"}"))
      assertTrue(runCatching { r.event(event) }.isFailure); assertEquals(4,server.requestCount)
    }
  }
}
