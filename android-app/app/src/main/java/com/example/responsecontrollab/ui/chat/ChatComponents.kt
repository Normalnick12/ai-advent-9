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
fun ChatBubble(message: ChatMessage, modifier: Modifier = Modifier) {
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


@Composable
fun ChatComposer(draft: String, onDraft: (String) -> Unit, busy: Boolean,
                 canSend: Boolean, canReset: Boolean, onSend: () -> Unit, onReset: () -> Unit,
                 tagPrefix: String = "chat") {
  OutlinedTextField(value = draft, onValueChange = onDraft,
    label = { Text(stringResource(R.string.chat_message)) }, enabled = !busy,
    minLines = 1, maxLines = 3, modifier = Modifier.fillMaxWidth().testTag("${tagPrefix}_input"))
  FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    Button(onClick = onSend, enabled = canSend, modifier = Modifier.testTag("${tagPrefix}_send")) {
      Text(stringResource(R.string.chat_send))
    }
    OutlinedButton(onClick = onReset, enabled = canReset, modifier = Modifier.testTag("${tagPrefix}_reset")) {
      Text(stringResource(R.string.chat_reset))
    }
  }
}
