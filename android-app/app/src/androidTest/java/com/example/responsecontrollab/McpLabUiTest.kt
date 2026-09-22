package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.mcp.*
import org.junit.Rule
import org.junit.Test

class McpLabUiTest {
  @get:Rule val composeRule = createComposeRule()

  @Test fun inspectorShowsEveryCallAndOptionalStatusWithoutMainScreenRawJson() {
    val result = McpLabOperationDto("operation", "P", "forced", server_url = "https://maven.example.org/mcp",
      response_id = "resp-17", final_text = "Получены версии", outcome = "unclassified_error", invocation = "observed",
      calls = listOf(
        McpCallEvidenceDto(id = "call-failed", name = "get_google_maven_versions", status = "failed", outcome = "unclassified_error"),
        McpCallEvidenceDto(id = "call-ok", name = "get_google_maven_versions", arguments = "actual-arguments",
          output = "raw-evidence", outcome = "found", parsed_result = MavenEvidenceDto("found", "androidx.core", "core-ktx",
            listOf("1", "2-alpha"), "https://source.example", "2026-09-22T10:00:00Z", "lookup-17"))))
    composeRule.setContent { ResponseControlLabTheme {
      McpLabContent(McpLabUiState(result = result), {}, {}, {}, {})
    } }
    composeRule.onNodeWithText("raw-evidence", substring = true).assertDoesNotExist()
    composeRule.onNodeWithTag("mcp_inspector_toggle").performScrollTo().performClick()
    composeRule.onNodeWithText("Response id: resp-17", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Call id: call-failed", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Call status: failed", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Arguments: actual-arguments").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Call status: не предоставлен", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Lookup id: lookup-17", substring = true).performScrollTo().assertIsDisplayed()
  }

  @Test fun autoNoCallShowsNoFabricatedCallOrLookup() {
    val result = McpLabOperationDto("operation", "P", "auto", outcome = "not_called", invocation = "not_observed")
    composeRule.setContent { ResponseControlLabTheme {
      McpLabContent(McpLabUiState(mode = "auto", result = result), {}, {}, {}, {})
    } }
    composeRule.onNodeWithText("Инструмент не вызван").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithTag("mcp_inspector_toggle").performScrollTo().performClick()
    composeRule.onNodeWithText("MCP calls отсутствуют в полученном результате.").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Call id:", substring = true).assertDoesNotExist()
    composeRule.onNodeWithText("Lookup id:", substring = true).assertDoesNotExist()
  }
}
