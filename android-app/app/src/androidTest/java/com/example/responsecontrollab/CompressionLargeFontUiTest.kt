package com.example.responsecontrollab

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.ui.compression.CompressionLabScreen
import com.example.responsecontrollab.ui.compression.CompressionLabViewModel
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CompressionLargeFontUiTest {
  @get:Rule val rule = createComposeRule()
  @OptIn(ExperimentalTestApi::class)
  @Test fun largeFontWithKeyboardKeepsComposerActionsAccessible() {
    val repo = CompressionUiRepository()
    val vm = CompressionLabViewModel(repo, tokenUiStore())
    rule.setContent {
      DeviceConfigurationOverride(DeviceConfigurationOverride.FontScale(1.5f)) {
        MaterialTheme { CompressionLabScreen(vm, {}) }
      }
    }
    rule.waitUntil { vm.uiState.value.ready }
    rule.onNodeWithTag("compression_input").performClick().performTextInput("Большой шрифт")
    rule.onNodeWithTag("compression_send").assertIsDisplayed()
    rule.onNodeWithTag("compression_reset").assertIsDisplayed()
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("compression_chat").performScrollToNode(hasTestTag("compression_details"))
    rule.onNodeWithTag("compression_details").performClick()
    rule.onNodeWithTag("compression_stats").performScrollToNode(hasTestTag("compression_question"))
    rule.onNodeWithTag("compression_question").assertIsDisplayed()
    rule.runOnIdle { assertEquals(0, repo.sends) }
  }
}
