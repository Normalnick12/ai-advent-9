package com.example.responsecontrollab.ui.main

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.GenerateResponseDto
import com.example.responsecontrollab.data.GenerationControlsDto
import com.example.responsecontrollab.R
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val prettyJson = Json { prettyPrint = true }

@Composable
fun ResponseControlScreen(viewModel: ResponseControlViewModel, onBack: () -> Unit) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  Scaffold(
    modifier = Modifier.fillMaxSize(),
    contentWindowInsets = WindowInsets.safeDrawing,
    topBar = { LearningDayTopBar(LearningDay.RESPONSE_CONTROL, onBack) },
  ) { innerPadding ->
    Column(
      modifier =
        Modifier.fillMaxSize()
          .padding(innerPadding)
          .consumeWindowInsets(innerPadding)
          .testTag("lesson_02")
          .verticalScroll(rememberScrollState())
          .padding(horizontal = 16.dp, vertical = 8.dp),
      verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
      Text(
        stringResource(R.string.response_intro),
        style = MaterialTheme.typography.bodyLarge,
      )
      OutlinedTextField(
        value = state.prompt,
        onValueChange = viewModel::setPrompt,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(stringResource(R.string.prompt_label)) },
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
        Text(stringResource(if (state.isLoading) R.string.generating else R.string.generate))
      }

      if (state.isLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
      state.errorMessage?.let { ErrorCard(it) }
      state.freeResult?.let { ResultCard(stringResource(R.string.result_free), it) }
      state.controlledResult?.let { ResultCard(stringResource(R.string.result_controlled), it) }
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
    Text(stringResource(R.string.response_mode), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    Row(
      modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
      horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      ResponseMode.entries.forEach { mode ->
        FilterChip(
          selected = selected == mode,
          onClick = { onSelected(mode) },
          label = {
            Text(stringResource(
              when (mode) {
                ResponseMode.FREE -> R.string.mode_free
                ResponseMode.CONTROLLED -> R.string.mode_controlled
                ResponseMode.COMPARE -> R.string.mode_compare
              }
            ))
          },
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
      Text(stringResource(R.string.response_controls), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
      ControlSwitch(stringResource(R.string.structured_json), state.structuredOutput, viewModel::setStructuredOutput)
      ControlSwitch(stringResource(R.string.length_limit), state.lengthLimit, viewModel::setLengthLimit)
      OutlinedTextField(
        value = state.maxOutputTokens,
        onValueChange = viewModel::setMaxOutputTokens,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(stringResource(R.string.max_output_tokens_label)) },
        enabled = state.lengthLimit && !state.isLoading,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        singleLine = true,
      )
      ControlSwitch(stringResource(R.string.finish_instruction), state.finishInstruction, viewModel::setFinishInstruction)
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
      Text(stringResource(R.string.result_status, result.status), style = MaterialTheme.typography.labelLarge)
      Text(stringResource(R.string.request_id, result.request_id ?: stringResource(R.string.no_data)))
      Text(stringResource(R.string.output_tokens, result.output_tokens?.toString() ?: stringResource(R.string.no_data)))
      Text(stringResource(R.string.result_controls, result.controls.summary()))
      result.incomplete_reason?.let {
        Text(
          stringResource(R.string.answer_incomplete, it),
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

@Composable
private fun GenerationControlsDto.summary(): String =
  stringResource(
    R.string.controls_summary,
    stringResource(if (structured_output) R.string.yes else R.string.no),
    max_output_tokens?.toString() ?: stringResource(R.string.no_limit),
    stringResource(if (finish_instruction) R.string.yes else R.string.no),
  )
