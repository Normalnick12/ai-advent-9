package com.example.responsecontrollab.ui.benchmark

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.ModelBenchmarkConfigDto
import com.example.responsecontrollab.data.ModelBenchmarkResultDto
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import java.math.BigDecimal
import java.math.RoundingMode
import java.util.Locale
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

private val answerJson = Json { prettyPrint = true }

@Composable
fun ModelBenchmarkScreen(viewModel: ModelBenchmarkViewModel, onBack: () -> Unit) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  LaunchedEffect(viewModel) { viewModel.onOpen() }
  ModelBenchmarkContent(state, viewModel::selectModel, viewModel::runComparison, viewModel::loadCatalog, onBack)
}

@Composable
fun ModelBenchmarkContent(
  state: ModelBenchmarkUiState,
  onSelect: (String, String) -> Unit,
  onRun: () -> Unit,
  onReloadCatalog: () -> Unit,
  onBack: () -> Unit,
) {
  Scaffold(
    modifier = Modifier.fillMaxSize(), contentWindowInsets = WindowInsets.safeDrawing,
    topBar = { LearningDayTopBar(LearningDay.MODEL_BENCHMARK, onBack) },
  ) { padding ->
    Column(
      Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
        .testTag("lesson_05").verticalScroll(rememberScrollState()).padding(16.dp),
      verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
      Text("Пять задач. Три модели. Один эксперимент.", style = MaterialTheme.typography.titleMedium)
      Text("Меняется только модель; запрос и параметры одинаковы для всех трёх вызовов.")
      if (state.catalogLoading) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Загружаем каталог моделей…")
      }
      state.catalogError?.let {
        Text(it, color = MaterialTheme.colorScheme.error)
        OutlinedButton(onClick = onReloadCatalog, enabled = !state.catalogLoading) { Text("Повторить загрузку каталога") }
      }
      state.catalog?.let { catalog ->
        catalog.roles.forEach { role ->
          val selected = catalog.models.find { it.id == state.selections[role.id] }
          var expanded by rememberSaveable(role.id) { mutableStateOf(false) }
          Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(role.display_name, fontWeight = FontWeight.SemiBold)
            Box {
              OutlinedButton(
                onClick = { expanded = true }, modifier = Modifier.fillMaxWidth().testTag("model_select_${role.id}"),
                enabled = !state.isLoading && !state.catalogLoading,
              ) {
                Column(Modifier.fillMaxWidth()) {
                  Text(selected?.display_name ?: "Выберите модель")
                  selected?.let { Text(it.id, style = MaterialTheme.typography.bodySmall) }
                }
              }
              DropdownMenu(expanded = expanded && !state.isLoading, onDismissRequest = { expanded = false }) {
                catalog.models.filter { it.id in role.allowed_model_ids }.forEach { model ->
                  DropdownMenuItem(
                    text = { Column { Text(model.display_name); Text(model.tier, style = MaterialTheme.typography.bodySmall) } },
                    onClick = { onSelect(role.id, model.id); expanded = false },
                    modifier = Modifier.testTag("model_option_${role.id}_${model.id}"),
                  )
                }
              }
            }
          }
        }
        if (state.selections.values.size != state.selections.values.toSet().size) {
          Text("Одна модель выбрана несколько раз: каждый слот выполнит отдельный запрос.", color = MaterialTheme.colorScheme.secondary)
        }
      }
      Button(
        onClick = onRun, modifier = Modifier.fillMaxWidth().testTag("benchmark_run"),
        enabled = state.catalog != null && state.catalogError == null && !state.catalogLoading && !state.isLoading,
      ) { Text("Запустить сравнение") }
      if (state.isLoading) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Сравнение выполняется. Три запроса запущены параллельно.", modifier = Modifier.testTag("benchmark_loading"))
      }
      state.runError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("benchmark_error")) }
      (state.latestBatch?.config ?: state.catalog?.config)?.let { ParametersCard(it) }
      state.latestBatch?.let { batch ->
        Text(
          if (state.isLoading || state.runError != null) "Предыдущий результат" else "Результаты последнего запуска",
          style = MaterialTheme.typography.titleLarge,
        )
        Text("Запуск ${batch.request_id} · Вызовов API: ${batch.api_call_count}", style = MaterialTheme.typography.bodySmall)
        batch.results.forEach { result ->
          key(batch.request_id, result.role) { ResultCard(result, batch.request_id) }
        }
        Text("Один запуск — наблюдение, а не устойчивый рейтинг. Сравнивайте качество, время и стоимость для своей задачи.")
      }
    }
  }
}

@Composable
private fun ParametersCard(config: ModelBenchmarkConfigDto) {
  var expanded by rememberSaveable(config.fingerprint) { mutableStateOf(false) }
  Card(Modifier.fillMaxWidth()) {
    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
      TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth().testTag("benchmark_parameters")) {
        Text(if (expanded) "Скрыть параметры эксперимента" else "Параметры эксперимента")
      }
      if (expanded) {
        Text("Версия: ${config.benchmark_version} · Responses API")
        Text("Рассуждение: ${config.reasoning_effort} · Лимит выхода: ${config.max_output_tokens}")
        Text("temperature: ${config.temperature} · top_p: ${config.top_p}")
        Text("Строгий JSON: ${if (config.strict_output) "да" else "нет"} · Повторов: ${config.max_retries}")
        Text("Хранение: ${if (config.store) "включено" else "выключено"} · Тариф: ${config.service_tier}")
        Text("Запуск: ${config.execution} · Ожидание модели: ${config.upstream_timeout_seconds} с")
        Text("Инструкция", fontWeight = FontWeight.Bold)
        SelectionContainer { Text(config.instructions) }
        Text("Общий запрос", fontWeight = FontWeight.Bold)
        SelectionContainer { Text(config.prompt) }
        Text("SHA-256: ${config.fingerprint}", style = MaterialTheme.typography.bodySmall)
      }
    }
  }
}

@Composable
private fun ResultCard(result: ModelBenchmarkResultDto, requestId: String) {
  var expanded by rememberSaveable(requestId, result.role) { mutableStateOf(false) }
  Card(Modifier.fillMaxWidth().testTag("benchmark_result_${result.role}")) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
      Text(result.display_name, style = MaterialTheme.typography.titleLarge)
      Text(localizedStatus(result.status), color = MaterialTheme.colorScheme.secondary)
      val metrics = listOf(
        "Качество" to (result.quality?.let { "${it.correct_count}/${it.total_tasks}" } ?: "Нет проверяемого результата"),
        "Время" to String.format(Locale.forLanguageTag("ru"), "%.2f с", result.latency_ms / 1000.0),
        "Токены" to number(result.usage.total_tokens),
        "Стоимость" to formatBenchmarkCost(result.cost.amount_usd),
      )
      BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = if (maxWidth < 280.dp || LocalDensity.current.fontScale > 1.2f) 1 else 2
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
          metrics.chunked(columns).forEach { group ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
              group.forEach { (label, value) ->
                Column(Modifier.weight(1f)) {
                  Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                  Text(value, fontWeight = FontWeight.SemiBold)
                }
              }
            }
          }
        }
      }
      result.reason?.let { Text(it, color = MaterialTheme.colorScheme.error) }
      Text("Стоимость по тарифам, USD", style = MaterialTheme.typography.bodySmall)
      OutlinedButton(
        onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth().testTag("benchmark_details_${result.role}"),
      ) { Text(if (expanded) "Скрыть детали" else "Показать детали") }
      if (expanded) {
        result.tasks.forEachIndexed { index, task ->
          HorizontalDivider()
          Text("Задача ${index + 1} — ${verdictLabel(task.verdict)}", fontWeight = FontWeight.Bold)
          SelectionContainer {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
              Text("Ответ модели:")
              Text(task.actual_answer?.let { answerJson.encodeToString(JsonObject.serializer(), it) } ?: "Нет проверяемого результата")
              task.reference_answer?.let {
                Text("Эталон проверки:")
                Text(answerJson.encodeToString(JsonObject.serializer(), it))
              }
            }
          }
        }
        HorizontalDivider()
        SelectionContainer {
          Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Подробные метрики", style = MaterialTheme.typography.titleMedium)
            Text("Входные токены: ${number(result.usage.input_tokens)}")
            Text("Вход из кэша: ${number(result.usage.cached_input_tokens)}")
            Text("Запись в кэш: ${number(result.usage.cache_write_tokens)}")
            Text("Выходные токены: ${number(result.usage.output_tokens)}")
            Text("Рассуждение (часть выхода): ${number(result.usage.reasoning_tokens)}")
            Text("Всего токенов: ${number(result.usage.total_tokens)}")
            Text("Время API: ${result.latency_ms} мс")
            Text("Запрошенная модель: ${result.requested_model}")
            Text("Фактическая модель: ${result.resolved_model ?: "Нет данных"}")
            Text("Статус: ${result.status}")
            Text("Исходный статус: ${result.response_status ?: "Нет данных"}")
            Text("Вызовов API: ${result.api_call_count}")
            Text("Расчёт стоимости", style = MaterialTheme.typography.titleMedium)
            Text("Точная сумма: ${result.cost.amount_usd ?: "Нет данных"} USD")
            result.cost.reason?.let { Text(it) }
            Text("Тарифная модель: ${result.cost.pricing_model ?: "Нет данных"}")
            Text("Тариф: ${result.cost.service_tier ?: "Нет данных"}")
            result.cost.rates?.let {
              Text("За 1 млн токенов: вход ${it.input}, кэш ${it.cached_input}, запись ${it.cache_write}, выход ${it.output} USD")
            }
            Text(result.cost.formula)
            Text("I — вход; C — кэш; W — запись; O — выход. R — соответствующий тариф. Рассуждение уже включено в O.")
            Text("Источник: ${result.cost.source_url ?: "Нет данных"}")
            Text("Проверено: ${result.cost.checked_at ?: "Нет данных"}")
            if (result.quality == null) result.raw_output?.let {
              Text("Полученный текст", fontWeight = FontWeight.Bold)
              Text(it)
            }
          }
        }
      }
    }
  }
}

private fun number(value: Long?): String = value?.toString() ?: "Нет данных"

internal fun formatBenchmarkCost(value: String?): String {
  val amount = value?.toBigDecimalOrNull() ?: return "Нет данных"
  val rounded = amount.setScale(8, RoundingMode.HALF_UP)
  if (amount > BigDecimal.ZERO && rounded == BigDecimal.ZERO.setScale(8)) return "<0,00000001 USD"
  return rounded.stripTrailingZeros().toPlainString().replace('.', ',') + " USD"
}

private fun verdictLabel(verdict: String): String = when (verdict) {
  "correct" -> "Верно"
  "incorrect" -> "Неверно"
  else -> "Не проверено"
}

private fun localizedStatus(status: String): String = when (status) {
  "completed" -> "Завершено"
  "incomplete" -> "Ответ не завершён"
  "refused" -> "Отказ модели"
  "timeout" -> "Время ожидания истекло"
  "invalid_response" -> "Неверная структура ответа"
  "api_error" -> "Ошибка OpenAI"
  else -> "Ошибка обработки"
}
