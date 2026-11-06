package de.omafon.companion.ui.device

import android.app.Application
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.outlined.Battery5Bar
import androidx.compose.material.icons.outlined.BatteryChargingFull
import androidx.compose.material.icons.outlined.Contacts
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.automirrored.outlined.PhoneMissed
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.SignalWifi4Bar
import androidx.compose.material.icons.outlined.SignalWifiOff
import androidx.compose.material.icons.outlined.SystemUpdate
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.DeviceStatus
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.stateLabel
import de.omafon.companion.data.variantLabel
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.CenteredProgress
import de.omafon.companion.ui.ErrorPanel
import de.omafon.companion.ui.LabeledValue
import de.omafon.companion.ui.SectionCard
import kotlinx.coroutines.delay

class DashboardViewModel(app: Application, id: String) : DeviceViewModel<DeviceStatus>(app, id) {
    override suspend fun fetch(api: OmafonApi) = api.status()

    fun speak(text: String) = action { api ->
        api.speak(text)
        say("Das Omafon sagt es jetzt an.")
    }

    fun restart() = action { api ->
        api.restart()
        say("Das Omafon startet neu, sobald es in Ruhe ist.")
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun DashboardScreen(
    deviceId: String,
    onBack: () -> Unit,
    onOpen: (String) -> Unit,
    onRepair: (host: String, port: Int, name: String) -> Unit,
    onRemoved: () -> Unit,
) {
    val app = LocalContext.current.applicationContext as Application
    val vm: DashboardViewModel = viewModel(key = "dash-$deviceId") { DashboardViewModel(app, deviceId) }
    val state by vm.state.collectAsStateWithLifecycle()
    val device by vm.device.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    var menu by remember { mutableStateOf(false) }
    var confirmForget by remember { mutableStateOf(false) }
    var confirmRestart by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(lifecycle) {                 // alle 10 s still aktualisieren – nur sichtbar
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) { delay(10_000); vm.refresh(silent = true) }
        }
    }

    Scaffold(
        topBar = {
            BackTopBar(device?.name ?: "Omafon", onBack) {
                IconButton(onClick = { menu = true }) { Icon(Icons.Outlined.MoreVert, "Mehr") }
                DropdownMenu(menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Neu starten") }, onClick = { menu = false; confirmRestart = true },
                        leadingIcon = { Icon(Icons.Outlined.RestartAlt, null) })
                    DropdownMenuItem(text = { Text("Aus der App entfernen") },
                        onClick = { menu = false; confirmForget = true })
                }
            }
        },
        snackbarHost = { SnackbarHost(snack) },
    ) { pad ->
        val s = state.data
        PullToRefreshBox(isRefreshing = state.loading && s != null, onRefresh = { vm.refresh() },
            modifier = Modifier.fillMaxSize().padding(pad)) {
            when {
                s == null && state.loading -> CenteredProgress()
                s == null -> ErrorPanel(
                    state.error ?: "Fehler", onRetry = { vm.refresh() }, unauthorized = state.unauthorized,
                    onRepair = device?.let { d -> { onRepair(d.host, d.port, d.name) } },
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                )
                else -> Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    StatusTiles(s)
                    SectionCard {
                        LabeledValue("Zustand", stateLabel(s.state))
                        LabeledValue("Variante", variantLabel(s.variant))
                        LabeledValue("Version", s.version)
                        LabeledValue("Läuft seit", uptime(s.uptimeS))
                        if (s.restartPending) {
                            Text("Neustart wartet, bis das Telefon in Ruhe ist.",
                                color = MaterialTheme.colorScheme.tertiary)
                        }
                        if (!s.timeKnown) {
                            Text("Uhrzeit am Omafon noch unbekannt (kein WLAN/Netz seit dem Einschalten). " +
                                "Die Info-Taste sagt sie erst an, wenn sie stimmt.",
                                color = MaterialTheme.colorScheme.error)
                        }
                    }
                    SpeakCard(enabled = s.state == "idle", onSpeak = vm::speak)
                    ElevatedCard(Modifier.fillMaxWidth()) {
                        NavRow(Icons.Outlined.Settings, "Einstellungen", "Lautstärke, Tasten, Notruf …") { onOpen("settings") }
                        NavRow(Icons.Outlined.Contacts, "Kontakte", "Kurzwahl, Sprachwahl, Notrufkette") { onOpen("contacts") }
                        NavRow(Icons.Outlined.SystemUpdate, "Updates",
                            if (s.update?.updateAvailable == true) "Neue Version ${s.update.available?.version}" else "Version ${s.version}",
                            badge = s.update?.updateAvailable == true) { onOpen("update") }
                        NavRow(Icons.Outlined.Devices, "Gekoppelte Apps", "Wer das Omafon verwalten darf") { onOpen("clients") }
                    }
                }
            }
        }
    }

    if (confirmForget) {
        AlertDialog(
            onDismissRequest = { confirmForget = false },
            title = { Text("Aus der App entfernen?") },
            text = { Text("Das Omafon selbst bleibt unverändert. Zum Wiederverbinden neu koppeln.") },
            confirmButton = { TextButton(onClick = { confirmForget = false; vm.forget(onRemoved) }) { Text("Entfernen") } },
            dismissButton = { TextButton(onClick = { confirmForget = false }) { Text("Abbrechen") } },
        )
    }
    if (confirmRestart) {
        AlertDialog(
            onDismissRequest = { confirmRestart = false },
            title = { Text("Omafon neu starten?") },
            text = { Text("Das Telefon sagt den Neustart an und ist etwa eine halbe Minute nicht erreichbar. " +
                "Ein laufendes Gespräch wird nicht unterbrochen.") },
            confirmButton = { TextButton(onClick = { confirmRestart = false; vm.restart() }) { Text("Neu starten") } },
            dismissButton = { TextButton(onClick = { confirmRestart = false }) { Text("Abbrechen") } },
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun StatusTiles(s: DeviceStatus) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
        maxItemsInEachRow = 2) {
        val mod = Modifier.weight(1f)
        Tile(mod, if (s.charging) Icons.Outlined.BatteryChargingFull else Icons.Outlined.Battery5Bar,
            s.battery?.let { "$it %" } ?: "–", if (s.charging) "lädt" else "Akku",
            warn = (s.battery ?: 100) < 20 && !s.charging)
        Tile(mod, if (s.online) Icons.Outlined.SignalWifi4Bar else Icons.Outlined.SignalWifiOff,
            if (s.online) "Verbunden" else "Offline", s.connection.ifBlank { "Netz" }, warn = !s.online)
        Tile(mod, Icons.Outlined.Mail, s.unread.toString(), "ungelesen")
        Tile(mod, Icons.AutoMirrored.Outlined.PhoneMissed, s.missed.toString(), "verpasst", warn = s.missed > 0)
    }
}

@Composable
private fun Tile(modifier: Modifier, icon: ImageVector, value: String, label: String, warn: Boolean = false) {
    val color = if (warn) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer
    ElevatedCard(modifier, colors = androidx.compose.material3.CardDefaults.elevatedCardColors(containerColor = color)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Icon(icon, null)
            Text(value, style = MaterialTheme.typography.headlineSmall)
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun SpeakCard(enabled: Boolean, onSpeak: (String) -> Unit) {
    var text by rememberSaveable { mutableStateOf("") }
    SectionCard {
        Text("Testansage", style = MaterialTheme.typography.titleMedium)
        Text("Das Omafon spricht den Text – gut zum Prüfen von Lautstärke und Stimme.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(text, { text = it.take(200) }, Modifier.weight(1f), singleLine = true,
                placeholder = { Text("Hallo Oma, hier ist Peter!") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { if (text.isNotBlank()) onSpeak(text) }))
            IconButton(onClick = { onSpeak(text) }, enabled = enabled && text.isNotBlank()) {
                Icon(Icons.AutoMirrored.Filled.Send, "Ansagen")
            }
        }
        if (!enabled) Text("Geht nur, wenn das Telefon in Ruhe ist.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun NavRow(icon: ImageVector, title: String, subtitle: String, badge: Boolean = false, onClick: () -> Unit) {
    ListItem(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        leadingContent = {
            BadgedBox(badge = { if (badge) Badge() }) { Icon(icon, null) }
        },
        headlineContent = { Text(title) },
        supportingContent = { Text(subtitle) },
        trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
        colors = androidx.compose.material3.ListItemDefaults.colors(
            containerColor = androidx.compose.ui.graphics.Color.Transparent),
    )
}

private fun uptime(s: Long): String = when {
    s < 3600 -> "${s / 60} min"
    s < 86400 -> "${s / 3600} h ${s % 3600 / 60} min"
    s < 2 * 86400 -> "1 Tag"
    else -> "${s / 86400} Tagen"
}
