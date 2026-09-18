package com.example.responsecontrollab

import com.example.responsecontrollab.ui.chat.ChatViewModel
import com.example.responsecontrollab.ui.token.TokenLabViewModel
import com.example.responsecontrollab.ui.compression.CompressionLabViewModel
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.AppRoot
import com.example.responsecontrollab.ui.benchmark.ModelBenchmarkViewModel
import com.example.responsecontrollab.ui.main.ResponseControlViewModel
import com.example.responsecontrollab.ui.reasoning.ReasoningLabViewModel
import com.example.responsecontrollab.ui.temperature.TemperatureLabViewModel

class MainActivity : ComponentActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)

    enableEdgeToEdge()
    setContent {
      val container = (application as ResponseControlApplication).container
      val viewModel: ResponseControlViewModel =
        viewModel(factory = ResponseControlViewModel.factory(container.responseRepository))
      val reasoningLabViewModel: ReasoningLabViewModel =
        viewModel(factory = ReasoningLabViewModel.factory(container.reasoningLabRepository))
      val temperatureLabViewModel: TemperatureLabViewModel =
        viewModel(factory = TemperatureLabViewModel.factory(container.temperatureLabRepository))
      val modelBenchmarkViewModel: ModelBenchmarkViewModel =
        viewModel(factory = ModelBenchmarkViewModel.factory(container.modelBenchmarkRepository))
      val chatViewModel: ChatViewModel = viewModel(key = ChatViewModel.DAY_06_KEY, factory = ChatViewModel.factory(container.chatRepository))
      val persistentChatViewModel: ChatViewModel = viewModel(key = ChatViewModel.DAY_07_KEY,
        factory = ChatViewModel.factory(container.chatRepository, container.currentSessionStore))
      val tokenLabViewModel: TokenLabViewModel = viewModel(key = TokenLabViewModel.KEY,
        factory = TokenLabViewModel.factory(container.tokenLabRepository, container.tokenSessionStore))
      val compressionLabViewModel: CompressionLabViewModel = viewModel(key = CompressionLabViewModel.KEY,
        factory = CompressionLabViewModel.factory(container.compressionLabRepository, container.compressionSessionStore))
      val strategiesViewModel: com.example.responsecontrollab.ui.strategies.ContextStrategiesLabViewModel = viewModel(key="day10", factory=com.example.responsecontrollab.ui.strategies.ContextStrategiesLabViewModel.factory(container.contextStrategiesRepository,container.strategyPreferences))
      val personalizationViewModel: com.example.responsecontrollab.ui.profile.PersonalizationViewModel = viewModel(key="day12", factory=com.example.responsecontrollab.ui.profile.PersonalizationViewModel.factory(container.personalizationRepository))
      val taskStateViewModel: com.example.responsecontrollab.ui.taskstate.TaskStateViewModel = viewModel(key="day13", factory=com.example.responsecontrollab.ui.taskstate.TaskStateViewModel.factory(container.taskStateRepository))
      val invariantsViewModel: com.example.responsecontrollab.ui.invariants.InvariantsViewModel = viewModel(key="day14", factory=com.example.responsecontrollab.ui.invariants.InvariantsViewModel.factory(container.invariantsRepository))
      val playgroundViewModel: com.example.responsecontrollab.ui.playground.PlaygroundViewModel = viewModel(key="day15", factory=com.example.responsecontrollab.ui.playground.PlaygroundViewModel.factory(container.playgroundRepository))
      ResponseControlLabTheme {
        val memoryViewModel: com.example.responsecontrollab.ui.memory.MemoryLayersViewModel = viewModel(key="day11", factory=com.example.responsecontrollab.ui.memory.MemoryLayersViewModel.factory(container.memoryLayersRepository))
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
          AppRoot(
            playgroundViewModel = playgroundViewModel,
            invariantsViewModel = invariantsViewModel,
            taskStateViewModel = taskStateViewModel,
            personalizationViewModel = personalizationViewModel,
            memoryLayersViewModel = memoryViewModel,
            contextStrategiesViewModel = strategiesViewModel,
            compressionLabViewModel = compressionLabViewModel,
            tokenLabViewModel = tokenLabViewModel,
            chatViewModel = chatViewModel,
            persistentChatViewModel = persistentChatViewModel,
            responseControlViewModel = viewModel,
            reasoningLabViewModel = reasoningLabViewModel,
            temperatureLabViewModel = temperatureLabViewModel,
            modelBenchmarkViewModel = modelBenchmarkViewModel,
          )
        }
      }
    }
  }
}
