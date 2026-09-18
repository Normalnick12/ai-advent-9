package com.example.responsecontrollab

import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.PlaygroundCurrent
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.playground.PlaygroundScreen
import com.example.responsecontrollab.ui.playground.PlaygroundViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PlaygroundUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=PlaygroundFixture()
  private lateinit var vm: PlaygroundViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,PlaygroundViewModel.factory(repo))["day15",PlaygroundViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_15"))
    rule.onNodeWithTag("day_15").performClick()
    rule.waitUntil { vm.uiState.value.loaded }
  }
  private fun show(tag: String) {
    rule.onNodeWithTag("playground_scroll").performScrollToNode(hasTestTag(tag))
  }
  private fun click(tag: String) {
    show(tag); rule.onNodeWithTag(tag).performClick()
    rule.waitUntil { !vm.uiState.value.busy }
  }
  private fun event(name: String) = click("playground_event_$name")
  @Test fun forbiddenRecoveryPauseAndForwardDoneUseDistinctResults() {
    event("REQUIREMENTS_READY")
    click("playground_section_Проверка запрещённого перехода"); click("playground_forbidden")
    assertEquals("rejected",vm.uiState.value.receipts[vm.uiState.value.latest]!!.outcome)
    assertTrue(repo.value.memory!!.short_term.isEmpty())
    event("REQUIREMENTS_REVISION_REQUIRED")
    assertEquals("PLANNING_REQUIREMENTS",repo.value.task_state!!.state_id)
    event("REQUIREMENTS_READY"); event("PLAN_APPROVED")
    click("playground_forbidden")
    assertEquals("rejected",vm.uiState.value.receipts[vm.uiState.value.latest]!!.outcome)
    event("PAUSE"); show("playground_send"); rule.onNodeWithTag("playground_send").assertExists()
    event("RESUME"); event("IMPLEMENTATION_READY")
    event("VALIDATION_FAILED")
    show("playground_result")
    rule.onNodeWithText("Recovery applied — возврат применён").assertIsDisplayed()
    rule.onNodeWithTag("playground_error").assertDoesNotExist()
    click("playground_inspect"); show("playground_summary")
    rule.onNodeWithText("Outcome: Recovery applied — возврат применён").assertExists()
    click("playground_open_raw"); rule.onNodeWithTag("playground_raw").assertTextContains("VALIDATION_FAILED",substring=true)
    Espresso.pressBack(); assertEquals("inspector",vm.uiState.value.page)
    Espresso.pressBack(); event("IMPLEMENTATION_READY"); event("VALIDATION_CONFIRMED")
    show("playground_stage"); rule.onNodeWithTag("playground_stage").assertTextEquals("Задача завершена")
    rule.onNodeWithTag("playground_query").assertDoesNotExist()
    assertEquals(0,repo.sends)
  }
  @Test fun reviewedSetupCancelAlternateValuesAndPartialCompletion() {
    rule.runOnIdle { repo.value=PlaygroundCurrent(); vm.refresh() }
    rule.waitUntil { !vm.uiState.value.busy }
    click("playground_new_task")
    click("playground_setup_required_architecture_MVVM")
    click("playground_cancel"); assertEquals(0,repo.creates)
    click("playground_new_task"); click("playground_setup_profile_mentor")
    click("playground_setup_required_architecture_MVVM")
    click("playground_setup_required_ui_toolkit_Views"); click("playground_setup_required_async_model_RxJava")
    click("playground_setup_payment"); click("playground_review")
    assertEquals(0,repo.creates)
    rule.runOnIdle { repo.partial=true }
    click("playground_confirm")
    rule.runOnIdle { vm.back() }
    click("playground_complete")
    assertEquals("MVVM",repo.lastCreate!!.configuration.policy.required_architecture)
    assertFalse(repo.lastCreate!!.configuration.policy.payment_confirmation_required)
    assertEquals(1,repo.creates); assertEquals(1,repo.completes)
  }
  @Test fun rotationInFlightDraftInspectorAndBackDoNotReplay() {
    show("playground_query"); rule.onNodeWithTag("playground_query").performTextInput("Обсудим retry")
    Espresso.closeSoftKeyboard()
    rule.activityRule.scenario.recreate(); show("playground_query")
    rule.onNodeWithTag("playground_query").assertTextContains("Обсудим retry")
    rule.runOnIdle { repo.gate=CompletableDeferred() }
    show("playground_send"); rule.onNodeWithTag("playground_send").performClick()
    rule.waitUntil { repo.sends==1 }
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { repo.gate!!.complete(Unit) }
    rule.waitUntil { !vm.uiState.value.busy }
    click("playground_pair_1"); click("playground_section_Memory")
    rule.activityRule.scenario.recreate()
    assertTrue("Memory" in vm.uiState.value.expanded)
    click("playground_open_raw"); Espresso.pressBack(); Espresso.pressBack(); Espresso.pressBack()
    open(); assertEquals(1,repo.sends); assertEquals(0,repo.events); assertEquals(1,repo.reads)
  }
  @Test fun refusalTechnicalFailureAndUnavailableHistoryAreSeparate() {
    rule.runOnIdle { repo.violate=true; vm.draft("query"); vm.send() }
    rule.waitUntil { !vm.uiState.value.busy }
    show("playground_pair_1")
    rule.onNodeWithText("Отказ по ограничениям задачи.").assertIsDisplayed()
    rule.onNodeWithText("UNTRUSTED REJECTED CODE").assertDoesNotExist()
    rule.runOnIdle { repo.technical=true; vm.draft("failure"); vm.send() }
    rule.waitUntil { !vm.uiState.value.busy }
    assertEquals(2,repo.value.memory!!.short_term.size)
    assertEquals("failure",vm.uiState.value.draft)
    show("playground_error"); rule.onNodeWithTag("playground_error").assertTextContains("Техническая ошибка",substring=true)
    rule.runOnIdle { vm.inspect(null) }
    show("playground_unavailable"); rule.onNodeWithTag("playground_unavailable").assertIsDisplayed()
  }
  @Test fun narrowLargeFontAndImeKeepControlsUsable() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.setContent {
        ResponseControlLabTheme {
          val d=LocalDensity.current
          CompositionLocalProvider(LocalDensity provides Density(d.density,1.5f)) {
            Box(Modifier.width(320.dp)) { PlaygroundScreen(vm) {} }
          }
        }
      }
    }
    show("playground_query"); rule.onNodeWithTag("playground_query").performTextInput("Уточнение")
    show("playground_send"); rule.onNodeWithTag("playground_send").assertIsDisplayed()
    Espresso.closeSoftKeyboard()
    click("playground_send")
    assertEquals(1,repo.sends)
    event("REQUIREMENTS_READY"); event("REQUIREMENTS_REVISION_REQUIRED")
    assertEquals("recovery_applied",vm.uiState.value.receipts[vm.uiState.value.latest]!!.outcome)
  }
}
