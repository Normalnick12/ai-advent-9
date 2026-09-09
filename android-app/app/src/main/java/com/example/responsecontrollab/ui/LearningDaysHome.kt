package com.example.responsecontrollab.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.R

enum class LearningDay(
  val number: String,
  val destination: AppDestination,
  @param:StringRes val title: Int,
  @param:StringRes val description: Int,
) {
  RESPONSE_CONTROL("02", AppDestination.RESPONSE_CONTROL, R.string.day_02_title, R.string.day_02_description),
  REASONING("03", AppDestination.REASONING_LAB, R.string.day_03_title, R.string.day_03_description),
  TEMPERATURE("04", AppDestination.TEMPERATURE_LAB, R.string.day_04_title, R.string.day_04_description),
  MODEL_BENCHMARK("05", AppDestination.MODEL_BENCHMARK, R.string.day_05_title, R.string.day_05_description),
  FIRST_AGENT("06", AppDestination.FIRST_AGENT, R.string.day_06_title, R.string.day_06_description),
  CONTEXT_PERSISTENCE("07", AppDestination.CONTEXT_PERSISTENCE, R.string.day_07_title, R.string.day_07_description),
  TOKEN_LAB("08", AppDestination.TOKEN_LAB, R.string.day_08_title, R.string.day_08_description),

}

@Composable
fun LearningDaysHome(onOpenDay: (AppDestination) -> Unit) {
  Scaffold(
    contentWindowInsets = WindowInsets.safeDrawing,
    topBar = {
      HeaderSurface {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
          Text(
            stringResource(R.string.learning_days_title),
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
          )
          Text(
            stringResource(R.string.choose_learning_day),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
          )
        }
      }
    },
  ) { innerPadding ->
    val direction = LocalLayoutDirection.current
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
      LazyColumn(
        modifier = Modifier.widthIn(max = 640.dp).fillMaxSize()
          .consumeWindowInsets(innerPadding).testTag("days_catalog"),
        contentPadding = PaddingValues(
          start = innerPadding.calculateLeftPadding(direction) + 16.dp,
          end = innerPadding.calculateRightPadding(direction) + 16.dp,
          top = innerPadding.calculateTopPadding() + 16.dp,
          bottom = innerPadding.calculateBottomPadding() + 16.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(12.dp),
      ) {
        items(LearningDay.entries, key = { it.destination.name }) { day ->
          Card(
            onClick = { onOpenDay(day.destination) },
            modifier = Modifier.fillMaxWidth().testTag("day_${day.number}"),
          ) {
            Row(
              Modifier.padding(16.dp),
              verticalAlignment = Alignment.CenterVertically,
              horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
              Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                  stringResource(R.string.day_number, day.number),
                  style = MaterialTheme.typography.labelLarge,
                  color = MaterialTheme.colorScheme.primary,
                )
                Text(stringResource(day.title), style = MaterialTheme.typography.titleLarge)
                Text(
                  stringResource(day.description),
                  style = MaterialTheme.typography.bodyMedium,
                  color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
              }
              Icon(
                painterResource(R.drawable.ic_arrow_forward),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
              )
            }
          }
        }
      }
    }
  }
}

@Composable
fun LearningDayTopBar(day: LearningDay, onBack: () -> Unit) {
  HeaderSurface {
    Row(
      Modifier.fillMaxWidth().padding(start = 4.dp, end = 16.dp, top = 8.dp, bottom = 8.dp),
      verticalAlignment = Alignment.CenterVertically,
    ) {
      IconButton(onClick = onBack) {
        Icon(painterResource(R.drawable.ic_arrow_back), stringResource(R.string.back_to_days))
      }
      Column(Modifier.weight(1f).padding(start = 4.dp).semantics { heading() }) {
        Text(
          stringResource(R.string.day_number, day.number),
          style = MaterialTheme.typography.labelMedium,
          color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(stringResource(day.title), style = MaterialTheme.typography.titleLarge)
      }
    }
  }
}

@Composable
private fun HeaderSurface(content: @Composable () -> Unit) {
  Surface(color = MaterialTheme.colorScheme.surface) {
    Box(
      Modifier.fillMaxWidth().windowInsetsPadding(
        WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)
      )
    ) { content() }
  }
}
