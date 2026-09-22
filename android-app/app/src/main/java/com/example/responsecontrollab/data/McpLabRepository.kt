package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import retrofit2.http.Body
import retrofit2.http.POST

const val MCP_DEFAULT_PROMPT = "Получи опубликованные версии androidx.core:core-ktx из Google Maven. Укажи количество и три последних элемента в порядке источника. Не оценивай стабильность или совместимость."

@Serializable
data class McpLabRequestDto(val prompt: String, val mode: String)

@Serializable
data class MavenEvidenceDto(
  val status: String,
  val group_id: String,
  val artifact_id: String,
  val versions: List<String>,
  val source_url: String,
  val checked_at: String,
  val lookup_id: String,
)

@Serializable
data class McpCallEvidenceDto(
  val id: String? = null,
  val server_label: String? = null,
  val name: String? = null,
  val arguments: String? = null,
  val status: String? = null,
  val output: String? = null,
  val error: JsonElement? = null,
  val outcome: String,
  val parsed_result: MavenEvidenceDto? = null,
  val evidence_error: String? = null,
)

@Serializable
data class McpLabOperationDto(
  val operation_id: String,
  val submitted_prompt: String,
  val mode: String,
  val server_label: String = "android_dependencies",
  val server_url: String? = null,
  val response_id: String? = null,
  val provider_status: String? = null,
  val final_text: String? = null,
  val mcp_items: List<JsonElement> = emptyList(),
  val imported_tools: List<JsonElement> = emptyList(),
  val calls: List<McpCallEvidenceDto> = emptyList(),
  val outcome: String,
  val invocation: String,
  val error_message: String? = null,
)

interface McpLabApi {
  @POST("api/v1/mcp-tool-lab/run")
  suspend fun run(@Body request: McpLabRequestDto): McpLabOperationDto
}

fun interface McpLabRepository {
  suspend fun run(prompt: String, mode: String): McpLabOperationDto
}

class DefaultMcpLabRepository(private val api: McpLabApi) : McpLabRepository {
  override suspend fun run(prompt: String, mode: String) = api.run(McpLabRequestDto(prompt, mode))
}
