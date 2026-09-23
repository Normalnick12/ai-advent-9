package com.example.responsecontrollab.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import retrofit2.http.Body
import retrofit2.http.POST

const val WATCH_CREATE_PROMPT = "Создай наблюдение за androidx.core:core-ktx в Google Maven: interval_seconds=21600, max_runs=3. Сообщи watch_id и расписание."
const val WATCH_SUMMARY_PROMPT = "Получи сводку выбранного watch. Кратко объясни сохранённые результаты и изменения версий."

@Serializable
data class WatchRequestDto(val prompt: String, val operation: String, val watch_id: String? = null)

@Serializable
data class WatchExecutionDto(
  val run_id: String, val watch_id: String, val scheduled_at: String, val started_at: String,
  val completed_at: String? = null, val checked_at: String? = null, val state: String,
  val lookup_outcome: String? = null, val lookup_id: String? = null, val source_url: String,
  val version_count: Int? = null, val error_category: String? = null,
)

@Serializable
data class WatchFactsDto(
  val watch_id: String, val group_id: String, val artifact_id: String,
  val interval_seconds: Int, val max_runs: Int, val created_at: String,
  val next_run_at: String? = null, val status: String, val runs_total: Int, val skipped_slots: Int,
  val successful: Int = 0, val failed: Int = 0, val interrupted: Int = 0,
  val comparable_snapshots: Int = 0, val first_checked_at: String? = null, val last_checked_at: String? = null,
  val first_version_count: Int? = null, val last_version_count: Int? = null,
  val changes_detected: Int = 0, val newly_seen_versions: List<String> = emptyList(),
  val latest_execution: WatchExecutionDto? = null, val through_execution_id: String? = null,
  val generated_at: String? = null, val executions: List<WatchExecutionDto> = emptyList(),
  val running_execution: WatchExecutionDto? = null,
)

@Serializable
data class WatchCallDto(
  val id: String? = null, val server_label: String? = null, val name: String? = null,
  val arguments: String? = null, val status: String? = null, val output: String? = null,
  val error: JsonElement? = null, val outcome: String,
  val receipt: WatchFactsDto? = null, val summary: WatchFactsDto? = null,
)

@Serializable
data class WatchOperationDto(
  val operation_id: String, val submitted_prompt: String, val operation: String,
  val selected_watch_id: String? = null, val server_url: String? = null,
  val response_id: String? = null, val provider_status: String? = null, val final_text: String? = null,
  val mcp_items: List<JsonElement> = emptyList(), val calls: List<WatchCallDto> = emptyList(),
  val outcome: String, val invocation: String, val error_message: String? = null,
  val evidence_saved: Boolean = false,
)

interface DependencyWatchApi {
  @POST("api/v1/dependency-watch/run")
  suspend fun run(@Body request: WatchRequestDto): WatchOperationDto
}

fun interface DependencyWatchRepository {
  suspend fun run(request: WatchRequestDto): WatchOperationDto
}

class DefaultDependencyWatchRepository(private val api: DependencyWatchApi) : DependencyWatchRepository {
  override suspend fun run(request: WatchRequestDto) = api.run(request)
}

@Serializable
data class WatchReceipts(val watches: List<WatchFactsDto> = emptyList(), val selectedId: String? = null)

interface WatchReceiptStore {
  fun load(): WatchReceipts
  fun save(value: WatchReceipts)
}

class SharedWatchReceiptStore(context: Context) : WatchReceiptStore {
  private val prefs = context.getSharedPreferences("day18_watch_receipts_v1", Context.MODE_PRIVATE)
  private val json = Json { ignoreUnknownKeys = true }
  override fun load(): WatchReceipts = prefs.getString("snapshot", null)?.let {
    json.decodeFromString<WatchReceipts>(it)
  } ?: WatchReceipts()
  override fun save(value: WatchReceipts) {
    check(prefs.edit().putString("snapshot", json.encodeToString(value)).commit()) { "Receipt storage unavailable" }
  }
}
