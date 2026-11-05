package de.omafon.companion.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import de.omafon.companion.AppContainer
import de.omafon.companion.OmafonApp
import de.omafon.companion.data.ApiException

/** Zustand eines Ladevorgangs für die Oberfläche. */
data class Loadable<T>(
    val data: T? = null,
    val loading: Boolean = false,
    val error: String? = null,
    val unauthorized: Boolean = false,
)

fun Throwable.userMessage(): String = when (this) {
    is ApiException -> message ?: "Fehler"
    else -> message ?: javaClass.simpleName
}

fun Throwable.isUnauthorized() = this is ApiException && unauthorized

@Composable
fun container(): AppContainer = (LocalContext.current.applicationContext as OmafonApp).container

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BackTopBar(title: String, onBack: () -> Unit, actions: @Composable () -> Unit = {}) {
    TopAppBar(
        title = { Text(title) },
        navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück") }
        },
        actions = { actions() },
    )
}

@Composable
fun CenteredProgress(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
}

/** Fehlerkarte mit "Nochmal"; bei abgelaufener Kopplung "Neu koppeln". */
@Composable
fun ErrorPanel(message: String, onRetry: () -> Unit, modifier: Modifier = Modifier,
               unauthorized: Boolean = false, onRepair: (() -> Unit)? = null) {
    Column(
        modifier.fillMaxWidth().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(Icons.Outlined.ErrorOutline, null, Modifier.size(48.dp), tint = MaterialTheme.colorScheme.error)
        Text(message, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyLarge)
        if (unauthorized && onRepair != null) {
            Button(onClick = onRepair) { Text("Neu koppeln") }
        } else {
            Button(onClick = onRetry) { Text("Nochmal versuchen") }
        }
    }
}

@Composable
fun SectionCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { content() }
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier.padding(start = 4.dp, top = 16.dp, bottom = 4.dp),
        style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
}

@Composable
fun LabeledValue(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.size(8.dp))
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
