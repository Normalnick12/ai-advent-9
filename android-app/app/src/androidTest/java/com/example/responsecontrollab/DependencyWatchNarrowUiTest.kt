package com.example.responsecontrollab

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.espresso.Espresso
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.watch.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class DependencyWatchNarrowUiTest {
  @get:Rule val rule = createComposeRule()
  @OptIn(ExperimentalTestApi::class)
  @Test fun narrowLargeFontImeAndFailedAttemptRemainReadable() {
    var calls = 0
    val vm = DependencyWatchViewModel(DependencyWatchRepository { calls++; error("offline") }, object : WatchReceiptStore {
      override fun load() = WatchReceipts()
      override fun save(value: WatchReceipts) {}
    })
    rule.setContent {
      DeviceConfigurationOverride(DeviceConfigurationOverride.ForcedSize(androidx.compose.ui.unit.DpSize(320.dp, 640.dp))) {
        DeviceConfigurationOverride(DeviceConfigurationOverride.FontScale(1.5f)) {
          MaterialTheme { DependencyWatchScreen(vm, {}) }
        }
      }
    }
    rule.onNodeWithTag("watch_prompt").performScrollTo().performClick().performTextReplacement("Создай watch")
    rule.onNodeWithTag("watch_send").performScrollTo().assertIsDisplayed()
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("watch_send").performScrollTo().performClick()
    rule.waitUntil { vm.uiState.value.error != null }
    rule.onNodeWithTag("watch_error").performScrollTo().assertIsDisplayed()
    rule.onNodeWithText("Сохранённая сводка").assertDoesNotExist()
    rule.onNodeWithTag("watch_inspector").performScrollTo().performClick()
    rule.onNodeWithText("Submitted prompt: Создай watch", substring = true).performScrollTo().assertIsDisplayed()
    rule.runOnIdle { assertEquals(1, calls) }
  }
}
