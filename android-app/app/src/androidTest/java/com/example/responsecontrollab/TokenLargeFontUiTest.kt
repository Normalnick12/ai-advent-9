package com.example.responsecontrollab

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.ui.token.TokenLabScreen
import com.example.responsecontrollab.ui.token.TokenLabViewModel
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TokenLargeFontUiTest {
  @get:Rule val rule = createComposeRule()
  @OptIn(ExperimentalTestApi::class)
  @Test fun largeFontWithImeKeepsActionsAndDiagnosticsAccessible() {
    val repo = TokenUiRepository()
    val vm = TokenLabViewModel(repo, tokenUiStore())
    rule.setContent {
      DeviceConfigurationOverride(DeviceConfigurationOverride.FontScale(1.5f)) {
        MaterialTheme { TokenLabScreen(vm, {}) }
      }
    }
    rule.waitUntil { vm.uiState.value.initialized && !vm.uiState.value.busy }
    rule.onNodeWithTag("token_input").performClick().performTextInput("Проверка большого шрифта")
    rule.onNodeWithTag("token_send").assertIsDisplayed()
    rule.onNodeWithTag("token_reset").assertIsDisplayed()
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("token_content").performScrollToNode(hasTestTag("token_prepare"))
    rule.onNodeWithTag("token_prepare").performClick()
    rule.waitUntil { vm.uiState.value.preparation != null }
    rule.onNodeWithTag("token_content").performScrollToNode(hasTestTag("token_execute"))
    rule.onNodeWithTag("token_execute").assertIsDisplayed()
    rule.runOnIdle { assertEquals(0, repo.executes); assertEquals(0, repo.sends) }
  }
}
