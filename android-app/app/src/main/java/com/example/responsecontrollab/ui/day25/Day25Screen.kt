package com.example.responsecontrollab.ui.day25

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import com.example.responsecontrollab.ui.chat.*

@Composable
fun Day25Screen(viewModel: Day25ViewModel, onBack: () -> Unit) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  var memoryExpanded by rememberSaveable { mutableStateOf(false) }
  val list = rememberLazyListState()
  LaunchedEffect(viewModel) { viewModel.initialize() }
  LaunchedEffect(state.visibleTurns.size) { if (state.visibleTurns.isNotEmpty()) list.animateScrollToItem(state.visibleTurns.size - 1) }
  Scaffold(topBar = { LearningDayTopBar(LearningDay.STATEFUL_RAG, onBack) }) { padding ->
    Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().padding(12.dp),
      verticalArrangement = Arrangement.spacedBy(8.dp)) {
      Text("Подтверждённых ходов: ${state.snapshot?.history_turn_count ?: if (state.sessionId == null && state.initialized) 0 else "—"} · revision ${state.snapshot?.revision ?: "—"}",
        modifier = Modifier.testTag("day25_session"))
      state.sessionId?.let { Text("Session: $it", style = MaterialTheme.typography.labelSmall) }
      Card(Modifier.fillMaxWidth()) {
        TextButton(onClick = { memoryExpanded = !memoryExpanded }, modifier = Modifier.testTag("day25_memory_toggle")) {
          Text(if (memoryExpanded) "Task Memory ▴" else "Task Memory ▾")
        }
        if (memoryExpanded) {
          val memory = state.snapshot?.memory
          LazyColumn(Modifier.fillMaxWidth().heightIn(max = 180.dp).padding(horizontal = 12.dp).testTag("day25_memory")) {
            val groups = listOf("Goal" to listOfNotNull(memory?.goal), "Constraints" to memory?.constraints.orEmpty(),
              "Terms" to memory?.terms.orEmpty(), "Clarifications" to memory?.clarifications.orEmpty())
            groups.forEach { (label, entries) ->
              item { Text("$label: ${if (entries.isEmpty()) "—" else ""}", style = MaterialTheme.typography.labelLarge) }
              items(entries) { Text("${it.text} (U${it.source_user_turn})", style = MaterialTheme.typography.bodySmall) }
            }
          }
        }
      }
      LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("day25_transcript"), state = list,
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        items(state.visibleTurns, key = { it.turn_id }) { turn ->
          Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            ChatBubble(ChatMessage(true, turn.user))
            ChatBubble(ChatMessage(false, turn.grounded.answer))
            if (turn.grounded.status == "insufficient_context") {
              Text("Недостаточно контекста · источников нет · Task Memory не обновлена", modifier = Modifier.testTag("day25_abstention"), style = MaterialTheme.typography.labelMedium)
            } else {
              Text("Источники", style = MaterialTheme.typography.labelLarge)
              turn.grounded.sources.forEach { source ->
                Text("${source.source} — ${source.section}", style = MaterialTheme.typography.bodySmall)
              }
            }
          }
        }
      }
      state.notice?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
      state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("day25_error")) }
      if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth().testTag("day25_loading"))
      if (state.recoveryRequired) OutlinedButton(onClick = viewModel::read, enabled = !state.busy,
        modifier = Modifier.testTag("day25_read")) { Text("Прочитать состояние") }
      ChatComposer(state.draft, viewModel::updateDraft, state.busy, state.canSend,
        state.canReset, viewModel::send, viewModel::reset, "day25")
    }
  }
}
