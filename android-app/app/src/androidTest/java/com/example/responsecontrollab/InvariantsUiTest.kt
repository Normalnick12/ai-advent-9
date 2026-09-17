package com.example.responsecontrollab

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.ui.invariants.InvariantsViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class InvariantsUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=InvariantsFixture()
  private lateinit var vm: InvariantsViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,InvariantsViewModel.factory(repo))["day14",InvariantsViewModel::class.java]
    }
    rule.activityRule.scenario.recreate(); open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_14"))
    rule.onNodeWithTag("day_14").performClick(); rule.waitUntil { vm.uiState.value.loaded }
  }
  private fun show(tag: String) { rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasTestTag(tag)) }
  private fun click(tag: String) { show(tag); rule.onNodeWithTag(tag).performClick(); rule.waitForIdle() }
  @Test fun zeroCallRefusalAndHistoricalReceiptSurviveConversationAndBack() {
    click("invariants_conflicting-stack"); rule.waitUntil { !vm.uiState.value.busy }
    show("invariants_outcome"); rule.onNodeWithTag("invariants_outcome").assertTextContains("not_dispatched",substring=true)
    assertEquals(0,repo.value.generation_calls); assertEquals(2,repo.value.memory!!.short_term.size)
    val o=vm.uiState.value.latest!!
    click("invariants_new_conversation"); click("invariants_page_inspector"); show("invariants_historical")
    rule.onNodeWithTag("invariants_historical").assertTextContains(o.memory.session_id,substring=true)
    Espresso.pressBack(); assertEquals("main",vm.uiState.value.page)
    Espresso.pressBack(); open(); assertEquals(o,vm.uiState.value.latest); assertEquals(1,repo.proposals)
  }
  @Test fun rotationKeepsScrollAndInFlightRequestWithoutReplay() {
    show("invariants_conflicting-stack")
    val scroll=rule.onNodeWithTag("invariants_scroll").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
    rule.activityRule.scenario.recreate(); rule.waitForIdle()
    assertEquals(scroll,rule.onNodeWithTag("invariants_scroll").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value(),1f)
    rule.runOnIdle { repo.gate=CompletableDeferred() }
    click("invariants_compatible-retry"); rule.waitUntil { repo.proposals==1 }
    rule.activityRule.scenario.recreate(); rule.runOnIdle { assertTrue(vm.uiState.value.busy); repo.gate!!.complete(Unit) }
    rule.waitUntil { !vm.uiState.value.busy }; assertEquals(1,repo.proposals); assertEquals("accepted",vm.uiState.value.latest!!.turn.decision)
  }
  @Test fun incompleteAndPausedStateDisableActionsAndShowSetupValues() {
    rule.runOnIdle { repo.value=repo.value.copy(ready=false,can_propose=false,policy=null,readiness=repo.value.readiness.copy(policy_ready=false)); vm.refresh() }
    rule.waitUntil { !vm.uiState.value.busy }; show("invariants_compatible-retry")
    rule.onNodeWithTag("invariants_compatible-retry").assertIsNotEnabled()
    click("invariants_page_setup"); click("invariants_setup"); assertEquals(1,repo.setups)
    click("invariants_event_PAUSE"); Espresso.pressBack(); show("invariants_conflicting-stack")
    rule.onNodeWithTag("invariants_conflicting-stack").assertIsNotEnabled(); assertEquals(0,repo.proposals)
  }
  @Test fun rawRejectedCandidateOnlyInDiagnosticInspectorAndTechnicalErrorSeparate() {
    rule.runOnIdle { repo.violate=true }; click("invariants_compatible-retry")
    show("invariants_reply"); rule.onNodeWithTag("invariants_reply").assertTextContains("Безопасный отказ",substring=true)
    rule.onNodeWithText("RAW REJECTED MVVM").assertDoesNotExist()
    click("invariants_page_inspector")
    rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasText("Raw candidate — отклонён, не сохранён в conversation (диагностика)"))
    rule.onNodeWithText("Raw candidate — отклонён, не сохранён в conversation (диагностика)").assertIsDisplayed()
    Espresso.pressBack(); rule.runOnIdle { repo.technical=true }; click("invariants_compatible-retry")
    show("invariants_error"); rule.onNodeWithTag("invariants_error").assertTextContains("Техническая ошибка",substring=true)
    show("invariants_outcome"); rule.onNodeWithTag("invariants_outcome").assertTextContains("not_attempted",substring=true)
    rule.onNodeWithTag("invariants_reply").assertDoesNotExist(); assertEquals(2,repo.value.memory!!.short_term.size)
  }
}
