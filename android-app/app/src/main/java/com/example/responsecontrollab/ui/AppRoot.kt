package com.example.responsecontrollab.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import com.example.responsecontrollab.ui.main.ResponseControlScreen
import com.example.responsecontrollab.ui.main.ResponseControlViewModel
import com.example.responsecontrollab.ui.reasoning.ReasoningLabScreen
import com.example.responsecontrollab.ui.reasoning.ReasoningLabViewModel
import com.example.responsecontrollab.ui.temperature.TemperatureLabScreen
import com.example.responsecontrollab.ui.temperature.TemperatureLabViewModel

enum class AppDestination { HOME, RESPONSE_CONTROL, REASONING_LAB, TEMPERATURE_LAB }

@Composable
fun AppRoot(
  responseControlViewModel: ResponseControlViewModel,
  reasoningLabViewModel: ReasoningLabViewModel,
  temperatureLabViewModel: TemperatureLabViewModel,
) {
  var destination by rememberSaveable { mutableStateOf(AppDestination.HOME) }
  val screenStates = rememberSaveableStateHolder()
  val onBack = { destination = AppDestination.HOME }
  BackHandler(enabled = destination != AppDestination.HOME, onBack = onBack)

  screenStates.SaveableStateProvider(destination.name) {
    when (destination) {
      AppDestination.HOME -> LearningDaysHome(onOpenDay = { destination = it })
      AppDestination.RESPONSE_CONTROL -> ResponseControlScreen(responseControlViewModel, onBack)
      AppDestination.REASONING_LAB -> ReasoningLabScreen(reasoningLabViewModel, onBack)
      AppDestination.TEMPERATURE_LAB -> TemperatureLabScreen(temperatureLabViewModel, onBack)
    }
  }
}
