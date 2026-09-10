package com.example.responsecontrollab.ui.compression

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.R
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import com.example.responsecontrollab.ui.chat.ChatBubble
import com.example.responsecontrollab.ui.chat.ChatComposer
import java.util.Locale
import kotlin.math.abs

private fun count(value: Long?) = value?.toString() ?: "нет данных"
private fun cost(phase: CompressionPhaseDto) = if (phase.cost.status == "available")
  "${phase.cost.amountUsd} USD" else "нет данных"
fun compressionDeltaText(context: CompressionContextDto?): String {
  val delta = context?.tokenDelta ?: return "Изменение: ещё не измерено"
  val percent = context.percentDelta?.let { String.format(Locale.ROOT, "%.1f", abs(it)) }
  return when {
    delta > 0 -> "Экономия: $delta токенов (${percent ?: "нет данных"}%)"
    delta < 0 -> "Дополнительный расход: ${abs(delta)} токенов (+${percent ?: "нет данных"}%)"
    else -> "Без изменения"
  }
}

@Composable
fun CompressionLabScreen(viewModel: CompressionLabViewModel, onBack: () -> Unit) {
  LaunchedEffect(viewModel) { viewModel.initialize() }
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  var details by rememberSaveable { mutableStateOf(false) }
  val holder = rememberSaveableStateHolder()
  BackHandler(enabled = details) { details = false }
  Scaffold(topBar = {
    if (!details) LearningDayTopBar(LearningDay.HISTORY_COMPRESSION, onBack)
    else Row(Modifier.fillMaxWidth().windowInsetsPadding(
      WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)).padding(8.dp)) {
      IconButton(onClick = { details = false }, modifier = Modifier.testTag("compression_details_back")) {
        Icon(painterResource(R.drawable.ic_arrow_back), "Назад к чату")
      }
      Column { Text("День 09", style = MaterialTheme.typography.labelMedium)
        Text("Статистика и сравнение", style = MaterialTheme.typography.titleLarge) }
    }
  }, contentWindowInsets = WindowInsets.safeDrawing) { padding ->
    holder.SaveableStateProvider(if (details) "details" else "chat") {
      Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().padding(horizontal = 16.dp)) {
        if (details) CompressionDetails(state, viewModel)
        else CompressionChat(state, viewModel) { details = true }
      }
    }
  }
}

@Composable
private fun ColumnScope.CompressionChat(state: CompressionLabState, vm: CompressionLabViewModel, onDetails: () -> Unit) {
  var preview by rememberSaveable { mutableStateOf(false) }
  val scroll = rememberSaveable(state.generation, saver = LazyListState.Saver) { LazyListState() }
  LazyColumn(state = scroll, modifier = Modifier.weight(1f).fillMaxWidth().testTag("compression_chat"),
    verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 8.dp)) {
    item {
      Text("Завершённых ходов: ${state.historyTurnCount ?: "нет данных"}", Modifier.testTag("compression_count"))
      Card(Modifier.fillMaxWidth().testTag("compression_context_card")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
          Text("Сжатие включено · Raw tail: последние 4 сообщения", style = MaterialTheme.typography.labelLarge)
          Text("Контекст последнего запроса", style = MaterialTheme.typography.labelMedium)
          val context = state.lastNormal?.context
          Text("В сводке: ${context?.summarizedMessageCount ?: "—"} · Raw: ${context?.rawTailCount ?: "—"}/4")
          Text(if (context == null) "FULL → COMPRESSED: ещё не измерено"
            else "FULL ${count(context.fullInputTokens)} → COMPRESSED ${count(context.compressedInputTokens)}")
          Text(compressionDeltaText(context), Modifier.testTag("compression_delta"))
        }
      }
      TextButton(onClick = onDetails, modifier = Modifier.testTag("compression_details")) { Text("Статистика и сравнение") }
      val step = state.historyTurnCount ?: 0
      if (step in 0..3) TextButton(onClick = { vm.loadFixture(step) }, enabled = state.ready,
        modifier = Modifier.testTag("compression_fixture")) { Text("Вставить учебный шаг ${step+1}/4") }
      if (state.draft.length > 300) TextButton(onClick = { preview = true }) { Text("Прочитать учебный текст целиком") }
      ErrorAndRecovery(state, vm)
    }
    if (state.restored) item { Text("Диалог восстановлен. Предыдущие сообщения не отображаются.") }
    itemsIndexed(state.messages) { i, message -> ChatBubble(message, Modifier.testTag("compression_message_$i")) }
  }
  OperationProgress(state)
  ChatComposer(state.draft, vm::updateDraft, state.busy, state.canSend, state.canReset,
    vm::send, vm::newConversation, "compression")
  if (preview) AlertDialog(onDismissRequest = { preview = false }, title = { Text("Текст перед отправкой") },
    text = { SelectionContainer(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) { Text(state.draft) } },
    confirmButton = { TextButton(onClick = { preview = false }) { Text("Закрыть") } })
}

@Composable
private fun ErrorAndRecovery(state: CompressionLabState, vm: CompressionLabViewModel) {
  state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("compression_error")) }
  if (state.restoreFailed || state.compareRefreshRequired) OutlinedButton(onClick = vm::retryRestore,
    enabled = !state.busy && !state.recoveryRequired) { Text("Повторить проверку диалога") }
}

@Composable
private fun OperationProgress(state: CompressionLabState) {
  if (state.busy) {
    LinearProgressIndicator(Modifier.fillMaxWidth())
    Text(when (state.operation) {
      CompressionActivity.RESTORING -> "Восстановление диалога…"
      CompressionActivity.SENDING -> "Подготовка контекста и ответ…"
      CompressionActivity.COMPARING -> "Подготовка и сравнение двух ответов…"
      CompressionActivity.RESETTING -> "Сброс диалога…"
      else -> "Чтение сохранённой сводки…"
    })
  }
}

@Composable
private fun ContextDetails(context: CompressionContextDto?) {
  if (context == null) { Text("Контекст ещё не измерен."); return }
  Text("FULL — полная история: ${count(context.fullInputTokens)} tokens")
  Text("COMPRESSED — сводка и raw tail: ${count(context.compressedInputTokens)} tokens")
  Text(compressionDeltaText(context))
  Text("В сводке ${context.summarizedMessageCount} сообщений; boundary ${context.boundary ?: "нет"}; raw tail ${context.rawTailCount}/4")
  Text("Размер сводки: ${context.summaryChars} символов; standalone count: ${count(context.summaryStandaloneTokens)}")
  Text("Standalone count включает оформление summary message без инструкций. Измерения не складываются.", style = MaterialTheme.typography.bodySmall)
  Text("Источник: FULL ${context.fullSource}, COMPRESSED ${context.compressedSource}; count calls ${context.countCalls}", style = MaterialTheme.typography.bodySmall)
  if (context.fullError != null || context.compressedError != null || context.summaryError != null)
    Text("Не все измерения доступны: ${listOfNotNull(context.fullError, context.compressedError, context.summaryError).joinToString()}")
  if (context.reserveWarning) Text("Input с резервом ответа ${context.reservedOutputTokens} превышает окно ${context.contextWindow}.", color = MaterialTheme.colorScheme.error)
}

@Composable
private fun PhaseDetails(label: String, phase: CompressionPhaseDto) {
  Text(label, style = MaterialTheme.typography.titleSmall)
  if (!phase.generationAttempted) { Text("Generation не выполнялась."); return }
  Text("Actual input ${count(phase.usage?.inputTokens)} · output ${count(phase.usage?.outputTokens)} · cached ${count(phase.usage?.cachedInputTokens)}")
  Text("Оценочная стоимость: ${cost(phase)} · ${phase.latencyMs ?: "—"} мс")
  Text("${phase.resolvedModel ?: phase.requestedModel ?: "модель неизвестна"} · ${phase.actualServiceTier ?: "tier неизвестен"} · ${phase.status}", style = MaterialTheme.typography.bodySmall)
  phase.errorCode?.let { Text(it, color = MaterialTheme.colorScheme.error) }
}

@Composable
private fun BranchCard(label: String, branch: CompressionBranchDto?, modifier: Modifier = Modifier) {
  Card(modifier.testTag("compression_branch_$label")) {
    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
      Text(label, style = MaterialTheme.typography.titleMedium)
      Text("Проверка трёх фактов: ${branch?.score?.let { "$it/3" } ?: "нет оценки"}")
      branch?.facts?.forEach { (name, ok) -> Text("$name: ${if (ok) "сохранён" else "не сохранён"}") }
      SelectionContainer { Text(branch?.reply ?: "Ответ недоступен") }
      branch?.let { Text("Статус: ${it.status}"); it.errorCode?.let { code -> Text(code) }; PhaseDetails("Response usage", it.phase) }
    }
  }
}

@Composable
private fun CompressionDetails(state: CompressionLabState, vm: CompressionLabViewModel) {
  val scroll = rememberSaveable(state.generation, saver = LazyListState.Saver) { LazyListState() }
  var showDurable by rememberSaveable(state.generation) { mutableStateOf(false) }
  var showLocal by rememberSaveable(state.comparison?.attemptId) { mutableStateOf(false) }
  LazyColumn(state = scroll, modifier = Modifier.fillMaxSize().testTag("compression_stats"),
    verticalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(vertical = 12.dp)) {
    item { Text("Контекст последнего запроса чата", style = MaterialTheme.typography.titleMedium); ContextDetails(state.lastNormal?.context) }
    item {
      TextButton(onClick = { showDurable = !showDurable; if (showDurable) vm.loadSummary() }, enabled = !state.busy,
        modifier = Modifier.testTag("compression_summary_toggle")) { Text(if (showDurable) "Скрыть сохранённую сводку" else "Текущая сохранённая сводка") }
      state.summaryMetadata?.let { Text("Durable: ${it.messageCount} сообщений; boundary ${it.boundary}") }
      if (showDurable) SelectionContainer { Text(if (!state.summaryLoaded && state.sessionId != null) "Сводка ещё не загружена" else state.summary?.text ?: "Сводка ещё не создана", Modifier.testTag("compression_durable_summary")) }
    }
    state.lastNormal?.let { normal -> item {
      PhaseDetails("Обновление сводки в последней попытке чата", normal.summaryPhase)
      PhaseDetails("Последний ответ чата", normal.responsePhase)
      Text("Вся операция: ${normal.latencyMs} мс; пара сохранена: ${normal.committed}")
    } }
    item {
      Text("Измерения текущего запуска приложения", style = MaterialTheme.typography.titleMedium)
      Text("Получено операций: ${state.observations.size}. Это наблюдаемые расходы, не lifetime billing диалога.")
      val unknown = state.observations.count { it.result == null }
      if (unknown > 0) Text("Операций с неизвестным результатом и расходом: $unknown")
      val latestSummary = state.observations.mapNotNull { it.result }
        .lastOrNull { it.kind == "send" && it.summaryPhase.generationAttempted }
      latestSummary?.let { PhaseDetails("Последняя выполненная summarization чата", it.summaryPhase) }
      val totals = state.totals()
      if (totals.isEmpty()) Text("Billable phase measurements ещё не получены.")
      totals.forEach { (name, total) ->
        Text("$name: ${total.calls} calls; известные input ${total.input}, output ${total.output}; ${total.cost.toPlainString()} USD")
        if (total.unknownCost > 0 || total.unknownUsage > 0) Text("Неполные данные: стоимость ${total.unknownCost}, usage ${total.unknownUsage} phases")
      }
      Text("Общая известная стоимость: ${totals.values.fold(java.math.BigDecimal.ZERO) { sum, value -> sum+value.cost }.toPlainString()} USD")
      Text("Меньше response input не доказывает экономию денег: обновление сводки и сравнение тоже оплачиваются.")
    }
    item {
      Text("Сравнить ответы на одном snapshot", style = MaterialTheme.typography.titleMedium)
      Text("Явный запуск: два ответа и, при необходимости, одна локальная сводка. Диалог и durable summary не изменяются.")
      OutlinedTextField(value = state.question, onValueChange = vm::updateQuestion, enabled = !state.busy,
        label = { Text("Вопрос для сравнения") }, modifier = Modifier.fillMaxWidth().testTag("compression_question"))
      FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { vm.compare(true) }, enabled = state.canCompare, modifier = Modifier.testTag("compression_compare_scored")) { Text("Проверить три факта") }
        OutlinedButton(onClick = { vm.compare(false) }, enabled = state.canCompare, modifier = Modifier.testTag("compression_compare")) { Text("Сравнить без оценки") }
      }
      TextButton(onClick = vm::loadQuestion, enabled = !state.busy) { Text("Вставить контрольный вопрос") }
      ErrorAndRecovery(state, vm); OperationProgress(state)
    }
    state.comparison?.let { result ->
      item {
        Text("Результат сравнения", style = MaterialTheme.typography.titleMedium)
        Text("Вопрос: ${result.question ?: "—"}")
        Text("Snapshot: ${result.snapshotId?.take(12) ?: "—"}; confirmed turns: ${result.historyTurnCount}")
        if (state.comparisonStale) Text("Результат относится к предыдущему snapshot диалога.")
        Text("Проверка применимости: ${result.scenarioStatus}")
        result.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        ContextDetails(result.context)
        PhaseDetails("Подготовка сравнения (отдельный overhead)", result.summaryPhase)
        Text("Wall-clock сравнения: ${result.latencyMs} мс; durations параллельных веток не складываются.")
      }
      item {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
          if (maxWidth >= 720.dp) Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.testTag("compression_side_by_side")) {
            BranchCard("FULL", result.full, Modifier.weight(1f)); BranchCard("COMPRESSED", result.compressed, Modifier.weight(1f))
          } else Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.testTag("compression_vertical")) {
            BranchCard("FULL", result.full, Modifier.fillMaxWidth()); BranchCard("COMPRESSED", result.compressed, Modifier.fillMaxWidth())
          }
        }
      }
      item {
        TextButton(onClick = { showLocal = !showLocal }) { Text(if (showLocal) "Скрыть сводку сравнения" else "Сводка, использованная в сравнении") }
        if (showLocal) {
          Text("Источник: ${if (result.summarySource == "compare_local") "локальная, не сохранена" else "durable snapshot"}; boundary ${result.compareSummary?.boundary ?: "нет"}")
          SelectionContainer { Text(result.compareSummary?.text ?: "Сводка отсутствует") }
        }
      }
    }
    item {
      Text("Учебные сообщения: каждое нужно явно отправить из чата.", style = MaterialTheme.typography.titleSmall)
      FlowRow { repeat(4) { index -> TextButton(onClick = { vm.loadFixture(index) }, enabled = state.ready) { Text("Вставить шаг ${index+1}") } } }
    }
  }
}
