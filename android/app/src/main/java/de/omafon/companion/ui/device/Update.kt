package de.omafon.companion.ui.device

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.NewReleases
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.ApiException
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.UpdateInfo
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.CenteredProgress
import de.omafon.companion.ui.ErrorPanel
import de.omafon.companion.ui.LabeledValue
import de.omafon.companion.ui.SectionCard
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

/** Was die App gerade über den Ablauf weiß (über die Phase des Omafon hinaus). */
enum class UpdateStep { NONE, WORKING, RESTARTING, DONE }

/** Text zur Phase des Omafon (omafon/update.py). */
fun phaseLabel(phase: String) = when (phase) {
    "checking" -> "Sucht nach Updates …"
    "downloading" -> "Lädt herunter …"
    "verifying" -> "Prüft Signatur und Paket …"
    "installing" -> "Installiert …"
    "restarting" -> "Startet neu …"
    "error" -> "Fehler"
    else -> "Bereit"
}

class UpdateViewModel(app: Application, id: String) : DeviceViewModel<UpdateInfo>(app, id) {
    val step = MutableStateFlow(UpdateStep.NONE)
    val checking = MutableStateFlow(false)
    private var poll: Job? = null
    private var target: String? = null

    override suspend fun fetch(api: OmafonApi) = api.update()

    fun check() = action(checking) { api ->
        val info = api.updateCheck()
        _state.value = _state.value.copy(data = info, error = null)
        say(if (info.updateAvailable) "Version ${info.available?.version} ist verfügbar."
            else "Das Omafon ist auf dem neuesten Stand.")
    }

    fun install() {
        target = state.value.data?.available?.version
        action { api ->
            _state.value = _state.value.copy(data = api.updateInstall())
            step.value = UpdateStep.WORKING
            follow()
        }
    }

    fun rollback() = action { api ->
        _state.value = _state.value.copy(data = api.updateRollback())
        target = null
        step.value = UpdateStep.RESTARTING
        follow()
    }

    /**
     * Fortschritt verfolgen: erst die Phasen auf dem Omafon, dann den Neustart
     * (nicht erreichbar) bis es wieder antwortet.
     */
    private fun follow() {
        poll?.cancel()
        poll = viewModelScope.launch {
            var sawOffline = false
            repeat(150) {                       // höchstens ~5 Minuten
                delay(2_000)
                val info = try {
                    api().update()
                } catch (e: ApiException) {
                    if (!e.offline) { say(e.message ?: "Fehler"); step.value = UpdateStep.NONE; return@launch }
                    sawOffline = true
                    step.value = UpdateStep.RESTARTING
                    null
                }
                if (info != null) {
                    _state.value = _state.value.copy(data = info)
                    val running = target == null || info.current == target
                    when {
                        info.phase == "error" -> { step.value = UpdateStep.NONE; return@launch }
                        sawOffline && running -> { step.value = UpdateStep.DONE; return@launch }
                        info.phase == "restarting" -> step.value = UpdateStep.RESTARTING
                    }
                }
            }
            step.value = UpdateStep.NONE
            say("Das Omafon meldet sich nicht zurück. Bitte am Gerät nachsehen.")
        }
    }
}

@Composable
fun UpdateScreen(deviceId: String, onBack: () -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: UpdateViewModel = viewModel(key = "update-$deviceId") { UpdateViewModel(app, deviceId) }
    val state by vm.state.collectAsStateWithLifecycle()
    val step by vm.step.collectAsStateWithLifecycle()
    val checking by vm.checking.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    var confirmInstall by remember { mutableStateOf(false) }
    var confirmRollback by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }

    Scaffold(topBar = { BackTopBar("Updates", onBack) }, snackbarHost = { SnackbarHost(snack) }) { pad ->
        val u = state.data
        when {
            u == null && state.loading -> CenteredProgress(Modifier.padding(pad))
            u == null -> ErrorPanel(state.error ?: "Fehler", { vm.refresh() }, Modifier.padding(pad))
            else -> Column(
                Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                SectionCard {
                    LabeledValue("Installiert", u.current)
                    if (u.previous.isNotBlank()) LabeledValue("Vorherige", if (u.previous == "@basis") "Erstinstallation" else u.previous)
                    LabeledValue("Zustand", phaseLabel(u.phase))
                }
                if (!u.configured) {
                    SectionCard {
                        Text("Kein Update-Kanal eingerichtet", style = MaterialTheme.typography.titleMedium)
                        Text("In den Einstellungen unter „Updates“ die Manifest-URL eintragen. Der öffentliche " +
                            "Schlüssel (update_public_key) muss auf dem Omafon in config.yaml stehen – er lässt " +
                            "sich absichtlich nicht über die App ändern.")
                    }
                }
                if (u.lastError.isNotBlank()) {
                    SectionCard {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Outlined.Warning, null, tint = MaterialTheme.colorScheme.error)
                            Text(u.lastError, color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
                when (step) {
                    UpdateStep.WORKING, UpdateStep.RESTARTING -> SectionCard {
                        Text(if (step == UpdateStep.RESTARTING) "Das Omafon startet neu …" else phaseLabel(u.phase),
                            style = MaterialTheme.typography.titleMedium)
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text("Das Telefon sagt den Neustart an, sobald es in Ruhe ist. Läuft die neue Version " +
                            "nicht stabil, kehrt es von selbst zur alten zurück.", style = MaterialTheme.typography.bodySmall)
                    }
                    UpdateStep.DONE -> SectionCard {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Outlined.CheckCircle, null, tint = MaterialTheme.colorScheme.primary)
                            Text("Fertig – Version ${u.current} läuft.", style = MaterialTheme.typography.titleMedium)
                        }
                    }
                    else -> {}
                }
                if (u.updateAvailable && (step == UpdateStep.NONE || step == UpdateStep.DONE)) {
                    SectionCard {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Outlined.NewReleases, null, Modifier.size(28.dp), tint = MaterialTheme.colorScheme.primary)
                            Text("Version ${u.available?.version}", style = MaterialTheme.typography.titleLarge)
                        }
                        u.available?.notes?.takeIf { it.isNotBlank() }?.let { Text(it) }
                        Button(onClick = { confirmInstall = true }, enabled = !u.busy, modifier = Modifier.fillMaxWidth()) {
                            Text("Installieren")
                        }
                    }
                }
                OutlinedButton(onClick = { vm.check() },
                    enabled = u.configured && !checking && step != UpdateStep.WORKING &&
                        step != UpdateStep.RESTARTING && !u.busy,
                    modifier = Modifier.fillMaxWidth()) {
                    Text(if (checking) "Sucht …" else "Nach Updates suchen")
                }
                if (u.canRollback && (step == UpdateStep.NONE || step == UpdateStep.DONE)) {
                    TextButton(onClick = { confirmRollback = true }, modifier = Modifier.fillMaxWidth()) {
                        Text("Zur vorherigen Version zurück")
                    }
                }
            }
        }
    }

    if (confirmInstall) {
        AlertDialog(
            onDismissRequest = { confirmInstall = false },
            title = { Text("Update installieren?") },
            text = { Text("Das Omafon lädt das Paket, prüft die Signatur und startet danach neu – aber erst, " +
                "wenn kein Gespräch läuft. Für etwa eine Minute ist es nicht erreichbar.") },
            confirmButton = { TextButton(onClick = { confirmInstall = false; vm.install() }) { Text("Installieren") } },
            dismissButton = { TextButton(onClick = { confirmInstall = false }) { Text("Abbrechen") } },
        )
    }
    if (confirmRollback) {
        AlertDialog(
            onDismissRequest = { confirmRollback = false },
            title = { Text("Zurück zur vorherigen Version?") },
            text = { Text("Das Omafon startet danach neu.") },
            confirmButton = { TextButton(onClick = { confirmRollback = false; vm.rollback() }) { Text("Zurück") } },
            dismissButton = { TextButton(onClick = { confirmRollback = false }) { Text("Abbrechen") } },
        )
    }
}
