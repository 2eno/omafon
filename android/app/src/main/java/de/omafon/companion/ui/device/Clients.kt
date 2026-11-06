package de.omafon.companion.ui.device

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.LinkOff
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.PairedClient
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.CenteredProgress
import de.omafon.companion.ui.ErrorPanel

/** "2026-11-05T15:00:00" -> "5.11.2026, 15:00" (unlesbar: wie geliefert). */
fun germanDate(iso: String, withTime: Boolean = true): String = runCatching {
    val t = java.time.LocalDateTime.parse(iso.take(19))
    val d = "${t.dayOfMonth}.${t.monthValue}.${t.year}"
    if (withTime) d + ", %02d:%02d".format(t.hour, t.minute) else d
}.getOrDefault(iso)

class ClientsViewModel(app: Application, id: String) : DeviceViewModel<List<PairedClient>>(app, id) {
    override suspend fun fetch(api: OmafonApi) = api.clients().clients

    fun unpair(c: PairedClient, onSelf: () -> Unit) = action { api ->
        api.removeClient(c.id)
        if (c.isThis) forget(onSelf) else {
            say("${c.name} ist nicht mehr gekoppelt.")
            refresh(silent = true)
        }
    }
}

@Composable
fun ClientsScreen(deviceId: String, onBack: () -> Unit, onUnpairedSelf: () -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: ClientsViewModel = viewModel(key = "clients-$deviceId") { ClientsViewModel(app, deviceId) }
    val state by vm.state.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    var confirm by remember { mutableStateOf<PairedClient?>(null) }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }

    Scaffold(topBar = { BackTopBar("Gekoppelte Apps", onBack) }, snackbarHost = { SnackbarHost(snack) }) { pad ->
        val list = state.data
        when {
            list == null && state.loading -> CenteredProgress(Modifier.padding(pad))
            list == null -> ErrorPanel(state.error ?: "Fehler", { vm.refresh() }, Modifier.padding(pad))
            else -> LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp, pad.calculateTopPadding() + 8.dp, 16.dp, pad.calculateBottomPadding() + 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                item {
                    Text("Diese Handys dürfen das Omafon verwalten. Verlorenes Handy? Hier entkoppeln.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                items(list, key = { it.id }) { c ->
                    Card(Modifier.fillMaxWidth()) {
                        ListItem(
                            leadingContent = { Icon(Icons.Outlined.PhoneAndroid, null) },
                            headlineContent = { Text(if (c.isThis) "${c.name} (dieses Handy)" else c.name) },
                            supportingContent = {
                                Text("Gekoppelt ${germanDate(c.created, withTime = false)}" +
                                    if (c.lastSeen.isNotBlank()) " · zuletzt ${germanDate(c.lastSeen)}" else "")
                            },
                            trailingContent = {
                                IconButton(onClick = { confirm = c }) { Icon(Icons.Outlined.LinkOff, "Entkoppeln") }
                            },
                        )
                    }
                }
            }
        }
    }

    confirm?.let { c ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("${c.name} entkoppeln?") },
            text = { Text(if (c.isThis) "Diese App verliert den Zugriff. Zum Wiederverbinden neu koppeln."
                else "Das Handy kann das Omafon danach nicht mehr verwalten.") },
            confirmButton = { TextButton(onClick = { confirm = null; vm.unpair(c, onUnpairedSelf) }) { Text("Entkoppeln") } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Abbrechen") } },
        )
    }
}
