package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.watch.*
import org.junit.Rule
import org.junit.Test

class DependencyWatchUiTest {
  @get:Rule val composeRule = createComposeRule()
  @Test fun inspectorShowsAllCallsAndNullSummaryRemainsUnknown() {
    val facts = WatchFactsDto("watch1", "androidx.core", "core-ktx", 3600, 3, "t", "next", "active", 0, 0)
    val result = WatchOperationDto("op", "P", "summary", response_id = "resp18", final_text = "model prose",
      outcome = "tool_error", invocation = "observed", calls = listOf(
        WatchCallDto(id = "failed-call", outcome = "tool_error", error = kotlinx.serialization.json.JsonPrimitive("failure")),
        WatchCallDto(id = "ok-call", outcome = "completed", summary = facts, output = "raw-evidence")))
    composeRule.setContent { ResponseControlLabTheme {
      DependencyWatchContent(DependencyWatchUiState(result = result), {}, {}, {}, {}, {})
    } }
    composeRule.onNodeWithText("Версий сейчас: нет данных", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("raw-evidence", substring = true).assertDoesNotExist()
    composeRule.onNodeWithTag("watch_inspector").performScrollTo().performClick()
    composeRule.onNodeWithText("Call id: failed-call", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Call id: ok-call", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Output: raw-evidence", substring = true).performScrollTo().assertIsDisplayed()
  }

  @Test fun emptyAndLoadingDisableSummaryOrDuplicateSend() {
    composeRule.setContent { ResponseControlLabTheme {
      DependencyWatchContent(DependencyWatchUiState(operation = "summary", isLoading = true), {}, {}, {}, {}, {})
    } }
    composeRule.onNodeWithText("Пока нет сохранённых watch IDs.").assertIsDisplayed()
    composeRule.onNodeWithTag("watch_send").performScrollTo().assertIsNotEnabled()
  }
}
