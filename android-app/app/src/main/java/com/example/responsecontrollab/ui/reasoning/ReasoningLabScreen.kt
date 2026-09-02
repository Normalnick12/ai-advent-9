package com.example.responsecontrollab.ui.reasoning

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.responsecontrollab.data.StrategyResultDto

private const val META_PROMPT_STRATEGY = "META_PROMPT"

@Composable
fun ReasoningLabScreen(viewModel: ReasoningLabViewModel) {
  val state by viewModel.uiState.collectAsStateWithLifecycle()
  ReasoningLabContent(state = state, onRun = viewModel::runAllStrategies)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReasoningLabContent(
  state: ReasoningLabUiState,
  onRun: () -> Unit,
) {
  val isLoading = state is ReasoningLabUiState.Loading
  Scaffold(
    modifier = Modifier.fillMaxSize(),
    topBar = { TopAppBar(title = { Text("Лаборатория рассуждений") }) },
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
      BenchmarkSummaryCard()
      Button(
        onClick = onRun,
        modifier = Modifier.fillMaxWidth(),
        enabled = !isLoading,
      ) {
        Text(if (isLoading) "Стратегии выполняются…" else "Запустить все стратегии")
      }

      when (state) {
        ReasoningLabUiState.Idle ->
          Text("Запустите эксперимент, чтобы сравнить четыре стратегии.")
        ReasoningLabUiState.Loading -> {
          LinearProgressIndicator(Modifier.fillMaxWidth())
          Text("Выполняются пять вызовов OpenAI в четырёх параллельных стратегиях.")
        }
        is ReasoningLabUiState.Error ->
          Card(
            colors =
              CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer
              )
          ) {
            Text(
              text = "Ошибка запуска: ${state.message}",
              modifier = Modifier.fillMaxWidth().padding(16.dp),
              color = MaterialTheme.colorScheme.onErrorContainer,
            )
          }
        is ReasoningLabUiState.Content -> {
          Text(
            "Результаты запуска ${state.batch.request_id}",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
          )
          state.batch.results.forEach { StrategyResultCard(it) }
        }
      }
    }
  }
}

@Composable
private fun BenchmarkSummaryCard() {
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(
      modifier = Modifier.padding(16.dp),
      verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
      Text(
        "Фиксированная задача",
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.Bold,
      )
      Text("Выбрать набор фич A–H с максимальной ценностью при лимите 15 story points.")
      Text("Ограничения: B без E; C только с F; A без D; G без H.")
      Text(
        "Эталон полного перебора: A + C + F + G, стоимость 15, ценность 29.",
        fontWeight = FontWeight.SemiBold,
      )
    }
  }
}

@Composable
private fun StrategyResultCard(result: StrategyResultDto) {
  var promptExpanded by rememberSaveable(result.strategy, result.generated_prompt) {
    mutableStateOf(false)
  }
  Card(modifier = Modifier.fillMaxWidth()) {
    Column(
      modifier = Modifier.padding(16.dp),
      verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
      Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
      ) {
        Text(
          localizedStrategyName(result.strategy),
          modifier = Modifier.weight(1f),
          style = MaterialTheme.typography.titleLarge,
          fontWeight = FontWeight.Bold,
        )
        StatusBadge(result.correct)
      }
      HorizontalDivider()

      result.solution?.let { solution ->
        Text("Выбранные фичи: ${solution.selected_features.joinToString(", ")}")
        Text("Суммарная стоимость: ${solution.total_cost}")
        Text("Суммарная ценность: ${solution.total_value}")
        SelectionContainer {
          Text("Объяснение: ${solution.explanation}")
        }
      }
      result.error?.let { error ->
        Text(
          "Ошибка стратегии: ${error.message}",
          color = MaterialTheme.colorScheme.error,
          fontWeight = FontWeight.SemiBold,
        )
      }
      if (result.verification.violations.isNotEmpty()) {
        Text(
          "Проверка: ${result.verification.violations.joinToString(" ")}",
          color = MaterialTheme.colorScheme.error,
        )
      }

      HorizontalDivider()
      Text("Задержка: ${result.latency_ms} мс")
      Text(
        "Токены: вход ${result.usage.input_tokens}, выход ${result.usage.output_tokens}, " +
          "рассуждение ${result.usage.reasoning_tokens}, всего ${result.usage.total_tokens}"
      )
      Text("Вызовов API: ${result.api_call_count}")

      if (result.strategy == META_PROMPT_STRATEGY && result.generated_prompt != null) {
        OutlinedButton(
          onClick = { promptExpanded = !promptExpanded },
          modifier = Modifier.fillMaxWidth(),
        ) {
          Text(
            if (promptExpanded) {
              "Скрыть сгенерированный промпт"
            } else {
              "Показать сгенерированный промпт"
            }
          )
        }
        if (promptExpanded) {
          Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = MaterialTheme.shapes.small,
          ) {
            SelectionContainer {
              Text(
                text = result.generated_prompt,
                modifier =
                  Modifier.padding(12.dp)
                    .heightIn(max = 220.dp)
                    .verticalScroll(rememberScrollState()),
                fontFamily = FontFamily.Monospace,
              )
            }
          }
        }
      }
    }
  }
}

private fun localizedStrategyName(strategy: String): String =
  when (strategy) {
    "DIRECT" -> "Прямой ответ"
    "STEP_BY_STEP" -> "Пошаговое решение"
    "META_PROMPT" -> "Мета-промпт"
    "EXPERT_PANEL" -> "Группа экспертов"
    else -> "Неизвестная стратегия"
  }

@Composable
private fun StatusBadge(correct: Boolean) {
  Surface(
    color =
      if (correct) {
        MaterialTheme.colorScheme.primaryContainer
      } else {
        MaterialTheme.colorScheme.errorContainer
      },
    contentColor =
      if (correct) {
        MaterialTheme.colorScheme.onPrimaryContainer
      } else {
        MaterialTheme.colorScheme.onErrorContainer
      },
    shape = MaterialTheme.shapes.small,
  ) {
    Text(
      text = if (correct) "Правильно" else "Неправильно",
      modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
      fontWeight = FontWeight.Bold,
    )
  }
}
