package com.example.responsecontrollab.ui.mcp

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.McpLabOperationDto
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar

@Composable
fun McpLabScreen(viewModel: McpLabViewModel, onBack: () -> Unit) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  McpLabContent(state, viewModel::editPrompt, viewModel::selectMode, viewModel::send, onBack)
}

@Composable
fun McpLabContent(state: McpLabUiState, editPrompt: (String) -> Unit, selectMode: (String) -> Unit,
                  send: () -> Unit, onBack: () -> Unit) {
  var inspector by rememberSaveable(state.result?.operation_id, state.isLoading) { mutableStateOf(false) }
  Scaffold(topBar = { LearningDayTopBar(LearningDay.FIRST_MCP_TOOL, onBack) },
    contentWindowInsets = WindowInsets.safeDrawing) { padding ->
    Box(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentAlignment = Alignment.TopCenter) {
      Column(Modifier.widthIn(max = 760.dp).fillMaxSize().verticalScroll(rememberScrollState())
        .imePadding().padding(16.dp).testTag("mcp_lab"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Версии зависимости из Google Maven", style = MaterialTheme.typography.titleLarge)
        OutlinedTextField(state.prompt, editPrompt, label = { Text("Запрос") },
          modifier = Modifier.fillMaxWidth().testTag("mcp_prompt"), minLines = 3)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
          FilterChip(state.mode == "forced", { selectMode("forced") }, label = { Text("Проверить вызов") })
          FilterChip(state.mode == "auto", { selectMode("auto") }, label = { Text("Автовыбор") })
        }
        Text(if (state.mode == "forced") "Инструмент выбран заранее; координаты определяет модель."
          else "Модель решает, обращаться ли к инструменту.", style = MaterialTheme.typography.bodySmall)
        Button(send, enabled = !state.isLoading && state.prompt.isNotBlank(), modifier = Modifier.testTag("mcp_send")) {
          Text("Отправить")
        }
        if (state.isLoading) {
          LinearProgressIndicator(Modifier.fillMaxWidth())
          Text("Ожидаем результат текущей попытки…")
        }
        state.submittedPrompt?.let {
          Text("Отправлено · ${if (state.submittedMode == "forced") "Проверить вызов" else "Автовыбор"}",
            style = MaterialTheme.typography.labelLarge)
          Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("mcp_submitted"))
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.result?.let { result ->
          Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
              Text(outcomeLabel(result.outcome), modifier = Modifier.testTag("mcp_outcome"), style = MaterialTheme.typography.titleMedium)
              Text("Наблюдаемых вызовов: ${result.calls.size}")
              result.error_message?.let { Text(it) }
              result.calls.forEach { call ->
                call.parsed_result?.let { Text("${it.group_id}:${it.artifact_id} · ${outcomeLabel(it.status)} · версий: ${it.versions.size}") }
              }
            }
          }
          Text("Ответ модели", style = MaterialTheme.typography.titleMedium)
          SelectionContainer { Text(result.final_text ?: "Ответ модели отсутствует.") }
          TextButton({ inspector = !inspector }, modifier = Modifier.testTag("mcp_inspector_toggle")) {
            Text(if (inspector) "Скрыть Inspector" else "Открыть Inspector")
          }
          if (inspector) Inspector(result)
        }
      }
    }
  }
}

@Composable
private fun Inspector(result: McpLabOperationDto) {
  SelectionContainer {
    Column(Modifier.fillMaxWidth().testTag("mcp_inspector"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
      Text("MCP server: ${result.server_label}\n${result.server_url ?: "URL не настроен"}")
      Text("Operation id: ${result.operation_id}\nResponse id: ${result.response_id ?: "не предоставлен"}")
      Text("Responses status: ${result.provider_status ?: "не предоставлен"}\nInvocation: ${result.invocation}")
      Text("Imported tools: ${result.imported_tools.size}")
      result.imported_tools.forEach { Text(it.toString(), style = MaterialTheme.typography.bodySmall) }
      if (result.calls.isEmpty()) Text("MCP calls отсутствуют в полученном результате.")
      result.calls.forEachIndexed { index, call ->
        HorizontalDivider()
        Text("Вызов ${index + 1} · ${call.name ?: "имя не предоставлено"}", style = MaterialTheme.typography.titleSmall)
        Text("Server label: ${call.server_label ?: "не предоставлен"}\nCall id: ${call.id ?: "не предоставлен"}")
        Text("Arguments: ${call.arguments ?: "не предоставлены"}")
        Text("Call status: ${call.status ?: "не предоставлен"}\nOutcome: ${call.outcome}")
        call.parsed_result?.let { evidence ->
          Text("Lookup id: ${evidence.lookup_id}\nChecked at: ${evidence.checked_at}\nSource: ${evidence.source_url}")
          Text("Версии в порядке источника (${evidence.versions.size}):\n${evidence.versions.joinToString(", ")}")
        }
        call.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
        call.evidence_error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        call.output?.let { Text("Raw output: $it", style = MaterialTheme.typography.bodySmall) }
      }
      // Includes discovery failures / unexpected approvals even when there are no calls.
      result.mcp_items.forEach { Text("MCP item: $it", style = MaterialTheme.typography.bodySmall) }
    }
  }
}

private fun outcomeLabel(value: String): String = when (value) {
  "completed" -> "Операция завершена"
  "found" -> "Версии получены"
  "group_not_found" -> "Группа не найдена в Google Maven"
  "artifact_not_found" -> "Артефакт не найден в группе"
  "no_versions" -> "У артефакта нет версий"
  "not_called" -> "Инструмент не вызван"
  "configuration_error" -> "MCP server не настроен"
  "provider_error" -> "Ошибка Responses API"
  "mcp_error" -> "Ошибка MCP connection/discovery"
  "tool_error" -> "Ошибка выполнения инструмента"
  "unclassified_error" -> "Вызов вернул ошибку без подтверждённой категории"
  "invalid_tool_result" -> "Результат инструмента не прошёл проверку"
  "incomplete" -> "Ответ модели не завершён"
  "refused" -> "Модель отказалась отвечать"
  "model_response_missing" -> "Вызов наблюдался, ответ модели отсутствует"
  "failed" -> "Responses operation завершилась ошибкой"
  else -> value
}
