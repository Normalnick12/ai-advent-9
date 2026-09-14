package com.example.responsecontrollab.data

import com.example.responsecontrollab.ui.memory.MemoryFixture
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

class MemoryLayersRepositoryTest {
  @Test fun explicitWireAndReadOnlyRestore() = runTest {
    val server=MockWebServer(); server.start()
    try {
      val json=Json { ignoreUnknownKeys=true }
      val repo=DefaultMemoryLayersRepository(Retrofit.Builder().baseUrl(server.url("/"))
        .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build().create(MemoryLayersApi::class.java))
      val current=MemoryFixture().currentState
      server.enqueue(MockResponse().setBody(json.encodeToString(current)))
      assertEquals(current,repo.current())
      assertEquals("GET",server.takeRequest().method)
      server.enqueue(MockResponse().setBody(json.encodeToString(current)))
      repo.mutate(MemoryMutationRequest("a".repeat(64),"WORKING","current_architecture","remove"))
      val request=server.takeRequest()
      assertEquals("/api/v1/memory-layers/memory",request.path)
      val body=json.parseToJsonElement(request.body.readUtf8()).jsonObject
      assertEquals(setOf("snapshot_id","layer","key","operation"),body.keys)
      assertFalse(createBackendHttpClient().retryOnConnectionFailure)
      assertEquals(2,server.requestCount)
    } finally { server.shutdown() }
  }

  @Test fun rejectsBadOwnershipAndProbeMutationWithoutRetry() = runTest {
    val server=MockWebServer(); server.start()
    try {
      val json=Json { ignoreUnknownKeys=true }
      val repo=DefaultMemoryLayersRepository(Retrofit.Builder().baseUrl(server.url("/"))
        .client(createBackendHttpClient()).addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build().create(MemoryLayersApi::class.java))
      val f=MemoryFixture()
      server.enqueue(MockResponse().setBody(json.encodeToString(f.currentState.copy(
        state=f.currentState.state!!.copy(task_id=f.currentState.state!!.session_id)))))
      assertTrue(runCatching { repo.current() }.isFailure)
      val op=f.verify("A",MemorySnapshotRequest("a".repeat(64)))
      server.enqueue(MockResponse().setBody(json.encodeToString(op.copy(current=op.current.copy(
        state=op.current.state!!.copy(snapshot_id="b".repeat(64)))))))
      assertTrue(runCatching { repo.verify("A",MemorySnapshotRequest("a".repeat(64))) }.isFailure)
      assertEquals(2,server.requestCount)
    } finally { server.shutdown() }
  }
}
