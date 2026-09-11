package com.example.responsecontrollab.data

import android.content.Context
import android.content.SharedPreferences
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import retrofit2.http.*
import java.util.UUID

const val STRATEGIES_VERSION = "day10-gpt4o-mini-n6-v3"
const val STRATEGIES_SCENARIO = "meeting-rooms-v1"
val STRATEGIES = listOf("window", "facts", "branches")

@Serializable data class StrategyVersions(val config_version: String = STRATEGIES_VERSION, val scenario_version: String = STRATEGIES_SCENARIO)
@Serializable data class StrategyRevision(val expected_revision: Int, val config_version: String = STRATEGIES_VERSION, val scenario_version: String = STRATEGIES_SCENARIO)
@Serializable data class StrategyEvaluation(val expected_revision: Int, val attempt_id: String, val config_version: String = STRATEGIES_VERSION, val scenario_version: String = STRATEGIES_SCENARIO)
@Serializable data class StrategySend(val expected_revision: Int, val attempt_id: String, val step_id: Int, val target: String, val message: String, val config_version: String = STRATEGIES_VERSION, val scenario_version: String = STRATEGIES_SCENARIO)
@Serializable data class StrategyFixture(val step_id: Int, val title: String, val text: String, val preview: List<String>)
@Serializable data class StrategyCatalog(val scenario_version: String, val steps: List<StrategyFixture>, val questions: Map<String,String>)
@Serializable data class StrategyStep(val step_id: Int, val target: String, val user_id: String, val assistant_id: String, val revision: Int)
@Serializable data class StrategyFact(val scope: String, val key: String, val kind: String, val value: JsonPrimitive?, val state: String, val user_id: String, val evidence: String)
@Serializable data class StrategyMetric(val score: Int? = null, val total: Int = 11, val reason: String? = null)
@Serializable data class StrategyOutput(val snapshot_id: String, val revision: Int, val variant: String, val attempt_id: String, val status: String, val reply: String? = null, val quality: StrategyMetric, val retention: StrategyMetric, val isolation: Boolean? = null, val error: String? = null)
@Serializable data class StrategyRun(val run_id: String, val strategy: String, val config_version: String = STRATEGIES_VERSION, val scenario_version: String = STRATEGIES_SCENARIO, val revision: Int, val checkpoint: Int? = null, val steps: List<StrategyStep> = emptyList(), val facts: List<StrategyFact> = emptyList(), val counts: Map<String,Int> = emptyMap(), val latest: Map<String,String?> = emptyMap(), val outputs: List<StrategyOutput> = emptyList(), val busy: List<String> = emptyList())
@Serializable data class StrategyUsage(val input_tokens: Long? = null, val output_tokens: Long? = null, val total_tokens: Long? = null)
@Serializable data class StrategyPhase(val attempted: Boolean = false, val status: String = "not_attempted", val usage: StrategyUsage? = null)
@Serializable data class StrategyReceipt(val attempt_id: String, val status: String, val committed: Boolean = false, val error: String? = null, val reply: String? = null, val preflight: Int? = null, val response: StrategyPhase = StrategyPhase(), val extraction: StrategyPhase = StrategyPhase())
@Serializable data class StrategyOperation(val receipt: StrategyReceipt, val run: StrategyRun)

interface ContextStrategiesApi {
  @GET("api/v1/context-strategies/scenario") suspend fun catalog(): StrategyCatalog
  @POST("api/v1/context-strategies/{strategy}/runs") suspend fun create(@Path("strategy") strategy: String, @Body body: StrategyVersions): StrategyRun
  @GET("api/v1/context-strategies/{strategy}/runs/{id}") suspend fun read(@Path("strategy") strategy: String, @Path("id") id: String): StrategyRun
  @POST("api/v1/context-strategies/{strategy}/runs/{id}/messages") suspend fun send(@Path("strategy") strategy: String, @Path("id") id: String, @Body body: StrategySend): StrategyOperation
  @POST("api/v1/context-strategies/{strategy}/runs/{id}/checkpoint") suspend fun checkpoint(@Path("strategy") strategy: String, @Path("id") id: String, @Body body: StrategyRevision): StrategyRun
  @POST("api/v1/context-strategies/{strategy}/runs/{id}/evaluations/{variant}") suspend fun evaluate(@Path("strategy") strategy: String, @Path("id") id: String, @Path("variant") variant: String, @Body body: StrategyEvaluation): StrategyOperation
  @DELETE("api/v1/context-strategies/{strategy}/runs/{id}") suspend fun reset(@Path("strategy") strategy: String, @Path("id") id: String): JsonObject
}

interface ContextStrategiesRepository {
  suspend fun catalog(): StrategyCatalog
  suspend fun create(strategy: String): StrategyRun
  suspend fun read(strategy: String, id: String): StrategyRun
  suspend fun send(run: StrategyRun, body: StrategySend): StrategyOperation
  suspend fun checkpoint(run: StrategyRun): StrategyRun
  suspend fun evaluate(run: StrategyRun, variant: String, attempt: String): StrategyOperation
  suspend fun reset(strategy: String, id: String)
}

class DefaultContextStrategiesRepository(private val api: ContextStrategiesApi) : ContextStrategiesRepository {
  private fun StrategyRun.valid(strategy: String, id: String = run_id) = apply {
    require(run_id == id && UUID.fromString(id).toString() == id && this.strategy == strategy && strategy in STRATEGIES)
    require(config_version == STRATEGIES_VERSION && scenario_version == STRATEGIES_SCENARIO)
    require(steps.size <= 8 && revision == steps.size + if (checkpoint == null) 0 else 1)
    require(checkpoint == null || (strategy == "branches" && checkpoint == 12))
    require(steps.map { it.step_id } == (1..steps.size).toList())
    require(steps.all { it.target == if (strategy != "branches" || it.step_id <= 6) "root" else if (it.step_id == 7) "A" else "B" })
    require(counts.values.all { it >= 0 && it % 2 == 0 } && counts.values.sum() == steps.size * 2)
    require(facts.map { it.scope to it.key }.distinct().size == facts.size)
    require(facts.all { it.scope in listOf("shared","A","B") && it.state in listOf("set","cleared") && (it.state == "cleared") == (it.value == null || it.value is JsonNull) })
    require(outputs.all { it.variant in listOf("A","B") && it.revision == revision && UUID.fromString(it.attempt_id).toString() == it.attempt_id && it.quality.total == 11 && (it.quality.score == null || it.quality.score in 0..11) && (it.retention.score == null || it.retention.score in 0..11) })
  }
  override suspend fun catalog() = api.catalog().also {
    require(it.scenario_version == STRATEGIES_SCENARIO && it.steps.map { f -> f.step_id } == (1..8).toList())
    require(it.steps.all { f -> f.text.isNotBlank() && '\r' !in f.text && !f.text.endsWith('\n') })
    require(it.questions.keys == setOf("A","B"))
  }
  override suspend fun create(strategy: String) = api.create(strategy,StrategyVersions()).valid(strategy).also { require(it.revision == 0) }
  override suspend fun read(strategy: String,id: String) = api.read(strategy,id).valid(strategy,id)
  override suspend fun send(run: StrategyRun,body: StrategySend) = api.send(run.strategy,run.run_id,body).also {
    it.run.valid(run.strategy,run.run_id)
    require(it.receipt.attempt_id == body.attempt_id)
    require(it.run.revision == run.revision + if (it.receipt.committed) 1 else 0)
    if (it.receipt.committed) require(it.run.steps.last().step_id == body.step_id && it.run.steps.last().target == body.target && it.receipt.status == "completed")
  }
  override suspend fun checkpoint(run: StrategyRun) = api.checkpoint(run.strategy,run.run_id,StrategyRevision(run.revision)).valid(run.strategy,run.run_id)
  override suspend fun evaluate(run: StrategyRun,variant: String,attempt: String) = api.evaluate(run.strategy,run.run_id,variant,StrategyEvaluation(run.revision,attempt)).also {
    it.run.valid(run.strategy,run.run_id)
    require(it.run.revision == run.revision && !it.receipt.committed && it.receipt.attempt_id == attempt)
    if (it.receipt.status == "completed") require(it.run.outputs.any { o -> o.variant == variant && o.attempt_id == attempt })
  }
  override suspend fun reset(strategy: String,id: String) { api.reset(strategy,id) }
}

interface StrategyPreferences { fun get(key: String): String?; fun put(key: String,value: String?) }
class SharedStrategyPreferences internal constructor(openPreferences: (String) -> SharedPreferences) : StrategyPreferences {
  constructor(context: Context) : this({ name -> context.getSharedPreferences(name, Context.MODE_PRIVATE) })
  private val prefs = openPreferences("context_strategies_$STRATEGIES_VERSION")
  override fun get(key: String) = prefs.getString(key,null)
  override fun put(key: String,value: String?) { check(prefs.edit().putString(key,value).commit()) }
}
