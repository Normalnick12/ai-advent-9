package com.example.responsecontrollab.ui.temperature

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.TemperatureExperimentConfigDto
import com.example.responsecontrollab.data.TemperatureLabBatchResponseDto
import com.example.responsecontrollab.data.TemperatureResultDto

@Composable
fun TemperatureLabScreen(viewModel: TemperatureLabViewModel) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  TemperatureLabContent(
    state = state,
    onPromptChange = viewModel::editPrompt,
    onRun = viewModel::runComparison,
    onRestoreBenchmark = viewModel::restoreBenchmark,
  )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TemperatureLabContent(
  state: TemperatureLabUiState,
  onPromptChange: (String) -> Unit,
  onRun: () -> Unit,
  onRestoreBenchmark: () -> Unit,
) {
  Scaffold(
    modifier = Modifier.fillMaxSize(),
    topBar = { TopAppBar(title = { Text("Лаборатория температуры") }) },
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
        "Один запрос выполняется при temperature 0, 0.7 и 1.2.",
        style = MaterialTheme.typography.bodyLarge,
      )
      OutlinedTextField(
        value = state.prompt,
        onValueChange = onPromptChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text("Запрос") },
        minLines = 5,
        maxLines = 8,
        enabled = !state.isLoading,
      )
      Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
      ) {
        Button(
          onClick = onRun,
          modifier = Modifier.weight(1f),
          enabled = !state.isLoading && state.prompt.isNotEmpty(),
        ) {
          Text("Запустить сравнение")
        }
        OutlinedButton(
          onClick = onRestoreBenchmark,
          modifier = Modifier.weight(1f),
          enabled = !state.isLoading,
        ) {
          Text("Вернуть benchmark")
        }
      }
      ExperimentParametersCard(state.latestBatch?.config)

      if (state.isLoading) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Три temperature-запроса выполняются параллельно…")
      }
      state.errorMessage?.let { message -> ErrorCard(message) }
      state.latestBatch?.let { batch ->
        Text(
          "Результаты",
          style = MaterialTheme.typography.titleLarge,
          fontWeight = FontWeight.Bold,
        )
        if (batch.mode == "free") {
          Text(batch.mode_message, color = MaterialTheme.colorScheme.secondary)
        }
        batch.results.forEach { TemperatureResultCard(it, batch.mode) }
      }

      if (state.isBenchmarkPrompt && state.latestBatch?.mode == "benchmark") {
        UniqueNamesCard(state.uniqueNames)
      }
      if (state.history.isNotEmpty()) {
        HistorySection(state.history)
      }
    }
  }
}

@Composable
private fun ExperimentParametersCard(config: TemperatureExperimentConfigDto?) {
  var expanded by rememberSaveable { mutableStateOf(false) }
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
      TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth()) {
        Text(if (expanded) "Скрыть параметры эксперимента" else "Параметры эксперимента")
      }
      if (expanded) {
        Text("Модель: ${config?.model ?: "gpt-5.6"}")
        Text("Значения temperature: 0 / 0.7 / 1.2")
        Text("Рассуждение: effort=none, mode=standard")
        Text("Максимум выходных токенов: 600")
        Text("top_p: значение по умолчанию")
        Text("Хранение ответа: отключено")
        Text("Формат: строгая структура variants для benchmark, обычный текст для свободного режима")
        Text("Меняется только temperature", fontWeight = FontWeight.Bold)
      }
    }
  }
}

@Composable
private fun TemperatureResultCard(result: TemperatureResultDto, mode: String) {
  var expanded by rememberSaveable(result.temperature, result.status, result.latency_ms) {
    mutableStateOf(false)
  }
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
      Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(
          "temperature ${formatTemperature(result.temperature)}",
          style = MaterialTheme.typography.titleMedium,
          fontWeight = FontWeight.Bold,
        )
        Text(localizedStatus(result.status), fontWeight = FontWeight.SemiBold)
      }
      if (mode == "benchmark" && result.validation != null) {
        Text(
          "Соблюдение требований: ${result.validation.requirements_met}/" +
            "${result.validation.total_requirements}",
          fontWeight = FontWeight.Bold,
        )
      } else if (mode == "free") {
        Text("Автопроверка benchmark недоступна для произвольного запроса.")
      }
      Text(
        "Токены: вход ${result.usage.input_tokens}, выход ${result.usage.output_tokens}, " +
          "рассуждение ${result.usage.reasoning_tokens}, всего ${result.usage.total_tokens}"
      )
      Text("Задержка этого запроса: ${result.latency_ms} мс")
      result.error?.let { Text("Ошибка: ${it.message}", color = MaterialTheme.colorScheme.error) }
      val hasAnswer = result.content != null || result.variants != null
      if (hasAnswer) {
        OutlinedButton(
          onClick = { expanded = !expanded },
          modifier = Modifier.fillMaxWidth(),
        ) {
          Text(if (expanded) "Скрыть ответ" else "Показать ответ")
        }
      }
      if (expanded) {
        HorizontalDivider()
        SelectionContainer {
          Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            result.variants?.forEachIndexed { index, variant ->
              Text("${index + 1}. ${variant.name} — ${variant.slogan}")
            }
            result.content?.let { Text(it) }
          }
        }
      }
    }
  }
}

@Composable
private fun UniqueNamesCard(aggregates: List<UniqueNameAggregate>) {
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
      Text("Уникальные названия", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
      Text("Уникальных после нормализации / всего создано за сессию.")
      aggregates.forEach { item ->
        Text(
          "temperature ${formatTemperature(item.temperature)}: " +
            "${item.uniqueCount} / ${item.totalGenerated}"
        )
      }
    }
  }
}

@Composable
private fun HistorySection(history: List<TemperatureLabBatchResponseDto>) {
  Text("История текущего запроса", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
  history.forEachIndexed { index, batch ->
    Card(modifier = Modifier.fillMaxWidth()) {
      Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Запуск ${index + 1}: ${batch.request_id}", fontWeight = FontWeight.SemiBold)
        Text("Режим: ${if (batch.mode == "benchmark") "benchmark" else "свободный"}")
        batch.results.forEach { result ->
          Text(
            "temperature ${formatTemperature(result.temperature)} — " +
              "${localizedStatus(result.status)}, ${result.usage.total_tokens} токенов, " +
              "${result.latency_ms} мс"
          )
        }
      }
    }
  }
}

@Composable
private fun ErrorCard(message: String) {
  Card(modifier = Modifier.fillMaxWidth()) {
    Text(
      "Ошибка запуска: $message",
      modifier = Modifier.padding(16.dp),
      color = MaterialTheme.colorScheme.error,
    )
  }
}

private fun localizedStatus(status: String): String =
  when (status) {
    "completed" -> "Завершён"
    "incomplete" -> "Не завершён"
    "error" -> "Ошибка"
    else -> "Неизвестный статус"
  }

private fun formatTemperature(temperature: Double): String =
  if (temperature == 0.0) "0" else temperature.toString()
