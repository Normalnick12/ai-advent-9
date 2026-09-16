package com.example.responsecontrollab

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.TaskReadiness
import com.example.responsecontrollab.ui.taskstate.TaskStateViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TaskStateUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=TaskFixture()
  private lateinit var vm: TaskStateViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,TaskStateViewModel.factory(repo))["day13",TaskStateViewModel::class.java]
    }
    rule.activityRule.scenario.recreate(); open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_13"))
    rule.onNodeWithTag("day_13").performClick(); rule.waitUntil { vm.uiState.value.loaded }
  }
  private fun tag(tag: String) {
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag(tag)); rule.onNodeWithTag(tag).performClick(); rule.waitForIdle()
  }
  private fun send(query: String) {
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag("task_message"))
    rule.onNodeWithTag("task_message").performTextInput(query); Espresso.closeSoftKeyboard()
    tag("task_send"); rule.waitUntil { !vm.uiState.value.busy }
  }
  @Test fun twoConversationsPausedComposerAndHistoricalInspector() {
    send("Execution"); assertEquals(2,repo.value.memory!!.short_term.size)
    tag("task_event_PAUSE"); tag("task_new_conversation")
    rule.onNodeWithTag("task_session").assertTextContains("0 turns",substring=true)
    rule.onNodeWithTag("task_event_IMPLEMENTATION_READY").assertDoesNotExist()
    send("Где мы остановились?"); assertEquals("PAUSED",repo.value.task_state!!.status)
    val status=vm.uiState.value.latest!!
    tag("task_new_conversation"); rule.onNodeWithTag("task_session").assertTextContains("0 turns",substring=true)
    tag("task_event_RESUME"); tag("task_page_inspector")
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag("task_historical"))
    rule.onNodeWithTag("task_historical").assertTextContains(status.memory.session_id,substring=true)
    assertEquals("PAUSED",vm.uiState.value.latest!!.selected_state.status)
    Espresso.pressBack(); send("Продолжим")
    assertEquals(3,repo.sends); assertEquals(2,repo.events); assertEquals(2,repo.lifecycles)
    assertEquals("EXECUTION_IMPLEMENT",repo.value.task_state!!.state_id)
  }
  @Test fun rotationPreservesDraftScrollAndInFlightResultWithoutReplay() {
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag("task_message"))
    // Test saved scroll with a stable viewport; IME interaction is covered by send().
    rule.runOnIdle { vm.message("Draft") }
    val scroll=rule.onNodeWithTag("task_scroll").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
    rule.activityRule.scenario.recreate(); rule.waitForIdle()
    rule.onNodeWithTag("task_message").assertTextContains("Draft")
    assertEquals(scroll,rule.onNodeWithTag("task_scroll").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value(),1f)
    rule.runOnIdle { repo.gate=CompletableDeferred() }
    tag("task_send"); rule.waitUntil { repo.sends==1 }; rule.activityRule.scenario.recreate()
    rule.runOnIdle { assertTrue(vm.uiState.value.busy); repo.gate!!.complete(Unit) }
    rule.waitUntil { !vm.uiState.value.busy }; Espresso.pressBack(); open()
    assertEquals(1,repo.sends); assertNotNull(vm.uiState.value.latest)
  }
  @Test fun preDispatchRejectionIsVisibleWithoutFabricatedActualReceipt() {
    rule.runOnIdle {
      repo.eventFailure=retrofit2.HttpException(retrofit2.Response.error<Any>(409,
        okhttp3.ResponseBody.create(null,"{\"error\":\"stale_task_state\",\"dispatch\":\"not_dispatched\"}")))
    }
    tag("task_event_PAUSE"); rule.waitUntil { !vm.uiState.value.busy }
    assertEquals("ACTIVE",repo.value.task_state!!.status); assertEquals(1,repo.events)
    tag("task_page_inspector")
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasText("Последняя операция dispatch: not_dispatched"))
    rule.onNodeWithText("Последняя операция dispatch: not_dispatched").assertIsDisplayed()
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasText("Actual receipt unavailable — запрос ещё не записан."))
    rule.onNodeWithText("Actual receipt unavailable — запрос ещё не записан.").assertIsDisplayed()
    assertNull(vm.uiState.value.latest); assertEquals(0,repo.sends)
  }
  @Test fun doneAndPartialSetupNeverInventControlsOrReceipt() {
    rule.runOnIdle {
      repo.value=repo.value.copy(task_state=repo.value.task_state!!.copy(state_id="DONE",phase="done",step="complete",expected_action="none",is_terminal=true,allowed_events=emptyList()))
      vm.refresh()
    }
    rule.waitUntil { !vm.uiState.value.busy }
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag("task_state_card"))
    rule.onNodeWithTag("task_event_PAUSE").assertDoesNotExist(); rule.onNodeWithTag("task_event_RESUME").assertDoesNotExist()
    rule.runOnIdle { repo.value=repo.value.copy(task_state=null,readiness=TaskReadiness(true,true,false),ready=false); vm.refresh() }
    rule.waitUntil { !vm.uiState.value.busy }
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasTestTag("task_message"))
    rule.onNodeWithTag("task_message").assertIsNotEnabled()
    tag("task_page_setup")
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasText("Создать State текущей задачи"))
    rule.onNodeWithText("Создать State текущей задачи").assertIsEnabled()
    tag("task_page_inspector")
    rule.onNodeWithTag("task_scroll").performScrollToNode(hasText("Actual receipt unavailable — запрос ещё не записан."))
    rule.onNodeWithText("Actual receipt unavailable — запрос ещё не записан.").assertIsDisplayed()
    assertEquals(0,repo.sends); assertEquals(0,repo.writes)
  }
}
