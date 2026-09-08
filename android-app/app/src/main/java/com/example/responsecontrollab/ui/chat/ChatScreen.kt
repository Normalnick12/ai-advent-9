package com.example.responsecontrollab.ui.chat

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.R
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar

@Composable
fun ChatScreen(viewModel: ChatViewModel, onBack: () -> Unit, day: LearningDay = LearningDay.FIRST_AGENT) {
  LaunchedEffect(viewModel) { viewModel.initialize() }
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  val scroll = rememberSaveable(state.generation, saver = LazyListState.Saver) { LazyListState() }
  Scaffold(
    topBar = { LearningDayTopBar(day, onBack) },
    contentWindowInsets = WindowInsets.safeDrawing,
  ) { padding ->
    val turnCount = state.historyTurnCount
    Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().padding(horizontal = 16.dp).testTag("chat_screen")) {
      Text(if (turnCount == null) stringResource(R.string.chat_count_unknown)
        else stringResource(R.string.chat_turn_count, turnCount), Modifier.testTag("chat_count"))
      if (state.restored) Text(stringResource(R.string.chat_restored), Modifier.testTag("chat_restored"))
      LazyColumn(
        state = scroll,
        modifier = Modifier.weight(1f).fillMaxWidth().testTag("chat_transcript"),
        contentPadding = PaddingValues(vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
      ) {
        if (state.messages.isEmpty() && state.pendingUser == null && !state.restored && state.restoration == ChatRestoration.READY) {
          item { Text(stringResource(R.string.chat_empty)) }
        }
        itemsIndexed(state.messages) { index, message ->
          ChatBubble(message, Modifier.testTag("chat_message_$index"))
        }
        state.pendingUser?.let { pending ->
          item { ChatBubble(ChatMessage(true, pending), Modifier.testTag("chat_pending")) }
        }
        state.error?.let { error ->
          item { Text(error, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("chat_error")) }
        }
      }
      if (state.busy) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(stringResource(when (state.operation) {
          ChatOperation.RESTORING -> R.string.chat_restoring
          ChatOperation.SAVING_ID -> R.string.chat_saving_id
          ChatOperation.CREATING -> R.string.chat_creating
          ChatOperation.RESETTING -> R.string.chat_resetting
          else -> R.string.chat_sending
        }))
      }
      if (state.canRetryRestore) OutlinedButton(onClick = viewModel::retryRestore, modifier = Modifier.testTag("chat_restore_retry")) {
        Text(stringResource(R.string.chat_restore_retry))
      }
      OutlinedTextField(
        value = state.draft,
        onValueChange = viewModel::updateDraft,
        label = { Text(stringResource(R.string.chat_message)) },
        enabled = !state.busy,
        minLines = 1, maxLines = 3,
        modifier = Modifier.fillMaxWidth().testTag("chat_input"),
      )
      // A wrapping row keeps both actions accessible with large system fonts.
      FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = viewModel::send, enabled = state.canSend, modifier = Modifier.testTag("chat_send")) {
          Text(stringResource(R.string.chat_send))
        }
        OutlinedButton(onClick = viewModel::newConversation, enabled = state.canReset, modifier = Modifier.testTag("chat_reset")) {
          Text(stringResource(R.string.chat_reset))
        }
      }
    }
  }
}

@Composable
private fun ChatBubble(message: ChatMessage, modifier: Modifier = Modifier) {
  Surface(
    modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium,
    color = if (message.isUser) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainer,
  ) {
    Column(Modifier.padding(12.dp)) {
      Text(stringResource(if (message.isUser) R.string.chat_user else R.string.chat_agent), style = MaterialTheme.typography.labelLarge)
      SelectionContainer { Text(message.text) }
    }
  }
}
