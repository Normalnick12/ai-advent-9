package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class DependencyWatchRepositoryTest {
  @Test fun mapsEveryCallAndNullCounts() = runTest {
    val raw = """{"operation_id":"op","submitted_prompt":"P","operation":"summary",
      "outcome":"completed","invocation":"observed","calls":[
        {"id":"failed","outcome":"tool_error"},
        {"id":"ok","outcome":"completed","summary":{"watch_id":"w","group_id":"g","artifact_id":"a",
          "interval_seconds":3600,"max_runs":3,"created_at":"t","status":"active","runs_total":0,
          "skipped_slots":0,"first_version_count":null,"last_version_count":null}}]}"""
    val decoded = Json.decodeFromString<WatchOperationDto>(raw)
    var sent: WatchRequestDto? = null
    val repo = DefaultDependencyWatchRepository(object : DependencyWatchApi {
      override suspend fun run(request: WatchRequestDto): WatchOperationDto { sent = request; return decoded }
    })
    val request = WatchRequestDto("P", "summary", "w")
    val result = repo.run(request)
    assertEquals(request, sent)
    assertEquals(listOf("failed", "ok"), result.calls.map { it.id })
    assertNull(result.calls[1].summary?.last_version_count)
    assertNull(result.calls[1].status)
    assertFalse(createBackendHttpClient().retryOnConnectionFailure)
  }
}
