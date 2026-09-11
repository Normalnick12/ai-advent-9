package com.example.responsecontrollab.ui.strategies

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

data class StrategyUi(val run: StrategyRun? = null, val id: String? = null, val busy: Boolean = false,
  val evaluations: Set<String> = emptySet(), val error: String? = null, val recovery: Boolean = false,
  val prepared: Int? = null, val receipts: Map<String,StrategyReceipt> = emptyMap(), val coverage: Boolean = true,
  val switches: Int? = 0, val branch: String = "A", val lastTokens: Int? = null,
  val evaluationErrors: Map<String,String> = emptyMap(), val pendingAttempts: Map<String,String> = emptyMap(),
  val unknownAttempts: Map<String,String> = emptyMap())
data class StrategiesState(val selected: String = "window", val runs: Map<String,StrategyUi> = STRATEGIES.associateWith { StrategyUi() }, val catalog: StrategyCatalog? = null, val initialized: Boolean = false, val loading: Boolean = false, val error: String? = null)

class ContextStrategiesLabViewModel(private val repository: ContextStrategiesRepository, private val prefs: StrategyPreferences) : ViewModel() {
  private val state = MutableStateFlow(StrategiesState())
  val uiState = state.asStateFlow()
  private fun update(strategy: String, block: (StrategyUi)->StrategyUi) {
    state.value = state.value.copy(runs = state.value.runs + (strategy to block(state.value.runs.getValue(strategy))))
  }
  fun initialize() {
    if (state.value.initialized || state.value.loading) return
    state.value = state.value.copy(loading=true)
    viewModelScope.launch {
      try {
        val selected = prefs.get("selected")?.takeIf { it in STRATEGIES } ?: "window"
        state.value = state.value.copy(selected=selected,catalog=repository.catalog())
        STRATEGIES.forEach { strategy ->
          val id = prefs.get("$strategy.id")
          val prepared = prefs.get("$strategy.prepared")?.toIntOrNull()?.takeIf { it in 1..8 }
          update(strategy) { it.copy(id=id,prepared=prepared,coverage=id == null,
            branch=prefs.get("branch")?.takeIf { b -> b in listOf("A","B") } ?: "A",
            switches=if (id == null) 0 else prefs.get("switches")?.toIntOrNull(),
            pendingAttempts=listOf("A","B").mapNotNull { v -> prefs.get("$strategy.pending.$v")?.let { v to it } }.toMap()) }
          if (id != null) reconcile(strategy)
        }
        state.value = state.value.copy(initialized=true,error=null)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { state.value = state.value.copy(error="Не удалось загрузить сценарий. Повторите чтение.")
      } finally { state.value = state.value.copy(loading=false) }
    }
  }
  fun select(strategy: String) {
    if (strategy !in STRATEGIES) return
    prefs.put("selected",strategy)
    state.value = state.value.copy(selected=strategy)
  }
  fun prepare() {
    val s = state.value.selected; val ui = state.value.runs.getValue(s)
    if (ui.busy || ui.recovery) return
    val next = (ui.run?.steps?.size ?: 0)+1
    if (next > 8) return
    prefs.put("$s.prepared",next.toString())
    update(s) { it.copy(prepared=next) }
  }
  fun next() {
    val s=state.value.selected; val ui=state.value.runs.getValue(s)
    if ((ui.prepared ?: 9) > (ui.run?.steps?.size ?: 0)) return
    prefs.put("$s.prepared",null); update(s) { it.copy(prepared=null) }
  }
  fun branch(target: String) {
    val ui=state.value.runs.getValue("branches")
    if (ui.run?.checkpoint == null || target !in listOf("A","B") || target == ui.branch) return
    val count=ui.switches?.plus(1)
    prefs.put("branch",target); prefs.put("switches",count?.toString())
    update("branches") { it.copy(branch=target,switches=count) }
  }
  fun send() {
    val s=state.value.selected; val ui=state.value.runs.getValue(s)
    val step=ui.prepared ?: return
    val fixture=state.value.catalog?.steps?.getOrNull(step-1) ?: return
    if (ui.busy || ui.recovery || ui.evaluations.isNotEmpty() || step != (ui.run?.steps?.size ?: 0)+1) return
    val target=if (s == "branches" && step>6) (if (step==7) "A" else "B") else "root"
    if (s == "branches" && step>6 && (ui.run?.checkpoint == null || ui.branch != target)) return
    val attempt=UUID.randomUUID().toString()
    var dispatch=false
    update(s) { it.copy(busy=true,error=null) }
    viewModelScope.launch {
      try {
        val run=ui.run ?: repository.create(s).also { created ->
          update(s) { it.copy(run=created,id=created.run_id) }
          prefs.put("$s.id",created.run_id)
          if (s=="branches") prefs.put("switches","0")
        }
        prefs.put("$s.id",run.run_id)
        dispatch=true
        val operation=repository.send(run,StrategySend(run.revision,attempt,step,target,fixture.text))
        publish(s,operation)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) {
        update(s) { it.copy(coverage=false,error="Исход Send неизвестен. Выполняется чтение подтверждённого состояния.",recovery=true,
          unknownAttempts=if(dispatch) it.unknownAttempts+(attempt to if(s=="facts") "response_or_extraction" else "response") else it.unknownAttempts) }
        reconcile(s)
      } finally { update(s) { it.copy(busy=false) } }
    }
  }
  private fun publish(s: String,op: StrategyOperation,variant: String? = null) {
    update(s) { current ->
      // Concurrent A/B HTTP completions can carry different output subsets.
      val incoming=if(variant==null) op.run.outputs else op.run.outputs.filter { it.variant==variant && it.attempt_id==op.receipt.attempt_id }
      val outputs=(current.run?.outputs.orEmpty()+incoming).associateBy { it.variant }.values.toList()
      current.copy(run=op.run.copy(outputs=outputs),receipts=current.receipts+(op.receipt.attempt_id to op.receipt),
        lastTokens=op.receipt.preflight,error=op.receipt.error?.let { "Операция не завершена: $it" })
    }
  }
  private suspend fun reconcile(s: String) {
    val id=state.value.runs.getValue(s).id ?: return
    try {
      val restored=repository.read(s,id)
      val pending=state.value.runs.getValue(s).pendingAttempts
      val run=restored.copy(outputs=restored.outputs.filter { pending[it.variant]==null || pending[it.variant]==it.attempt_id })
      update(s) { it.copy(run=run,recovery=run.busy.isNotEmpty(),error=if (run.busy.isNotEmpty()) "Операция ещё выполняется. Повторите чтение позже." else null,
        evaluationErrors=it.evaluationErrors + pending.filter { (v,a) -> run.outputs.none { o -> o.variant==v && o.attempt_id==a } }.mapValues { "Исход неизвестен; повтор только по явному действию." }) }
    } catch (e: CancellationException) { throw e
    } catch (_: Exception) { update(s) { it.copy(recovery=true,error="Не удалось прочитать run. Повторите чтение или сбросьте эксперимент.") } }
  }
  fun refresh() {
    val s=state.value.selected
    if (state.value.runs.getValue(s).busy) return
    viewModelScope.launch { reconcile(s) }
  }
  fun checkpoint() {
    val s="branches"; val ui=state.value.runs.getValue(s); val run=ui.run ?: return
    if (ui.busy || ui.recovery || ui.evaluations.isNotEmpty() || run.steps.size!=6 || run.checkpoint!=null) return
    update(s) { it.copy(busy=true) }
    viewModelScope.launch {
      try { val updated=repository.checkpoint(run); update(s) { it.copy(run=updated) }; prefs.put("branch","A"); update(s) { it.copy(branch="A") }
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { reconcile(s)
      } finally { update(s) { it.copy(busy=false) } }
    }
  }
  fun evaluate(variant: String) {
    val s=state.value.selected; val ui=state.value.runs.getValue(s); val run=ui.run ?: return
    if (variant !in listOf("A","B") || ui.busy || ui.recovery || variant in ui.evaluations || run.steps.size!=8) return
    val attempt=UUID.randomUUID().toString()
    prefs.put("$s.pending.$variant",attempt)
    update(s) { it.copy(evaluations=it.evaluations+variant,evaluationErrors=it.evaluationErrors-variant,
      pendingAttempts=it.pendingAttempts+(variant to attempt),run=it.run?.copy(outputs=it.run.outputs.filter { o -> o.variant!=variant })) }
    viewModelScope.launch {
      try {
        val result=repository.evaluate(run,variant,attempt)
        publish(s,result,variant)
        if(result.run.outputs.any { it.variant==variant && it.attempt_id==attempt }) {
          prefs.put("$s.pending.$variant",null)
          update(s) { it.copy(pendingAttempts=it.pendingAttempts-variant) }
        }
        if (result.receipt.error != null) update(s) { it.copy(evaluationErrors=it.evaluationErrors+(variant to result.receipt.error)) }
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { update(s) { it.copy(coverage=false,unknownAttempts=it.unknownAttempts+(attempt to "response")) }; reconcile(s)
      } finally { update(s) { it.copy(evaluations=it.evaluations-variant) } }
    }
  }
  fun reset() {
    val s=state.value.selected; val ui=state.value.runs.getValue(s)
    if (ui.busy || ui.evaluations.isNotEmpty()) return
    update(s) { it.copy(busy=true) }
    viewModelScope.launch {
      try {
        ui.id?.let { repository.reset(s,it) }
        prefs.put("$s.id",null); prefs.put("$s.prepared",null)
        listOf("A","B").forEach { prefs.put("$s.pending.$it",null) }
        if (s=="branches") { prefs.put("branch","A"); prefs.put("switches","0") }
        update(s) { StrategyUi() }
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { update(s) { it.copy(error="Сброс не подтверждён. Повторите чтение.",recovery=true) }
      } finally { update(s) { it.copy(busy=false) } }
    }
  }
  companion object {
    fun factory(repository: ContextStrategiesRepository,prefs: StrategyPreferences) = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = ContextStrategiesLabViewModel(repository,prefs) as T
    }
  }
}
