package com.example.responsecontrollab.ui.strategies

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.UUID

@OptIn(ExperimentalCoroutinesApi::class)
class ContextStrategiesViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()
  @Test fun v3PreferencesLeaveV1V2UntouchedAndStartWithoutRuns() = runTest {
    val historicalName = "context_strategies_day10-gpt4o-mini-n6-v1"
    val old = mutableMapOf("selected" to "facts", "branch" to "B", "switches" to "4")
    STRATEGIES.forEach { old["$it.id"] = UUID.randomUUID().toString(); old["$it.prepared"] = "4"; old["$it.pending.A"] = "historical-attempt" }
    val before = old.toMap()
    val secondName = "context_strategies_day10-gpt4o-mini-n6-v2"
    val files = mutableMapOf(historicalName to old, secondName to old.toMutableMap())
    val opened = mutableListOf<String>()
    val preferences = SharedStrategyPreferences { name ->
      opened += name
      memoryPreferences(files.getOrPut(name) { mutableMapOf() })
    }
    assertEquals("day10-gpt4o-mini-n6-v3", STRATEGIES_VERSION)
    assertEquals(listOf("context_strategies_day10-gpt4o-mini-n6-v3"), opened)
    val f = Fixture()
    val vm = ContextStrategiesLabViewModel(f, preferences)
    vm.initialize(); advanceUntilIdle()
    STRATEGIES.forEach { vm.select(it); vm.prepare() }
    assertEquals(0, f.creates); assertEquals(0, f.sends); assertEquals(0, f.evals); assertEquals(0, f.reads)
    vm.uiState.value.runs.values.forEach {
      assertNull(it.id); assertNull(it.run); assertTrue(it.receipts.isEmpty()); assertTrue(it.pendingAttempts.isEmpty())
      assertEquals("A", it.branch); assertEquals(0, it.switches)
    }
    assertEquals(before, files.getValue(historicalName))
    assertEquals(before, files.getValue(secondName))
    vm.select("window"); vm.send(); advanceUntilIdle()
    assertEquals(1, f.creates); assertEquals(1, f.sends)
    val cold = ContextStrategiesLabViewModel(f, preferences)
    cold.initialize(); advanceUntilIdle()
    assertEquals(1, cold.uiState.value.runs.getValue("window").run!!.revision)
    assertNull(cold.uiState.value.runs.getValue("facts").run)
    assertTrue(cold.uiState.value.runs.values.all { it.receipts.isEmpty() && it.run?.outputs.orEmpty().isEmpty() })
    assertEquals(before, files.getValue(historicalName))
    assertEquals(before, files.getValue(secondName))
    assertEquals(1, f.reads); assertEquals(1, f.creates); assertEquals(1, f.sends); assertEquals(0, f.evals)
  }
  @Test fun selectorPreparationAndRestorationNeverGenerate() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    vm.select("facts"); vm.prepare(); vm.select("window"); vm.select("facts")
    assertEquals(1,vm.uiState.value.runs.getValue("facts").prepared)
    assertEquals(0,f.sends); assertEquals(0,f.creates)
    vm.send(); vm.send(); advanceUntilIdle()
    assertEquals(1,f.sends); assertEquals(f.catalog().steps[0].text,f.lastText)
    vm.select("window"); assertNull(vm.uiState.value.runs.getValue("window").run)
    val cold=f.vm(); cold.initialize(); advanceUntilIdle()
    assertEquals(1,cold.uiState.value.runs.getValue("facts").run!!.steps.size)
    assertFalse(cold.uiState.value.runs.getValue("facts").coverage)
    assertEquals(1,f.sends)
  }
  @Test fun lostCommittedSendReconcilesWithoutReplayAndKeepsExactProgress() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle(); f.loseSend=true
    vm.prepare(); vm.send(); advanceUntilIdle()
    assertEquals(1,vm.uiState.value.runs.getValue("window").run!!.steps.size)
    vm.send(); advanceUntilIdle(); assertEquals(1,f.sends)
    assertFalse(vm.uiState.value.runs.getValue("window").coverage)
    vm.next(); vm.prepare(); assertEquals(2,vm.uiState.value.runs.getValue("window").prepared)
  }
  @Test fun independentSlotsReverseCompletionAndSourceStrategy() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    repeat(8) { vm.prepare(); vm.send(); advanceUntilIdle(); vm.next() }
    f.gates["A"]=CompletableDeferred(); f.gates["B"]=CompletableDeferred()
    vm.evaluate("A"); vm.evaluate("A"); vm.evaluate("B"); runCurrent()
    assertEquals(setOf("A","B"),vm.uiState.value.runs.getValue("window").evaluations)
    vm.select("facts")
    f.gates.getValue("B").complete(Unit); runCurrent()
    assertEquals(listOf("B"),vm.uiState.value.runs.getValue("window").run!!.outputs.map { it.variant })
    f.gates.getValue("A").complete(Unit); advanceUntilIdle()
    val ui=vm.uiState.value.runs.getValue("window")
    assertEquals(setOf("A","B"),ui.run!!.outputs.map { it.variant }.toSet())
    assertEquals(8,ui.run.revision); assertEquals(8,f.sends); assertEquals(2,f.evals)
    assertNull(vm.uiState.value.runs.getValue("facts").run)
    assertEquals(10,totals(ui.receipts.values,false).calls)
  }
  @Test fun explicitBranchTargetCheckpointAndManagementCounts() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle(); vm.select("branches")
    repeat(6) { vm.prepare(); vm.send(); advanceUntilIdle(); vm.next() }
    vm.prepare(); vm.send(); advanceUntilIdle(); assertEquals(6,f.sends)
    vm.checkpoint(); advanceUntilIdle(); vm.send(); advanceUntilIdle(); vm.next(); vm.prepare()
    vm.send(); advanceUntilIdle(); assertEquals(7,f.sends)
    vm.branch("B"); vm.send(); advanceUntilIdle()
    assertEquals("B",f.lastTarget); assertEquals(8,f.sends)
    assertEquals(1,vm.uiState.value.runs.getValue("branches").switches)
    assertEquals(9,vm.uiState.value.runs.getValue("branches").run!!.revision)
    assertEquals(0,totals(vm.uiState.value.runs.getValue("branches").receipts.values,true).calls)
  }
  @Test fun phaseTotalsDeduplicateAndUnknownIsNotFree() {
    val known=StrategyReceipt("a","completed",response=StrategyPhase(true,"completed",StrategyUsage(10,2,12)))
    val unknown=StrategyReceipt("b","error",extraction=StrategyPhase(true,"error"))
    assertEquals(12,totals(listOf(known,known),false).total.toInt())
    assertEquals(1,totals(listOf(unknown),true).calls)
    assertFalse(totals(listOf(unknown),true).complete)
    val inconsistent=known.copy(response=StrategyPhase(true,"completed",StrategyUsage(10,2,99)))
    assertFalse(totals(listOf(inconsistent),false).complete)
    assertEquals(12,totals(listOf(inconsistent),false).total.toInt())
  }
}

private class Fixture : ContextStrategiesRepository,StrategyPreferences {
  val preferences=mutableMapOf<String,String>(); val runs=mutableMapOf<String,StrategyRun>()
  var reads=0; var sends=0; var creates=0; var evals=0; var loseSend=false; var lastText=""; var lastTarget=""
  val gates=mutableMapOf<String,CompletableDeferred<Unit>>()
  fun vm()=ContextStrategiesLabViewModel(this,this)
  override fun get(key:String)=preferences[key]
  override fun put(key:String,value:String?) { if(value==null) preferences.remove(key) else preferences[key]=value }
  override suspend fun catalog()=StrategyCatalog(STRATEGIES_SCENARIO,(1..8).map { StrategyFixture(it,"Шаг $it","Exact user $it\nПолный текст",listOf("Compact $it")) },mapOf("A" to "Q A","B" to "Q B"))
  override suspend fun create(strategy:String): StrategyRun { creates++; return StrategyRun(UUID.randomUUID().toString(),strategy,revision=0).also { runs[strategy]=it } }
  override suspend fun read(strategy:String,id:String): StrategyRun { reads++; return runs.getValue(strategy) }
  override suspend fun send(run:StrategyRun,body:StrategySend): StrategyOperation {
    sends++; lastText=body.message; lastTarget=body.target
    val updated=run.copy(revision=run.revision+1,steps=run.steps+StrategyStep(body.step_id,body.target,"u${body.step_id}","a${body.step_id}",run.revision+1))
    runs[run.strategy]=updated
    if(loseSend) error("lost response")
    return StrategyOperation(StrategyReceipt(body.attempt_id,"completed",true,response=StrategyPhase(true,"completed",StrategyUsage(10,2,12))),updated)
  }
  override suspend fun checkpoint(run:StrategyRun)=run.copy(revision=run.revision+1,checkpoint=12).also { runs[run.strategy]=it }
  override suspend fun evaluate(run:StrategyRun,variant:String,attempt:String): StrategyOperation {
    evals++; gates[variant]?.await()
    val output=StrategyOutput("snapshot",run.revision,variant,attempt,"completed",quality=StrategyMetric(7),retention=StrategyMetric(5))
    val updated=run.copy(outputs=listOf(output))
    return StrategyOperation(StrategyReceipt(attempt,"completed",response=StrategyPhase(true,"completed",StrategyUsage(10,2,12))),updated)
  }
  override suspend fun reset(strategy:String,id:String) { runs.remove(strategy) }
}

// Implements only the Android preference methods used by the real adapter; no emulator needed.
private fun memoryPreferences(values: MutableMap<String, String>): android.content.SharedPreferences {
  val pending = mutableMapOf<String, String?>()
  lateinit var editor: android.content.SharedPreferences.Editor
  editor = java.lang.reflect.Proxy.newProxyInstance(
    android.content.SharedPreferences.Editor::class.java.classLoader,
    arrayOf(android.content.SharedPreferences.Editor::class.java)
  ) { _, method, args ->
    when (method.name) {
      "putString" -> { pending[args!![0] as String] = args[1] as String?; editor }
      "commit" -> { pending.forEach { (key, value) -> if (value == null) values.remove(key) else values[key] = value }; pending.clear(); true }
      else -> error("Unexpected editor operation: ${method.name}")
    }
  } as android.content.SharedPreferences.Editor
  return java.lang.reflect.Proxy.newProxyInstance(
    android.content.SharedPreferences::class.java.classLoader,
    arrayOf(android.content.SharedPreferences::class.java)
  ) { _, method, args ->
    when (method.name) {
      "getString" -> values[args!![0] as String] ?: args[1]
      "edit" -> editor
      else -> error("Unexpected preference operation: ${method.name}")
    }
  } as android.content.SharedPreferences
}
