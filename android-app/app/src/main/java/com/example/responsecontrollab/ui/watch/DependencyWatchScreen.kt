package com.example.responsecontrollab.ui.watch

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
import com.example.responsecontrollab.data.WatchFactsDto
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar

@Composable
fun DependencyWatchScreen(viewModel: DependencyWatchViewModel, onBack: () -> Unit) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  DependencyWatchContent(state, viewModel::editPrompt, viewModel::selectOperation,
    viewModel::selectWatch, viewModel::send, onBack)
}

@Composable
fun DependencyWatchContent(state: DependencyWatchUiState, editPrompt: (String) -> Unit,
  selectOperation: (String) -> Unit, selectWatch: (String) -> Unit, send: () -> Unit, onBack: () -> Unit) {
  var inspector by rememberSaveable(state.result?.operation_id, state.isLoading) { mutableStateOf(false) }
  Scaffold(topBar = { LearningDayTopBar(LearningDay.DEPENDENCY_WATCH, onBack) }) { padding ->
    Box(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding(), contentAlignment = Alignment.TopCenter) {
      Column(Modifier.widthIn(max = 640.dp).fillMaxSize().verticalScroll(rememberScrollState())
        .padding(16.dp).testTag("watch_scroll"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Фоновые проверки Google Maven", style = MaterialTheme.typography.titleLarge)
        Text("Watch выполняется на VPS. Для создания и получения сводки нужен локальный backend.")
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
          FilterChip(selected = state.operation == "create", onClick = { selectOperation("create") },
            enabled = !state.isLoading, label = { Text("Создать") })
          FilterChip(selected = state.operation == "summary", onClick = { selectOperation("summary") },
            enabled = !state.isLoading, label = { Text("Сводка") })
        }
        Text("Сохранённые watches", style = MaterialTheme.typography.titleMedium)
        if (state.receipts.watches.isEmpty()) Text("Пока нет сохранённых watch IDs.")
        state.receipts.watches.forEach { watch ->
          OutlinedButton(onClick = { selectWatch(watch.watch_id) }, enabled = !state.isLoading,
            modifier = Modifier.fillMaxWidth().testTag("watch_select_${watch.watch_id}")) {
            Text("${if (state.receipts.selectedId == watch.watch_id) "✓ " else ""}${watch.group_id}:${watch.artifact_id}\n${watch.watch_id}\nПоследнее известное: ${watch.status}, ${watch.runs_total}/${watch.max_runs}\nИнтервал: ${watch.interval_seconds} с; следующий: ${watch.next_run_at ?: "нет"}")
          }
        }
        OutlinedTextField(state.prompt, editPrompt, label = { Text("Запрос агенту") }, minLines = 3,
          enabled = !state.isLoading, modifier = Modifier.fillMaxWidth().testTag("watch_prompt"))
        Text(if (state.operation == "create") "Каждый принятый вызов создаёт новый watch. Автоматического повтора нет."
             else "Сводка читает сохранённые результаты выбранного watch.")
        Button(onClick = send, enabled = !state.isLoading && (state.operation == "create" || state.receipts.selectedId != null),
          modifier = Modifier.fillMaxWidth().testTag("watch_send")) {
          Text(if (state.isLoading) "Ожидание…" else if (state.operation == "create") "Создать watch" else "Получить сводку")
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("watch_error")) }
        if (state.error != null && state.result == null && state.submittedRequest != null) {
          TextButton(onClick = { inspector = !inspector }, modifier = Modifier.testTag("watch_inspector")) { Text("Inspector") }
          if (inspector) SelectionContainer {
            Text("Submitted action: ${state.submittedRequest.operation}\nSelected watch: ${state.submittedRequest.watch_id ?: "нет"}\nSubmitted prompt: ${state.submittedRequest.prompt}\nResponse/calls: недоступны, факт вызова неизвестен")
          }
        }
        state.result?.let { result ->
          Text("Результат попытки: ${result.outcome}")
          Text("Факт вызова: ${result.invocation}")
          result.error_message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
          if (!result.evidence_saved) Text("Evidence на backend не сохранён.")
          if (result.calls.count { it.receipt != null } > 1) Text("Агент создал несколько watches. Все IDs сохранены; выберите нужный.")
          result.calls.forEach { call ->
            call.receipt?.let { Facts(it, false) }
            call.summary?.let { Facts(it, true) }
          }
          Text("Объяснение модели", style = MaterialTheme.typography.titleMedium)
          SelectionContainer { Text(result.final_text ?: "Модель не вернула объяснение.") }
          TextButton(onClick = { inspector = !inspector }, modifier = Modifier.testTag("watch_inspector")) {
            Text(if (inspector) "Скрыть Inspector" else "Inspector")
          }
          if (inspector) SelectionContainer {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
              Text("Operation id: ${result.operation_id}\nResponse id: ${result.response_id ?: "не предоставлен"}\nProvider status: ${result.provider_status ?: "не предоставлен"}\nEndpoint: ${result.server_url ?: "не задан"}")
              Text("Action: ${result.operation}\nSelected watch: ${result.selected_watch_id ?: "нет"}")
              Text("Submitted prompt: ${result.submitted_prompt}")
              if (result.calls.isEmpty()) Text("MCP calls отсутствуют в полученном результате.")
              result.calls.forEach { call ->
                Text("Call id: ${call.id ?: "не предоставлен"}\nTool: ${call.name}\nCall status: ${call.status ?: "не предоставлен"}\nOutcome: ${call.outcome}")
                Text("Arguments: ${call.arguments ?: "нет"}")
                Text("Output: ${call.output ?: "нет"}\nError: ${call.error ?: "нет"}")
              }
              Text("MCP items (discovery и calls): ${result.mcp_items}")
            }
          }
        }
      }
    }
  }
}

@Composable
private fun Facts(facts: WatchFactsDto, summary: Boolean) {
  Card(Modifier.fillMaxWidth()) {
    SelectionContainer {
      Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(if (summary) "Сохранённая сводка" else "Watch зарегистрирован", style = MaterialTheme.typography.titleMedium)
        Text("${facts.group_id}:${facts.artifact_id}\n${facts.watch_id}")
        Text("Статус: ${facts.status}\nЗапуски: ${facts.runs_total}/${facts.max_runs}\nИнтервал: ${facts.interval_seconds} с\nСледующий: ${facts.next_run_at ?: "нет"}\nПропущенные слоты: ${facts.skipped_slots}")
        if (summary) {
          if (facts.runs_total == 0) Text("Ожидание первой проверки; baseline ещё отсутствует.")
          facts.latest_execution?.let { Text("Последний run: ${it.state}; outcome: ${it.lookup_outcome ?: "неизвестен"}; ошибка: ${it.error_category ?: "нет"}") }
          Text("Успешно: ${facts.successful} · Ошибок: ${facts.failed} · Прервано: ${facts.interrupted}")
          Text("Сравнимых проверок: ${facts.comparable_snapshots}\nВерсий сначала: ${facts.first_version_count ?: "нет данных"}\nВерсий сейчас: ${facts.last_version_count ?: "нет данных"}\nИзменений: ${facts.changes_detected}")
          Text("Впервые замечены после baseline: ${facts.newly_seen_versions.joinToString().ifEmpty { "нет" }}")
          Text("Первая проверка: ${facts.first_checked_at ?: "нет данных"}\nПоследняя: ${facts.last_checked_at ?: "нет данных"}\nСводка через execution: ${facts.through_execution_id ?: "нет"}\nСформирована: ${facts.generated_at ?: "нет"}")
          facts.running_execution?.let { Text("Выполняется: ${it.run_id}") }
        }
      }
    }
  }
}
