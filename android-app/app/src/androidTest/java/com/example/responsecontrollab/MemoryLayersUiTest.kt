package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.memory.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class MemoryLayersUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=MemoryUiRepository()
  private lateinit var vm: MemoryLayersViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,MemoryLayersViewModel.factory(repo))[MemoryLayersViewModel.KEY,MemoryLayersViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_11"))
    rule.onNodeWithTag("day_11").performClick()
    rule.waitUntil { vm.uiState.value.initialized }
  }
  private fun click(text: String) {
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasText(text))
    rule.onNodeWithText(text).performClick()
    rule.waitForIdle()
  }
  private fun setupA() {
    click("Создать память Day 11")
    click("Отправить исходное сообщение")
    repeat(5) { click("Сохранить указанное значение") }
    rule.runOnIdle { assertEquals(listOf("A"),vm.uiState.value.current!!.applicable_stages) }
  }
  @Test fun explicitSetupInspectorPreviousSnapshotAndNavigation() {
    setupA()
    click("Проверить A")
    rule.waitUntil { repo.probes==1 }
    click("Память и контекст")
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasText("preferred_architecture=MVVM · исключено: working_override"))
    rule.onNodeWithText("preferred_architecture=MVVM · исключено: working_override").assertIsDisplayed()
    click("Показать точный запрос")
    rule.onNodeWithTag("memory_request").assertTextContains("MVI",substring=true)
    rule.onNodeWithTag("memory_request").assertTextContains("ORION-17",substring=true)
    Espresso.pressBack()
    click("B · Удалить Working architecture")
    click("Память и контекст")
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasTestTag("memory_snapshot_label"))
    rule.onNodeWithTag("memory_snapshot_label").assertTextEquals("Предыдущий снимок")
    Espresso.pressBack()
    click("Проверки A–E")
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasText("Доступно в запросе: 5/5"))
    rule.onNodeWithText("Доступно в запросе: 5/5").assertIsDisplayed()
    rule.onNodeWithText("Использовано в ответе: 4/5").assertIsDisplayed()
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasText("Следующий шаг · без оценки: Уточнить загрузку."))
    rule.onNodeWithText("Следующий шаг · без оценки: Уточнить загрузку.").assertIsDisplayed()
    rule.activityRule.scenario.recreate()
    Espresso.pressBack(); Espresso.pressBack(); open()
    rule.runOnIdle { assertEquals(1,repo.probes); assertEquals(1,repo.sends); assertEquals(6,repo.writes) }
  }
  @Test fun failedProbeShowsReasonAndUnavailableOutputAlongsideCorrectInput() {
    setupA()
    repo.probeError="fake_provider_error"
    click("Проверить A")
    click("Проверки A–E")
    rule.onNodeWithTag("memory_scroll").performScrollToNode(hasText("Доступно в запросе: 5/5"))
    rule.onNodeWithText("Доступно в запросе: 5/5").assertIsDisplayed()
    rule.onAllNodesWithText("Использовано в ответе: нет измерения")[0].assertIsDisplayed()
    rule.onNodeWithText("Причина: fake_provider_error").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1,repo.probes); assertEquals(1,vm.uiState.value.current!!.state!!.short_term.size/2) }
  }
  @Test fun lifecycleProbesAndProcessRestoreNeverReplay() {
    setupA()
    click("Проверить A")
    val before=vm.uiState.value.current!!.state
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,MemoryLayersViewModel.factory(repo))[MemoryLayersViewModel.KEY,MemoryLayersViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    rule.waitUntil { vm.uiState.value.initialized }
    rule.runOnIdle {
      assertEquals(before,vm.uiState.value.current!!.state)
      assertTrue(vm.uiState.value.results.isEmpty()); assertEquals(1,repo.probes)
    }
    click("B · Удалить Working architecture"); click("Проверить B")
    click("Новый разговор"); click("Проверить C")
    click("Новая задача"); click("Проверить D")
    click("Очистить Long-term"); click("Проверить E")
    rule.runOnIdle {
      assertEquals(5,repo.probes); assertEquals(1,repo.sends)
      assertTrue(vm.uiState.value.current!!.state!!.working.isEmpty())
      assertTrue(vm.uiState.value.current!!.state!!.long_term.isEmpty())
    }
  }
}

class MemoryUiRepository : MemoryLayersRepository {
  var probeError: String?=null
  var reads=0; var writes=0; var probes=0; var sends=0; var creates=0
  private var state: MemoryStateDto?=null
  private var serial=1
  private fun snapshot()=serial.toString(16).padStart(64,'0')
  private val long=linkedMapOf("project_code" to "ORION-17","preferred_architecture" to "MVVM")
  private val work=linkedMapOf("task" to "Checkout","current_architecture" to "MVI","release_marker" to "RC-42")
  private fun response(): MemoryCurrent {
    val s=state ?: return MemoryCurrent()
    val selectedLong=s.long_term.toMutableMap()
    val excluded=if(s.working.containsKey("current_architecture") && selectedLong.containsKey("preferred_architecture"))
      listOf(MemoryExcluded("LONG_TERM","preferred_architecture",selectedLong.remove("preferred_architecture")!!,"working_override"))
      else emptyList()
    val stage=when {
      s.working==work && s.long_term==long && s.short_term.isNotEmpty() -> "A"
      s.working==work.filterKeys { it!="current_architecture" } && s.long_term==long -> if(s.short_term.isEmpty()) "C" else "B"
      s.working.isEmpty() && s.short_term.isEmpty() && s.long_term==long -> "D"
      s.working.isEmpty() && s.short_term.isEmpty() && s.long_term.isEmpty() && s.inactive_tasks.isNotEmpty() -> "E"
      else -> null
    }
    return MemoryCurrent(s,applicable_stages=listOfNotNull(stage),preview=MemorySelection(s.working,selectedLong,excluded=excluded))
  }
  override suspend fun current(): MemoryCurrent { reads++; return response() }
  override suspend fun catalog()=MemoryCatalog("error_title=Сбой-47","same verification question",work,long)
  override suspend fun initialize(): MemoryCurrent {
    creates++
    if(state==null) state=MemoryStateDto(UUID.randomUUID().toString(),UUID.randomUUID().toString(),UUID.randomUUID().toString(),0,snapshot())
    return response()
  }
  override suspend fun mutate(body: MemoryMutationRequest): MemoryCurrent {
    writes++; serial++
    val s=state!!
    val map=(if(body.layer=="WORKING") s.working else s.long_term).toMutableMap()
    if(body.operation=="set") map[body.key]=body.value!! else map.remove(body.key)
    state=if(body.layer=="WORKING") s.copy(working=map,snapshot_id=snapshot()) else s.copy(long_term=map,snapshot_id=snapshot())
    return response()
  }
  override suspend fun transition(action: String,body: MemorySnapshotRequest): MemoryCurrent {
    serial++; val s=state!!
    state=when(action) {
      "new-task" -> s.copy(task_id=UUID.randomUUID().toString(),session_id=UUID.randomUUID().toString(),
        working=emptyMap(),short_term=emptyList(),inactive_tasks=s.inactive_tasks+s.task_id,
        inactive_sessions=s.inactive_sessions+InactiveSessionDto(s.session_id,s.task_id),snapshot_id=snapshot())
      "new-conversation" -> s.copy(session_id=UUID.randomUUID().toString(),short_term=emptyList(),
        inactive_sessions=s.inactive_sessions+InactiveSessionDto(s.session_id,s.task_id),snapshot_id=snapshot())
      else -> s.copy(long_term=emptyMap(),snapshot_id=snapshot())
    }
    return response()
  }
  private fun observation(stage: String?,stored: MemoryStateDto,reply: String,commit: Boolean=false): MemoryObservation {
    val check=MemoryCheck("available",true)
    val fields=listOf("project_code","release_marker","current_task","effective_architecture","last_error_title")
    val checks=fields.associateWith { check }
    return MemoryObservation(UUID.randomUUID().toString(),stored.snapshot_id,stored,response().preview!!,
      buildJsonObject { put("input","ORION-17 RC-42 Checkout MVI Сбой-47"); put("query","same verification question") },
      "completed",reply=reply,stage=stage,input_checks=if(stage==null) emptyMap() else checks,
      output_checks=if(stage==null) emptyMap() else checks+("effective_architecture" to MemoryCheck("mismatch",false)),
      parsed=if(stage==null) null else buildJsonObject { put("next_step","Уточнить загрузку."); put("effective_architecture","MVVM") },
      committed=commit)
  }
  override suspend fun send(body: MemorySendRequest): MemoryOperation {
    sends++; val before=state!!; serial++
    state=before.copy(short_term=listOf(MemoryMessageDto("user",body.message,0),MemoryMessageDto("assistant","Принято",1)),snapshot_id=snapshot())
    return MemoryOperation(response(),observation(null,before,"Принято",true))
  }
  override suspend fun verify(stage: String,body: MemorySnapshotRequest): MemoryOperation {
    probes++
    var observed=observation(stage,state!!,"Observed model response")
    probeError?.let { error -> observed=observed.copy(status="error",error=error,reply=null,parsed=null,
      output_checks=observed.output_checks.mapValues { MemoryCheck("unavailable",null) }) }
    return MemoryOperation(response(),observed)
  }
}
