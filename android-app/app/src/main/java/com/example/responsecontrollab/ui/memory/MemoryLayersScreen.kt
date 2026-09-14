package com.example.responsecontrollab.ui.memory

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
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive

private val prettyJson=Json { prettyPrint=true }
private fun checksLabel(checks: Map<String,MemoryCheck>): String =
  if(checks.isEmpty() || checks.values.any { it.correct==null }) "нет измерения"
  else "${checks.values.count { it.correct==true }}/${checks.size}"

private fun nextStep(observation: MemoryObservation): String? =
  (observation.parsed?.get("next_step") as? JsonPrimitive)?.content

@Composable
private fun MemoryCard(title: String, content: @Composable ColumnScope.()->Unit) {
  Card(Modifier.fillMaxWidth()) {
    Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
      Text(title,style=MaterialTheme.typography.titleMedium)
      content()
    }
  }
}

@Composable
fun MemoryLayersScreen(viewModel: MemoryLayersViewModel,onBack: ()->Unit) {
  val ui by viewModel.uiState.collectAsState()
  LaunchedEffect(Unit) { viewModel.load() }
  var page by rememberSaveable { mutableStateOf("main") }
  val pages=rememberSaveableStateHolder()
  val back={ if(page=="main") onBack() else page="main" }
  BackHandler(onBack=back)
  val state=ui.current?.state
  val enabled=!ui.busy && !ui.recovery && ui.current?.busy!=true
  Scaffold(contentWindowInsets=WindowInsets.safeDrawing,
    topBar={ LearningDayTopBar(LearningDay.MEMORY_LAYERS,back) }) { padding ->
    pages.SaveableStateProvider(page) {
      LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).testTag("memory_scroll"),
        state=rememberLazyListState(),contentPadding=PaddingValues(16.dp),
        verticalArrangement=Arrangement.spacedBy(12.dp)) {
        if(page!="main") item { TextButton(onClick={page="main"}) { Text("Назад к памяти") } }
        if(page=="inspector") {
          item { Text("Память и контекст",style=MaterialTheme.typography.headlineSmall) }
          item { MemoryCard("Сохранено сейчас") {
            if(state==null) Text("Память ещё не создана") else {
              Text("owner: ${state.memory_owner_id}\ntask: ${state.task_id}\nsession: ${state.session_id}")
              Text("Working: ${state.working}\nLong-term: ${state.long_term}")
              state.short_term.forEach { Text("${it.position} · ${it.role}: ${it.content}") }
              Text("Неактивные задачи: ${state.inactive_tasks.size} · разговоры: ${state.inactive_sessions.size}. Сохранены, не выбраны.")
            }
          } }
          item { MemoryCard("Выбрано в контекст / исключено сейчас") {
            Text("Working: ${ui.current?.preview?.selected_working.orEmpty()}")
            Text("Long-term: ${ui.current?.preview?.selected_long_term.orEmpty()}")
            ui.current?.preview?.excluded.orEmpty().forEach { Text("${it.key}=${it.value} · исключено: ${it.reason}") }
          } }
          ui.latest?.let { obs ->
            item { MemoryCard("Снимок последнего запроса") {
              Text(if(obs.snapshot_id==state?.snapshot_id) "Текущий снимок" else "Предыдущий снимок",modifier=Modifier.testTag("memory_snapshot_label"))
              Text(obs.snapshot_id)
              Text("Сохранено тогда: Working ${obs.stored.working}; Long-term ${obs.stored.long_term}")
              Text("Выбрано тогда: Working ${obs.selection.selected_working}; Long-term ${obs.selection.selected_long_term}")
              obs.selection.excluded.forEach { Text("Исключено тогда: ${it.key}=${it.value} · ${it.reason}") }
              var sources by rememberSaveable(obs.attempt_id) { mutableStateOf(false) }
              TextButton(onClick={sources=!sources}) { Text("Источники запроса") }
              if(sources) Text(obs.selection.selected_sources.joinToString("\n"))
            } }
            item { MemoryCard("Запрос к модели") {
              var expanded by rememberSaveable(obs.attempt_id) { mutableStateOf(false) }
              TextButton(onClick={expanded=!expanded}) { Text("Показать точный запрос") }
              if(expanded) Text(prettyJson.encodeToString(kotlinx.serialization.json.JsonObject.serializer(),obs.request),modifier=Modifier.testTag("memory_request"))
            } }
            item { MemoryCard("Ответ модели") { Text(obs.reply ?: "Ответ недоступен"); obs.error?.let { Text(it) } } }
          }
        } else if(page=="dashboard") {
          item { Text("Проверки A–E",style=MaterialTheme.typography.headlineSmall) }
          for(stage in listOf("A","B","C","D","E")) item {
            val obs=ui.results[stage]
            MemoryCard("Этап $stage") {
              Text("Доступно в запросе: ${checksLabel(obs?.input_checks.orEmpty())}")
              Text("Использовано в ответе: ${checksLabel(obs?.output_checks.orEmpty())}")
              if(obs!=null) {
                Text("Снимок: ${obs.snapshot_id.take(12)}")
                obs.error?.let { Text("Причина: $it",color=MaterialTheme.colorScheme.error) }
                nextStep(obs)?.let { Text("Следующий шаг · без оценки: $it") }
                obs.input_checks.forEach { (key,c) ->
                  val output=obs.output_checks[key]
                  Text("$key: ${c.status} · input=${c.correct}; output=${output?.status ?: "нет измерения"}")
                }
              }
            }
          }
          item { Text("Это проверки пяти точных полей, не общая оценка качества. Результаты хранятся только в текущем запуске.") }
          item { TextButton(onClick=viewModel::clearObservations,enabled=enabled) { Text("Очистить только результаты проверок") } }
        } else {
          item { MemoryCard("Краткосрочная · Short-term") {
            Text("Текущий разговор · ${state?.short_term?.size?.div(2) ?: 0} завершённых ходов")
            Text("Session: ${state?.session_id?.take(8) ?: "не создана"}. Полная история. Неактивных разговоров: ${state?.inactive_sessions?.size ?: 0}")
          } }
          item { MemoryCard("Рабочая · Working") {
            if(state?.working.isNullOrEmpty()) Text("Текущая задача пока не описана")
            state?.working?.forEach { (k,v) -> Text("$k = $v") }
          } }
          item { MemoryCard("Долговременная · Long-term") {
            Text("Сведения владельца между задачами и разговорами")
            if(state?.long_term.isNullOrEmpty()) Text("Сведения владельца пока не сохранены")
            state?.long_term?.forEach { (k,v) -> Text("$k = $v") }
            ui.current?.preview?.excluded?.forEach { Text("${it.value} сохранено; переопределено Working") }
          } }
          if(ui.busy) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
          ui.error?.let { item { Text(it,color=MaterialTheme.colorScheme.error) } }
          item { TextButton(onClick=viewModel::refresh,enabled=!ui.busy) { Text("Прочитать память") } }
          if(state==null) {
            item { Button(onClick=viewModel::initialize,enabled=enabled && ui.initialized) { Text("Создать память Day 11") } }
          } else {
            val stage=ui.current?.applicable_stages?.firstOrNull()
            item { Text("Текущий этап: ${stage ?: "подготовка"}",style=MaterialTheme.typography.titleLarge) }
            if(state.short_term.isEmpty() && state.working.isEmpty() && state.long_term.isEmpty()) {
              item { MemoryCard("Short-term · исходное сообщение") {
                Text(ui.catalog?.seed.orEmpty())
                Button(onClick=viewModel::seed,enabled=enabled,modifier=Modifier.testTag("memory_seed")) { Text("Отправить исходное сообщение") }
              } }
            }
            if(state.short_term.isNotEmpty()) {
              val writes=(ui.catalog?.long_term.orEmpty().map { Triple("LONG_TERM",it.key,it.value) } +
                ui.catalog?.working.orEmpty().map { Triple("WORKING",it.key,it.value) })
              val missing=writes.firstOrNull { (layer,key,_) ->
                key !in (if(layer=="WORKING") state.working else state.long_term)
              }
              if(stage==null && missing!=null) item { MemoryCard("Явная запись памяти") {
                val (layer,key,value)=missing
                Text("$layer · $key = $value")
                Button(onClick={viewModel.write(layer,key,value)},enabled=enabled,modifier=Modifier.testTag("memory_write")) { Text("Сохранить указанное значение") }
              } }
            }
            if(stage!=null) item { MemoryCard("Проверка $stage") {
              var query by rememberSaveable { mutableStateOf(false) }
              TextButton(onClick={query=!query}) { Text("Показать вопрос проверки") }
              if(query) Text(ui.catalog?.query.orEmpty())
              Button(onClick={viewModel.verify(stage)},enabled=enabled,modifier=Modifier.testTag("memory_verify")) { Text("Проверить $stage") }
              Text("Проверка не записывает вопрос и ответ в память.")
            } }
            if(stage=="A") item { Button(onClick=viewModel::removeArchitecture,enabled=enabled) { Text("B · Удалить Working architecture") } }
            item { Text("Новый разговор сохраняет прежнюю историю inactive. Новая задача также сохраняет прежнюю Working.") }
            item { OutlinedButton(onClick={viewModel.transition("new-conversation")},enabled=enabled) { Text("Новый разговор") } }
            item { OutlinedButton(onClick={viewModel.transition("new-task")},enabled=enabled) { Text("Новая задача") } }
            item { OutlinedButton(onClick={viewModel.transition("clear-long-term")},enabled=enabled) { Text("Очистить Long-term") } }
          }
          ui.latest?.let { item { MemoryCard("Последний ответ") {
            if(it.parsed==null) Text(it.reply ?: "Ответ недоступен") else {
              it.parsed.filterKeys { key -> key!="next_step" }.forEach { (key,value) ->
                Text("$key = ${(value as? JsonPrimitive)?.content ?: value}")
              }
              nextStep(it)?.let { step -> Text("Следующий шаг · без оценки: $step") }
            }
            if(it.snapshot_id!=state?.snapshot_id) Text("Ответ относится к предыдущему снимку")
          } } }
          item { Button(onClick={page="inspector"},modifier=Modifier.testTag("memory_inspector")) { Text("Память и контекст") } }
          item { Button(onClick={page="dashboard"}) { Text("Проверки A–E") } }
        }
      }
    }
  }
}
