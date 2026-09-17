package com.example.responsecontrollab

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.invariants.InvariantsScreen
import com.example.responsecontrollab.ui.invariants.InvariantsViewModel
import org.junit.Rule
import org.junit.Test

class InvariantsNarrowUiTest {
  @get:Rule val rule=createAndroidComposeRule<ComponentActivity>()
  @Test fun actionsAndReceiptRemainReachableAt320By480() {
    val repo=InvariantsFixture(); val vm=InvariantsViewModel(repo)
    rule.setContent { ResponseControlLabTheme { Box(Modifier.width(320.dp).height(480.dp)) { InvariantsScreen(vm,{}) } } }
    rule.waitUntil { vm.uiState.value.loaded }
    rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasTestTag("invariants_conflicting-stack"))
    rule.onNodeWithTag("invariants_conflicting-stack").assertIsDisplayed().performClick()
    rule.waitUntil { vm.uiState.value.latest!=null }
    rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasTestTag("invariants_reply"))
    rule.onNodeWithTag("invariants_reply").assertIsDisplayed()
    rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasTestTag("invariants_page_inspector"))
    rule.onNodeWithTag("invariants_page_inspector").performClick()
    rule.onNodeWithTag("invariants_scroll").performScrollToNode(hasTestTag("invariants_historical"))
    rule.onNodeWithTag("invariants_historical").assertIsDisplayed()
  }
}
