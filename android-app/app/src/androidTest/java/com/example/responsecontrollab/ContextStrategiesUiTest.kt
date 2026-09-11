package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.height
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.strategies.*
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class ContextStrategiesUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=StrategiesUiRepository()
  private val prefs=strategiesUiPreferences()
  private lateinit var vm: ContextStrategiesLabViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,ContextStrategiesLabViewModel.factory(repo,prefs))["day10",ContextStrategiesLabViewModel::class.java]
    }
    rule.activityRule.scenario.recreate(); open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_10"))
    rule.onNodeWithTag("day_10").performClick()
    rule.waitUntil { vm.uiState.value.initialized }
  }
  private fun text(value:String) = rule.onNodeWithText(value).also {
    rule.onNodeWithTag("strategies_scroll").performScrollToNode(hasText(value))
  }
  private fun select(s:String) {
    rule.onNodeWithTag("strategies_scroll").performScrollToNode(hasTestTag("strategy_$s"))
    rule.onNodeWithTag("strategy_$s").performClick()
  }
  private fun send(step:Int) {
    text("Подготовить шаг").performClick()
    text("Отправить шаг").performClick()
    rule.waitUntil { vm.uiState.value.runs.getValue(vm.uiState.value.selected).run?.steps?.size==step }
    if(step<8) text("Далее").performClick()
  }
  @Test fun preparationRawDisclosureCompactCardsAndRecreationDoNotReplay() {
    text("Подготовить шаг").performClick()
    text("Показать исходное сообщение").performClick()
    rule.onNodeWithTag("fixture_raw").assertTextEquals(repo.fixtures[0].text)
    rule.runOnIdle { assertEquals(0,repo.sends); assertEquals(0,repo.creates) }
    text("Отправить шаг").performClick()
    rule.waitUntil { repo.sends==1 }
    rule.activityRule.scenario.recreate()
    text("Шаг подтверждён").assertIsDisplayed()
    rule.runOnIdle { assertEquals(repo.fixtures[0].text,repo.lastText); assertEquals(1,repo.sends) }
    select("facts"); rule.runOnIdle { assertNull(vm.uiState.value.runs.getValue("facts").run) }
    select("window"); text("Шаг подтверждён").assertIsDisplayed()
    text("Сравнить стратегии").performClick()
    text("Сравнение стратегий").assertIsDisplayed()
    rule.activityRule.scenario.recreate(); text("Назад к сценарию").performClick()
    Espresso.pressBack(); open()
    rule.runOnIdle { assertEquals(1,repo.sends); assertEquals(0,repo.evals) }
  }
  @Test fun factsInspectorAndFullBranchWorkflowHaveExplicitEvaluations() {
    select("facts"); send(1)
    text("Показать факты").performClick()
    text("shared.goal → actual extracted value").assertIsDisplayed()
    text("shared.email_reminders → отменено").assertIsDisplayed()
    Espresso.pressBack(); select("branches")
    for(step in 1..6) send(step)
    text("Создать checkpoint").performClick()
    rule.waitUntil { vm.uiState.value.runs.getValue("branches").run?.checkpoint==12 }
    send(7)
    rule.onNodeWithTag("strategies_scroll").performScrollToNode(hasTestTag("branch_B"))
    rule.onNodeWithTag("branch_B").performClick()
    rule.onNodeWithText("reply A").assertDoesNotExist()
    send(8)
    text("Проверить ТЗ A").performClick()
    rule.waitUntil { repo.evals==1 }
    rule.runOnIdle { assertEquals(8,vm.uiState.value.runs.getValue("branches").run!!.steps.size) }
    text("Проверить ТЗ B").performClick()
    rule.waitUntil { repo.evals==2 }
    text("Сравнить стратегии").performClick()
    text("Изоляция веток: выполнено").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1,repo.checkpoints); assertEquals(9,repo.sends) }
  }
  @Test fun ordinarySmallScreenCanScrollToSendAndDashboard() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.setContent {
        com.example.responsecontrollab.theme.ResponseControlLabTheme {
          androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.width(320.dp).height(480.dp)) {
            ContextStrategiesLabScreen(vm) {}
          }
        }
      }
    }
    text("Подготовить шаг").performClick()
    text("Показать исходное сообщение").performClick()
    text("Отправить шаг").assertIsDisplayed().performClick()
    rule.waitUntil { repo.sends==1 }
    text("Сравнить стратегии").assertIsDisplayed().performClick()
    text("Сравнение стратегий").assertIsDisplayed()
    rule.runOnIdle { assertEquals(0,repo.evals) }
  }

  @Test fun processRestoreReadsDurableRunWithoutGeneration() {
    send(1)
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,ContextStrategiesLabViewModel.factory(repo,prefs))["day10",ContextStrategiesLabViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    rule.waitUntil { vm.uiState.value.initialized }
    rule.runOnIdle {
      assertEquals(1,vm.uiState.value.runs.getValue("window").run!!.steps.size)
      assertFalse(vm.uiState.value.runs.getValue("window").coverage)
      assertEquals(1,repo.sends)
    }
    text("Сравнить стратегии").performClick()
    text("Покрытие: неполное / неизвестно").assertIsDisplayed()
  }
}

fun strategiesUiPreferences() = object: StrategyPreferences {
  private val values=mutableMapOf<String,String>()
  override fun get(key:String)=values[key]
  override fun put(key:String,value:String?) { if(value==null) values.remove(key) else values[key]=value }
}

class StrategiesUiRepository : ContextStrategiesRepository {
  var creates=0; var sends=0; var evals=0; var checkpoints=0; var lastText=""
  val fixtures=(1..8).map { StrategyFixture(it,"Требования $it","Полное исходное сообщение $it\nuser_value=exact_$it",listOf("Краткое описание $it")) }
  private val runs=mutableMapOf<String,StrategyRun>()
  override suspend fun catalog()=StrategyCatalog(STRATEGIES_SCENARIO,fixtures,mapOf("A" to "Вопрос A","B" to "Вопрос B"))
  override suspend fun create(strategy:String): StrategyRun { creates++; return StrategyRun(UUID.randomUUID().toString(),strategy,revision=0).also { runs[strategy]=it } }
  override suspend fun read(strategy:String,id:String)=runs.getValue(strategy)
  override suspend fun send(run:StrategyRun,body:StrategySend): StrategyOperation {
    sends++; lastText=body.message
    val facts=if(run.strategy=="facts") listOf(StrategyFact("shared","goal","goal",JsonPrimitive("actual extracted value"),"set","u","e"),StrategyFact("shared","email_reminders","preference",null,"cleared","u","e")) else emptyList()
    val updated=run.copy(revision=run.revision+1,steps=run.steps+StrategyStep(body.step_id,body.target,"u${body.step_id}","a${body.step_id}",run.revision+1),
      counts=run.counts+(body.target to ((run.counts[body.target] ?: 0)+2)),latest=run.latest+(body.target to "reply ${body.target}"),facts=facts)
    runs[run.strategy]=updated
    return StrategyOperation(StrategyReceipt(body.attempt_id,"completed",true,reply="reply ${body.target}",preflight=123,response=StrategyPhase(true,"completed",StrategyUsage(10,2,12))),updated)
  }
  override suspend fun checkpoint(run:StrategyRun): StrategyRun { checkpoints++; return run.copy(checkpoint=12,revision=run.revision+1).also { runs[run.strategy]=it } }
  override suspend fun evaluate(run:StrategyRun,variant:String,attempt:String): StrategyOperation {
    evals++
    val output=StrategyOutput("snapshot",run.revision,variant,attempt,"completed","{}",StrategyMetric(7),StrategyMetric(8),true)
    val updated=run.copy(outputs=run.outputs.filter { it.variant!=variant }+output)
    runs[run.strategy]=updated
    return StrategyOperation(StrategyReceipt(attempt,"completed",response=StrategyPhase(true,"completed",StrategyUsage(10,2,12))),updated)
  }
  override suspend fun reset(strategy:String,id:String) { runs.remove(strategy) }
}
