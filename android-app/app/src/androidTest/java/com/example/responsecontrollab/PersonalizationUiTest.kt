package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.ui.profile.*
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PersonalizationUiTest {
  @get:Rule val rule=createAndroidComposeRule<MainActivity>()
  private val repo=ProfileFixture()
  private lateinit var vm: PersonalizationViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,PersonalizationViewModel.factory(repo))[PersonalizationViewModel.KEY,PersonalizationViewModel::class.java]
    }
    rule.activityRule.scenario.recreate(); open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_12"))
    rule.onNodeWithTag("day_12").performClick(); rule.waitUntil { vm.uiState.value.initialized }
  }
  private fun click(text: String) {
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasText(text)); rule.onNodeWithText(text).performClick(); rule.waitForIdle()
  }
  @Test fun customTypedEditorFlagsDraftRotationDuplicateNamesAndSelect() {
    click("Новый профиль")
    rule.onNodeWithTag("profile_name").performTextInput("Custom")
    click("English"); click("Объясняющий"); click("Подробно"); click("Четыре раздела")
    click("Пропускать базовые Android/Kotlin понятия"); click("Объяснять новые специальные термины")
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { assertEquals("Custom",vm.uiState.value.draft.name); assertTrue(vm.uiState.value.draft.skipBasics && vm.uiState.value.draft.explainTerms) }
    click("Сохранить профиль")
    rule.runOnIdle { assertNull(repo.value.active()); assertEquals("en",repo.value.profiles.single().language) }
    click("Выбрать")
    rule.runOnIdle { assertEquals(repo.memory,repo.value.memory) }
    click("Изменить"); click("Вывод и список"); click("5"); click("Сохранить профиль")
    rule.runOnIdle { assertEquals(5,repo.value.active()!!.response_format.max_bullets) }
    click("Новый профиль"); rule.onNodeWithTag("profile_name").performTextInput("Custom"); click("Сохранить профиль")
    rule.runOnIdle { assertEquals(2,repo.value.profiles.count { it.name=="Custom" }); assertEquals(1,repo.selects) }
    Espresso.pressBack(); open()
    rule.runOnIdle { assertEquals(3,repo.saves); assertEquals(0,repo.sends) }
  }
  @Test fun actualInspectorFailedOutputHistoricalRevisionAndNoReplay() {
    rule.runOnIdle { repo.prepared(); repo.failedOutput=true; vm.refresh() }
    rule.waitUntil { !vm.uiState.value.busy }
    click("Probe A"); click("Inspector A")
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasTestTag("profile_actual_request"))
    rule.onNodeWithTag("profile_actual_request").assertTextContains("instructions for technical",substring=true)
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasText("Output adherence: unavailable · fake_failure"))
    rule.onNodeWithText("Output adherence: unavailable · fake_failure").assertIsDisplayed()
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasTestTag("profile_notes"))
    rule.onNodeWithTag("profile_notes").performTextInput("Human observation")
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { assertEquals(1,repo.probes); assertEquals("Human observation",vm.uiState.value.notes.values.single()) }
    Espresso.pressBack()
    rule.runOnIdle { vm.edit(repo.value.active()); vm.draft(vm.uiState.value.draft.copy(name="Renamed")); vm.save() }
    rule.waitUntil { !vm.uiState.value.busy }
    click("Inspector A")
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasTestTag("profile_snapshot_label"))
    rule.onNodeWithTag("profile_snapshot_label").assertTextEquals("Предыдущий снимок")
    rule.runOnIdle { assertEquals(0,vm.uiState.value.inspected!!.profile.revision); assertEquals(1,repo.value.active()!!.revision) }
    Espresso.pressBack(); Espresso.pressBack(); open()
    rule.runOnIdle { assertEquals(1,repo.probes); assertEquals(0,repo.sends) }
  }
  @Test fun explicitTemplatesSeedFreezeABOnlyChangeSelectedProfile() {
    click("Создать из A · Compact Engineer"); click("Сохранить профиль")
    click("Создать из B · Mentor"); click("Сохранить профиль")
    val a=repo.value.profiles[0]; val b=repo.value.profiles[1]
    fun profileClick(id: String,text: String) {
      rule.onNodeWithTag("profile_scroll").performScrollToNode(hasTestTag("profile_$id"))
      rule.onNode(hasText(text) and hasAnyAncestor(hasTestTag("profile_$id"))).performClick()
      rule.waitForIdle()
    }
    profileClick(a.profile_id,"Слот A"); profileClick(b.profile_id,"Слот B")
    rule.runOnIdle { assertNull(repo.value.active()); assertEquals(0,repo.sends) }
    profileClick(a.profile_id,"Выбрать")
    click("Отправить seed"); click("Seed прочитан: стиль достаточно нейтрален")
    click("LONG_TERM · project_code = ORION-17"); click("LONG_TERM · preferred_architecture = MVVM")
    click("WORKING · task = Checkout"); click("WORKING · current_architecture = MVI"); click("WORKING · release_marker = RC-42")
    click("Freeze")
    val frozen=repo.value.memory
    click("Probe A"); profileClick(b.profile_id,"Выбрать")
    rule.runOnIdle { assertEquals(frozen,repo.value.memory); assertEquals(1,repo.probes) }
    click("Probe B")
    rule.runOnIdle { assertEquals(frozen,repo.value.memory); assertEquals(2,repo.probes); assertEquals(1,repo.sends); assertEquals(setOf("A","B"),vm.uiState.value.results.keys) }
  }
  @Test fun inFlightSendRotationNavigationAndColdRecoveryDoNotReplay() {
    rule.runOnIdle { repo.prepared(); repo.gate=CompletableDeferred(); vm.refresh() }
    rule.waitUntil { !vm.uiState.value.busy }
    rule.onNodeWithTag("profile_scroll").performScrollToNode(hasTestTag("profile_message"))
    rule.onNodeWithTag("profile_message").performTextInput("Current task?")
    click("Отправить"); rule.waitUntil { repo.sends==1 }
    rule.activityRule.scenario.recreate(); Espresso.pressBack(); open()
    rule.runOnIdle { assertEquals(1,repo.sends); assertTrue(vm.uiState.value.busy); repo.gate!!.complete(Unit) }
    rule.waitUntil { !vm.uiState.value.busy }
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm=ViewModelProvider(activity,PersonalizationViewModel.factory(repo))[PersonalizationViewModel.KEY,PersonalizationViewModel::class.java]
    }
    rule.activityRule.scenario.recreate(); rule.waitUntil { vm.uiState.value.initialized }
    rule.runOnIdle { assertEquals(1,repo.sends); assertNull(vm.uiState.value.latest); assertTrue(vm.uiState.value.results.isEmpty()); assertEquals(repo.value,vm.uiState.value.current) }
  }
}
