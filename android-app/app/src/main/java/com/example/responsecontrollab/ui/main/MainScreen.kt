package com.example.responsecontrollab.ui.main

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.GenerateResponseDto
import com.example.responsecontrollab.data.GenerationControlsDto
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val prettyJson = Json { prettyPrint = true }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResponseControlScreen(viewModel: ResponseControlViewModel) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  Scaffold(
    modifier = Modifier.fillMaxSize(),
    topBar = { TopAppBar(title = { Text("Response Control Lab") }) },
  ) { innerPadding ->
    Column(
      modifier =
        Modifier.fillMaxSize()
          .padding(innerPadding)
          .safeDrawingPadding()
          .verticalScroll(rememberScrollState())
          .padding(horizontal = 16.dp, vertical = 8.dp),
      verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
      Text(
        "Один prompt — разные уровни контроля ответа.",
        style = MaterialTheme.typography.bodyLarge,
      )
      OutlinedTextField(
        value = state.prompt,
        onValueChange = viewModel::setPrompt,
        modifier = Modifier.fillMaxWidth(),
        label = { Text("Prompt") },
        minLines = 2,
        enabled = !state.isLoading,
      )
      ModeSelector(state.mode, viewModel::setMode, state.isLoading)

      if (state.mode != ResponseMode.FREE) ControlsCard(state, viewModel)

      Button(
        onClick = viewModel::generate,
        modifier = Modifier.fillMaxWidth(),
        enabled = !state.isLoading && state.prompt.isNotBlank(),
      ) {
        Text(if (state.isLoading) "Generating…" else "Generate")
      }

      if (state.isLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
      state.errorMessage?.let { ErrorCard(it) }
      state.freeResult?.let { ResultCard("FREE", it) }
      state.controlledResult?.let { ResultCard("CONTROLLED", it) }
      Spacer(Modifier.height(12.dp))
    }
  }
}

@Composable
private fun ModeSelector(
  selected: ResponseMode,
  onSelected: (ResponseMode) -> Unit,
  disabled: Boolean,
) {
  Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Text("Режим", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    Row(
      modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
      horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      ResponseMode.entries.forEach { mode ->
        FilterChip(
          selected = selected == mode,
          onClick = { onSelected(mode) },
          label = { Text(mode.name) },
          enabled = !disabled,
        )
      }
    }
  }
}

@Composable
private fun ControlsCard(state: ResponseControlUiState, viewModel: ResponseControlViewModel) {
  Card(Modifier.fillMaxWidth()) {
    Column(
      modifier = Modifier.padding(12.dp),
      verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      Text("Controls", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
      ControlSwitch("Structured JSON", state.structuredOutput, viewModel::setStructuredOutput)
      ControlSwitch("Length limit", state.lengthLimit, viewModel::setLengthLimit)
      OutlinedTextField(
        value = state.maxOutputTokens,
        onValueChange = viewModel::setMaxOutputTokens,
        modifier = Modifier.fillMaxWidth(),
        label = { Text("max_output_tokens") },
        enabled = state.lengthLimit && !state.isLoading,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        singleLine = true,
      )
      ControlSwitch("Finish instruction", state.finishInstruction, viewModel::setFinishInstruction)
    }
  }
}

@Composable
private fun ControlSwitch(label: String, checked: Boolean, onChecked: (Boolean) -> Unit) {
  Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
    Text(label, modifier = Modifier.weight(1f))
    Switch(checked = checked, onCheckedChange = onChecked)
  }
}

@Composable
private fun ErrorCard(message: String) {
  Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
    Text(
      text = message,
      modifier = Modifier.fillMaxWidth().padding(16.dp),
      color = MaterialTheme.colorScheme.onErrorContainer,
    )
  }
}

@Composable
private fun ResultCard(title: String, result: GenerateResponseDto) {
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(
      modifier = Modifier.padding(16.dp),
      verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
      Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
      HorizontalDivider()
      SelectionContainer {
        val body =
          result.recipe?.let { prettyJson.encodeToString(it) }
            ?: result.content
            ?: "Ответ не содержит отображаемого содержимого."
        Text(
          text = body,
          style = MaterialTheme.typography.bodyMedium,
          fontFamily = if (result.recipe != null) FontFamily.Monospace else FontFamily.Default,
        )
      }
      HorizontalDivider()
      Text("status: ${result.status}", style = MaterialTheme.typography.labelLarge)
      Text("request id: ${result.request_id ?: "n/a"}")
      Text("output tokens: ${result.output_tokens ?: "n/a"}")
      Text("controls: ${result.controls.summary()}")
      result.incomplete_reason?.let {
        Text(
          "Ответ incomplete: $it",
          color = MaterialTheme.colorScheme.error,
          fontWeight = FontWeight.SemiBold,
        )
      }
      result.error?.let {
        Text("${it.code}: ${it.message}", color = MaterialTheme.colorScheme.error)
      }
    }
  }
}

private fun GenerationControlsDto.summary(): String =
  listOf(
      "structured=$structured_output",
      max_output_tokens?.let { "max=$it" } ?: "max=none",
      "finish=$finish_instruction",
    )
    .joinToString()
