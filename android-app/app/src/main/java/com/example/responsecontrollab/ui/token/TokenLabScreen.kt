package com.example.responsecontrollab.ui.token

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import com.example.responsecontrollab.ui.chat.ChatBubble
import com.example.responsecontrollab.ui.chat.ChatComposer
import java.util.Locale
import kotlinx.coroutines.delay

private fun countText(value: Long?, source: String = ""): String =
  value?.toString() ?: if (source == "not_measured") "не измерялось" else "нет данных"
private fun costText(cost: TokenCostDto?): String =
  if (cost?.status == "available" && cost.amountUsd != null) "${cost.amountUsd} USD" else "нет данных"

@Composable
fun TokenDiagnosticsBlock(result: TokenTurnDto) {
  val d = result.diagnostics
  var details by rememberSaveable(result.attemptId) { mutableStateOf(false) }
  Column(verticalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.testTag("token_diagnostics")) {
    Text("Диагностика последней попытки", style = MaterialTheme.typography.titleMedium)
    Text("Новое сообщение — отдельный provider count: ${countText(d?.currentMessageTokens, d?.currentSource.orEmpty())}")
    Text("Сохранённая история — отдельный provider count: ${countText(d?.savedHistoryTokens, d?.historySource.orEmpty())}")
    if (d?.historySource == "empty_history") Text("В сохранённой истории нет сообщений.")
    Text("Измерения не складываются. Новое сообщение и история посчитаны отдельно с оформлением сообщений; полный input включает инструкции и оформление всего запроса.")
    Text("Preflight input модели: ${countText(d?.preflightInputTokens)}", Modifier.testTag("token_preflight"))
    Text("Actual API input: ${countText(result.usage?.inputTokens)}", Modifier.testTag("token_actual_input"))
    Text("Actual output: ${countText(result.usage?.outputTokens)}")
    if (d != null) {
      val input = d.preflightInputTokens
      val fraction = if (input != null && d.contextWindow > 0) input.toDouble()/d.contextWindow else null
      Text("Контекст (preflight): ${countText(input)} / ${d.contextWindow}" +
        (fraction?.let { " — ${String.format(Locale.ROOT, "%.1f", it*100)}%" } ?: ""))
      if (fraction != null) LinearProgressIndicator(progress = { fraction.toFloat().coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
      Text("Резерв ответа: ${d.reservedOutputTokens} tokens (не actual usage)")
      if (d.reserveWarning) Text("Input с резервом ответа превышает окно.", color = MaterialTheme.colorScheme.error)
      Text("Подтверждённых ходов до этой попытки: ${d.historyTurnCountBefore}")
    }
    Text("Оценочная стоимость хода: ${costText(result.cost)}", Modifier.testTag("token_cost"))
    TextButton(onClick = { details = !details }) { Text(if (details) "Скрыть детали" else "Детали измерений") }
    if (details) {
      Text("Модель: ${result.resolvedModel ?: result.requestedModel ?: result.preparation?.model ?: "нет данных"}")
      Text("Tier: ${result.actualServiceTier ?: "нет данных"}; requested: ${result.requestedServiceTier ?: "нет данных"}")
      Text("Cached input: ${countText(result.usage?.cachedInputTokens)}; cache write: ${countText(result.usage?.cacheWriteTokens)}")
      Text("Reasoning: ${countText(result.usage?.reasoningTokens)}; total: ${countText(result.usage?.totalTokens)}")
      Text("Count calls: ${d?.countCalls ?: 0}; actual usage берётся только из ответа generation.")
      Text("Тарифы USD/MTok: input ${result.cost.inputRate}, cached ${result.cost.cachedInputRate}, output ${result.cost.outputRate}. Дата: ${result.cost.pricingDate}")
      Text(result.cost.source)
    }
  }
}

@Composable
fun TokenLabScreen(viewModel: TokenLabViewModel, onBack: () -> Unit) {
  LaunchedEffect(viewModel) { viewModel.initialize() }
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  val scroll = rememberSaveable(state.generation, saver = LazyListState.Saver) { LazyListState() }
  var confirmId by remember { mutableStateOf<String?>(null) }
  val p = state.preparation
  LaunchedEffect(p?.preparationId) {
    if (p != null) {
      delay((p.expiresAt*1000-System.currentTimeMillis()).toLong().coerceAtLeast(0))
      viewModel.expirePreparation(p.preparationId)
    }
  }
  if (p != null && confirmId != null && confirmId == p.preparationId) {
    AlertDialog(onDismissRequest = { confirmId = null }, title = { Text("Выполнить реальный overflow-запрос?") },
      text = { Text("Будет выполнен ровно один запрос к ${p.model} с отключённым truncation. Возможны расходы или другая provider ошибка. История не изменится при любом исходе.") },
      confirmButton = { TextButton(onClick = { confirmId = null; viewModel.executeOverflow() }, modifier = Modifier.testTag("token_confirm")) { Text("Подтверждаю один запрос") } },
      dismissButton = { TextButton(onClick = { confirmId = null }) { Text("Отмена") } })
  }
  Scaffold(topBar = { LearningDayTopBar(LearningDay.TOKEN_LAB, onBack) }, contentWindowInsets = WindowInsets.safeDrawing) { padding ->
    Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().padding(horizontal = 16.dp).testTag("token_screen")) {
      Text("Завершённых ходов: ${state.historyTurnCount ?: "нет данных"}", Modifier.testTag("token_count"))
      LazyColumn(state = scroll, modifier = Modifier.weight(1f).fillMaxWidth().testTag("token_content"),
        verticalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(vertical = 12.dp)) {
        item {
          Text("gpt-4o-mini · Полная подтверждённая история отправляется заново.")
          if (state.restored) Text("Диалог восстановлен. Предыдущие сообщения не отображаются.")
        }
        itemsIndexed(state.messages) { i, m -> ChatBubble(m, Modifier.testTag("token_message_$i")) }
        state.lastAttempt?.let { result -> item { TokenDiagnosticsBlock(result) } }
        state.error?.let { error -> item { Text(error, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("token_error")) } }
        if (state.restoreFailed || state.probeRefreshRequired) item {
          OutlinedButton(onClick = viewModel::retryRestore, enabled = !state.busy && !state.recoveryRequired) { Text("Повторить проверку диалога") }
        }
        item {
          Text("Последние попытки этого запуска (до 20)", style = MaterialTheme.typography.titleMedium)
          Text("№ · Actual input · Output · Оценочная стоимость")
        }
        itemsIndexed(state.observations) { _, row ->
          Text("${row.number} · ${countText(row.result?.usage?.inputTokens)} · ${countText(row.result?.usage?.outputTokens)} · ${costText(row.result?.cost)} · ${when (row.outcome) {
            "completed" -> "завершено"; "incomplete" -> "ответ не завершён"; "refused" -> "отказ"; "unknown" -> "исход неизвестен"; else -> "ошибка"
          }}", Modifier.testTag("token_row_${row.number}"))
        }
        item {
          OutlinedButton(onClick = viewModel::loadLongText, enabled = state.ready, modifier = Modifier.testTag("token_long")) { Text("Вставить длинный учебный текст") }
          Text("200 нумерованных строк; текст можно изменить перед отправкой.")
          OutlinedButton(onClick = viewModel::prepareOverflow, enabled = state.ready, modifier = Modifier.testTag("token_prepare")) { Text("Подготовить переполнение") }
          Text("Подготовка только считает токены. Один новый тестовый user message: заголовок, повторы ASCII-блока, просьба кратко ответить. История не подменяется.")
        }
        p?.let { prepared -> item {
          Text("Подготовлено: ${prepared.model}", style = MaterialTheme.typography.titleMedium)
          Text("Новый текст: ${prepared.messageChars} символов / ${prepared.messageUtf8Bytes} UTF-8 bytes. Полный payload: ${prepared.fullPayloadBytes} bytes.")
          Text("Рецепт: ${prepared.header} Блок: ${prepared.unit.trimEnd()}; LF после блока; повторов: ${prepared.repeats}; окончание: ${prepared.ending}")
          Text("Образец начала: ${prepared.sampleStart}\nОбразец конца: ${prepared.sampleEnd}")
          Text("SHA-256: ${prepared.payloadSha256}")
          Text("Это реальный запрос сверх окна модели. Подготовка ещё не запускала generation.")
          Button(onClick = { confirmId = prepared.preparationId }, enabled = state.ready, modifier = Modifier.testTag("token_execute")) { Text("Выполнить один overflow-запрос") }
          OutlinedButton(onClick = viewModel::cancelPreparation, enabled = !state.busy) { Text("Отменить подготовку") }
        } }
      }
      if (state.busy) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(when (state.operation) {
          TokenOperation.RESTORING -> "Восстановление диалога…"
          TokenOperation.CREATING -> "Создание диалога…"
          TokenOperation.SAVING_ID -> "Сохранение ID…"
          TokenOperation.PREPARING -> "Подсчёт большого запроса…"
          TokenOperation.EXECUTING -> "Один overflow-запрос…"
          TokenOperation.RESETTING -> "Сброс диалога…"
          else -> "Подсчёт и ответ модели…"
        })
      }
      ChatComposer(state.draft, viewModel::updateDraft, state.busy, state.canSend,
        state.canReset, viewModel::send, viewModel::newConversation, "token")
    }
  }
}
