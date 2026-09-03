package com.example.responsecontrollab.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.example.responsecontrollab.ui.main.ResponseControlScreen
import com.example.responsecontrollab.ui.main.ResponseControlViewModel
import com.example.responsecontrollab.ui.reasoning.ReasoningLabScreen
import com.example.responsecontrollab.ui.reasoning.ReasoningLabViewModel
import com.example.responsecontrollab.ui.temperature.TemperatureLabScreen
import com.example.responsecontrollab.ui.temperature.TemperatureLabViewModel

enum class AppDestination(val label: String, val shortLabel: String) {
  RESPONSE_CONTROL("Управление ответом", "02"),
  REASONING_LAB("Лаборатория рассуждений", "03"),
  TEMPERATURE_LAB("Лаборатория температуры", "04"),
}

@Composable
fun AppRoot(
  responseControlViewModel: ResponseControlViewModel,
  reasoningLabViewModel: ReasoningLabViewModel,
  temperatureLabViewModel: TemperatureLabViewModel,
) {
  var destination by rememberSaveable { mutableStateOf(AppDestination.RESPONSE_CONTROL) }
  Scaffold(
    bottomBar = {
      NavigationBar {
        AppDestination.entries.forEach { item ->
          NavigationBarItem(
            selected = destination == item,
            onClick = { destination = item },
            icon = { Text(item.shortLabel) },
            label = { Text(item.label) },
          )
        }
      }
    }
  ) { innerPadding ->
    Box(Modifier.padding(innerPadding)) {
      when (destination) {
        AppDestination.RESPONSE_CONTROL -> ResponseControlScreen(responseControlViewModel)
        AppDestination.REASONING_LAB -> ReasoningLabScreen(reasoningLabViewModel)
        AppDestination.TEMPERATURE_LAB -> TemperatureLabScreen(temperatureLabViewModel)
      }
    }
  }
}
