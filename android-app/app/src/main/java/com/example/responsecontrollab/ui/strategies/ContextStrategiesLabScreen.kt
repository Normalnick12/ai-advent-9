package com.example.responsecontrollab.ui.strategies

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar

fun strategyLabel(s: String) = when(s) { "window" -> "Окно"; "facts" -> "Факты"; else -> "Ветки" }
private fun StrategyMetric?.label() = this?.score?.let { "$it/11" } ?: "недоступно"

@Composable
fun ContextStrategiesLabScreen(viewModel: ContextStrategiesLabViewModel, onBack: ()->Unit) {
  val state by viewModel.uiState.collectAsState()
  LaunchedEffect(viewModel) { viewModel.initialize() }
  val pages=rememberSaveableStateHolder()
  var page by rememberSaveable { mutableStateOf("main") }
  val back = { if (page=="main") onBack() else page="main" }
  BackHandler(onBack=back)
  Scaffold(contentWindowInsets=WindowInsets.safeDrawing,
    topBar={ LearningDayTopBar(LearningDay.CONTEXT_STRATEGIES,back) }) { padding ->
    pages.SaveableStateProvider("$page/${state.selected}") {
      val scroll=rememberLazyListState()
      LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).testTag("strategies_scroll"),
        state=scroll,contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        if (page=="dashboard") {
          item { Text("Сравнение стратегий",style=MaterialTheme.typography.headlineSmall); TextButton(onClick={page="main"}) { Text("Назад к сценарию") } }
          STRATEGIES.forEach { s -> item(key=s) { DashboardCard(s,state.runs.getValue(s)) } }
          item { Text("Один сценарий не определяет универсального победителя. Стратегия должна соответствовать структуре задачи.") }
        } else if (page=="facts") {
          val facts=state.runs.getValue("facts").run?.facts.orEmpty()
          item { Text("Факты · только чтение",style=MaterialTheme.typography.headlineSmall) }
          item { Text("Актуальные") }
          facts.filter { it.state=="set" }.forEach { f -> item { Text("${f.scope}.${f.key} → ${f.value?.content}") } }
          item { Text("Отменённые") }
          facts.filter { it.state=="cleared" }.forEach { f -> item { Text("${f.scope}.${f.key} → отменено") } }
        } else {
          val s=state.selected; val ui=state.runs.getValue(s); val run=ui.run
          item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            STRATEGIES.forEach { strategy -> FilterChip(selected=s==strategy,onClick={viewModel.select(strategy)},label={Text(strategyLabel(strategy))},modifier=Modifier.weight(1f).testTag("strategy_$strategy")) }
          } }
          if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
          state.error?.let { error -> item { Text(error); Button(onClick=viewModel::initialize) { Text("Повторить загрузку") } } }
          item { StateCard(s,ui,viewModel) { page="facts" } }
          ui.error?.let { item { Text(it,color=MaterialTheme.colorScheme.error) } }
          if (ui.recovery) item { Button(onClick=viewModel::refresh,enabled=!ui.busy) { Text("Прочитать состояние") } }
          if (state.catalog != null) {
            val confirmed=run?.steps?.size ?: 0
            val index=ui.prepared ?: (confirmed+1).coerceAtMost(8)
            val fixture=state.catalog!!.steps[index-1]
            item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
              Text("Шаг $index из 8 · подтверждено $confirmed/8",style=MaterialTheme.typography.titleMedium)
              Text(fixture.title)
              fixture.preview.forEach { Text(it) }
              var raw by rememberSaveable(s,index) { mutableStateOf(false) }
              TextButton(onClick={raw=!raw}) { Text(if(raw) "Скрыть исходное сообщение" else "Показать исходное сообщение") }
              if (raw) Text(fixture.text,modifier=Modifier.testTag("fixture_raw"))
              when {
                ui.prepared != null && index<=confirmed -> {
                  Text("Шаг подтверждён")
                  if (confirmed<8) Button(onClick=viewModel::next,enabled=!ui.busy) { Text("Далее") }
                }
                confirmed<8 && ui.prepared==null -> Button(onClick=viewModel::prepare,enabled=!ui.busy && !ui.recovery) { Text("Подготовить шаг") }
                confirmed<8 -> {
                  val target=if(index==7) "A" else "B"
                  val branchReady=s!="branches" || index<=6 || (run?.checkpoint!=null && ui.branch==target)
                  if (!branchReady) Text(if(run?.checkpoint==null) "Сначала создайте checkpoint" else "Переключитесь в ветку $target")
                  Button(onClick=viewModel::send,enabled=!ui.busy && !ui.recovery && ui.evaluations.isEmpty() && branchReady,modifier=Modifier.testTag("strategy_send")) { Text(if(ui.busy) "Выполняется…" else "Отправить шаг") }
                }
              }
            } } }
          }
          if (run?.steps?.isNotEmpty()==true && state.catalog!=null) item {
            var timeline by rememberSaveable(s) { mutableStateOf(false) }
            TextButton(onClick={timeline=!timeline}) { Text("Пройденные шаги") }
            if(timeline) Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
              run.steps.forEach { step ->
                val original=state.catalog!!.steps[step.step_id-1]
                var expanded by rememberSaveable(s,step.step_id) { mutableStateOf(false) }
                TextButton(onClick={expanded=!expanded}) { Text("Шаг ${step.step_id} · ${original.title} · ${step.target}") }
                if(expanded) Text(original.text)
              }
            }
          }
          val latest=run?.latest?.get(if(s=="branches" && run.checkpoint!=null) ui.branch else "root")
          if (latest!=null) item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) { Text("Последний ответ Agent",style=MaterialTheme.typography.titleMedium); Text(latest) } } }
          if (run?.steps?.size==8) {
            listOf("A","B").forEach { v -> item {
              Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                var showQuestion by rememberSaveable(s,v) { mutableStateOf(false) }
                TextButton(onClick={showQuestion=!showQuestion}) { Text("Вопрос оценки $v") }
                if(showQuestion) Text(state.catalog?.questions?.get(v).orEmpty())
                Button(onClick={viewModel.evaluate(v)},enabled=!ui.busy && !ui.recovery && v !in ui.evaluations,modifier=Modifier.testTag("evaluate_$v")) { Text(if(v in ui.evaluations) "Проверяется ТЗ $v…" else "Проверить ТЗ $v") }
                val output=run.outputs.firstOrNull { it.variant==v }
                Text("ТЗ $v: ${output?.quality.label()}")
                ui.evaluationErrors[v]?.let { Text(it,color=MaterialTheme.colorScheme.error) }
                if (output!=null) {
                  var expanded by rememberSaveable(s,v,output.attempt_id) { mutableStateOf(false) }
                  TextButton(onClick={expanded=!expanded}) { Text("Результат ТЗ $v") }
                  if(expanded) Text(output.reply ?: "Ответ недоступен")
                }
              } }
            } }
          }
          item { Button(onClick={page="dashboard"},modifier=Modifier.testTag("strategies_dashboard")) { Text("Сравнить стратегии") } }
          item { TextButton(onClick=viewModel::reset,enabled=!ui.busy && ui.evaluations.isEmpty()) { Text(if(s=="branches") "Сбросить весь эксперимент с ветками" else "Сбросить этот run") } }
        }
      }
    }
  }
}

@Composable
private fun StateCard(s: String,ui: StrategyUi,vm: ContextStrategiesLabViewModel,inspector: ()->Unit) {
  val run=ui.run; val total=run?.counts?.values?.sum() ?: 0
  Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
    Text(strategyLabel(s),style=MaterialTheme.typography.titleLarge)
    when(s) {
      "window" -> {
        Text("N=6 · активных ${minOf(total,6)} · вне окна ${maxOf(total-6,0)}")
        Text((if(total>6) "old · old · " else "") + List(minOf(total,6)) { if(it%2==0) "[u]" else "[a]" }.joinToString(""))
        Text("Сохранённый audit не доступен модели вне окна.")
      }
      "facts" -> {
        Text("Фактов: ${run?.facts?.count { it.state=="set" } ?: 0} · raw tail=6")
        run?.facts?.filter { it.state=="set" }?.take(4)?.forEach { Text("${it.scope}.${it.key} → ${it.value?.content}") }
        TextButton(onClick=inspector) { Text("Показать факты") }
      }
      else -> {
        Text("Общий prefix: ${run?.counts?.get("root") ?: 0} сообщений")
        Text(if(run?.checkpoint!=null) "checkpoint → A / B" else "Checkpoint ещё не создан")
        Text("A: ${run?.counts?.get("A") ?: 0} · B: ${run?.counts?.get("B") ?: 0}")
        if(run?.checkpoint!=null) Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
          listOf("A","B").forEach { v -> FilterChip(selected=ui.branch==v,onClick={vm.branch(v)},label={Text("Ветка $v")},modifier=Modifier.testTag("branch_$v")) }
        }
        if(run?.steps?.size==6 && run.checkpoint==null) Button(onClick=vm::checkpoint,enabled=!ui.busy && !ui.recovery) { Text("Создать checkpoint") }
      }
    }
    Text("Контекст последнего запроса: ${ui.lastTokens?.toString() ?: "не измерен"} tokens")
    listOf("A","B").forEach { v -> Text("Сохранность $v: ${run?.outputs?.firstOrNull { it.variant==v }?.retention.label()}") }
  } }
}

@Composable
private fun DashboardCard(s: String,ui: StrategyUi) {
  val response=totals(ui.receipts.values,false); val maintenance=totals(ui.receipts.values,true)
  val complete=ui.coverage && response.complete && maintenance.complete
  Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
    Text(strategyLabel(s),style=MaterialTheme.typography.titleLarge)
    listOf("A","B").forEach { v ->
      val out=ui.run?.outputs?.firstOrNull { it.variant==v }
      Text("ТЗ $v: ${out?.quality.label()}")
      out?.quality?.score?.let { score -> LinearProgressIndicator(progress={score/11f},modifier=Modifier.fillMaxWidth()) }
    }
    listOf("A","B").forEach { v -> Text("Сохранность $v: ${ui.run?.outputs?.firstOrNull { it.variant==v }?.retention.label()}") }
    Text("Ответы input / output: ${response.input} / ${response.output}${if(!complete) " · известно частично" else ""}")
    Text("Обслуживание input / output: ${maintenance.input} / ${maintenance.output}${if(s=="facts" && !complete) " · известно частично" else ""}")
    Text("Всего известных tokens: ${response.total+maintenance.total}")
    Text(if(complete) "Покрытие: полное для наблюдённых операций" else "Покрытие: неполное / неизвестно")
    if(ui.unknownAttempts.isNotEmpty()) Text("Неизвестных исходов: ${ui.unknownAttempts.size}")
    Text("Обычные действия: ${ui.run?.steps?.size ?: 0}/8 Sends + ${ui.run?.outputs?.size ?: 0}/2 оценки")
    Text(if(s!="branches") "Управление памятью: 0 действий" else "Управление: checkpoint ${if(ui.run?.checkpoint!=null) 1 else 0}; переключений ${ui.switches?.toString() ?: "неизвестно"}")
    if(s=="branches") Text("Изоляция веток: " + when { ui.run?.outputs.orEmpty().any { it.isolation==false } -> "нарушено"; ui.run?.outputs?.size==2 && ui.run.outputs.all { it.isolation==true } -> "выполнено"; else -> "ещё не проверена" })
    Text(when(s) { "window" -> "Простая стратегия для локального недавнего контекста."; "facts" -> "Удобна для устойчивых требований и договорённостей."; else -> "Удобна для независимых альтернатив." })
  } }
}
