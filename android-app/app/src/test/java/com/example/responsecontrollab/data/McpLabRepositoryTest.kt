package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class McpLabRepositoryTest {
  @Test fun mapsCallsAndOptionalFieldsWithoutInventingEvidence() = runTest {
    val raw = """{
      "operation_id":"op","submitted_prompt":"Exact prompt","mode":"forced",
      "response_id":"resp","outcome":"unclassified_error","invocation":"observed",
      "mcp_items":[{"type":"mcp_list_tools","tools":[]}],"imported_tools":[],
      "calls":[
        {"id":"failed","name":"get_google_maven_versions","status":"failed","error":"upstream","outcome":"unclassified_error"},
        {"id":"ok","arguments":"{\"group_id\":\"androidx.core\"}","outcome":"found",
         "parsed_result":{"status":"found","group_id":"androidx.core","artifact_id":"core-ktx",
           "versions":["2-alpha","1"],"source_url":"https://example.org","checked_at":"2026-09-22T10:00:00Z","lookup_id":"lookup"}}
      ]} """
    val decoded = Json.decodeFromString<McpLabOperationDto>(raw)
    var sent: McpLabRequestDto? = null
    val repo = DefaultMcpLabRepository(object : McpLabApi {
      override suspend fun run(request: McpLabRequestDto): McpLabOperationDto { sent = request; return decoded }
    })
    val result = repo.run("Exact prompt", "forced")
    assertEquals(McpLabRequestDto("Exact prompt", "forced"), sent)
    assertEquals(listOf("failed", "ok"), result.calls.map { it.id })
    assertEquals("failed", result.calls[0].status)
    assertNull(result.calls[1].status)
    assertNotNull(result.calls[0].error)
    assertEquals(listOf("2-alpha", "1"), result.calls[1].parsed_result?.versions)
    assertEquals("lookup", result.calls[1].parsed_result?.lookup_id)
    assertEquals(1, result.mcp_items.size)
  }

  @Test fun noCallDoesNotInventReceiptFields() {
    val result = Json.decodeFromString<McpLabOperationDto>("""{"operation_id":"op","submitted_prompt":"P",
      "mode":"auto","outcome":"not_called","invocation":"not_observed"}""")
    assertTrue(result.calls.isEmpty())
    assertNull(result.response_id)
    assertTrue(result.imported_tools.isEmpty())
  }
}
