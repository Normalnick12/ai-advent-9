package synthetic.catalog

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class CatalogUiState(
    val title: String = "",
    val loading: Boolean = false,
)

interface CatalogCoordinator {
    suspend fun titleFor(itemId: String): String
    fun openDetails(itemId: String)
}

class CatalogViewModel(
    private val coordinator: CatalogCoordinator,
) : ViewModel() {
    private val mutableUiState = MutableStateFlow(CatalogUiState())
    val uiState: StateFlow<CatalogUiState> = mutableUiState.asStateFlow()

    suspend fun load(itemId: String) {
        mutableUiState.value = CatalogUiState(loading = true)
        val title = coordinator.titleFor(itemId)
        mutableUiState.value = CatalogUiState(title = title)
    }

    fun onDetails(itemId: String) {
        coordinator.openDetails(itemId)
    }
}

@Composable
fun CatalogRoute(itemId: String, viewModel: CatalogViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(itemId, viewModel) {
        viewModel.load(itemId)
    }

    Text(if (state.loading) "Loading" else state.title)
    Button(onClick = { viewModel.onDetails(itemId) }) {
        Text("Details")
    }
}
