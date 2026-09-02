package com.example.responsecontrollab

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
import com.example.responsecontrollab.ui.main.ResponseControlViewModel
import com.example.responsecontrollab.ui.reasoning.ReasoningLabViewModel

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
      ResponseControlLabTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
          AppRoot(
            responseControlViewModel = viewModel,
            reasoningLabViewModel = reasoningLabViewModel,
          )
        }
      }
    }
  }
}
