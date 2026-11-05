package de.omafon.companion.ui.devices

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.DEFAULT_PORT
import de.omafon.companion.data.variantLabel
import de.omafon.companion.ui.SectionTitle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DevicesScreen(
    onOpen: (String) -> Unit,
    onPair: (host: String, port: Int, name: String) -> Unit,
    vm: DevicesViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var manual by rememberSaveable { mutableStateOf(false) }
    val scroll = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        modifier = Modifier.nestedScroll(scroll.nestedScrollConnection),
        topBar = { LargeTopAppBar(title = { Text("Omafon") }, scrollBehavior = scroll) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { manual = true },
                icon = { Icon(Icons.Filled.Add, null) },
                text = { Text("Adresse eingeben") },
            )
        },
    ) { pad ->
        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding(),
                bottom = pad.calculateBottomPadding() + 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (ui.saved.isNotEmpty()) {
                item { SectionTitle("Meine Omafone") }
                items(ui.saved, key = { it.id }) { d ->
                    Card(
                        Modifier.fillMaxWidth().clickable { onOpen(d.id) },
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                    ) {
                        ListItem(
                            colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                            leadingContent = { Icon(Icons.Outlined.Phone, null, Modifier.size(32.dp)) },
                            headlineContent = { Text(d.name, style = MaterialTheme.typography.titleMedium) },
                            supportingContent = { Text("${variantLabel(d.variant)} · ${d.host}") },
                            trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
                        )
                    }
                }
            }
            item { SectionTitle("Im WLAN gefunden") }
            ui.searchError?.let { err ->
                item {
                    Text("$err – Adresse von Hand eingeben.", Modifier.padding(8.dp),
                        color = MaterialTheme.colorScheme.error)
                }
            } ?: item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 4.dp)) }
            if (ui.found.isEmpty() && ui.searchError == null) {
                item {
                    Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Suche läuft …", style = MaterialTheme.typography.bodyLarge)
                        Text(
                            "Das Handy muss im selben WLAN sein wie das Omafon. Wird nichts gefunden, " +
                                "die Adresse des Omafon eingeben (steht in der Fritz!Box unter Heimnetz).",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            items(ui.found, key = { "${it.host}:${it.port}" }) { f ->
                ListItem(
                    modifier = Modifier.clickable { onPair(f.host, f.port, f.name) },
                    leadingContent = { Icon(Icons.Outlined.Wifi, null) },
                    headlineContent = { Text(f.name) },
                    supportingContent = { Text("${f.host} – antippen zum Koppeln") },
                    trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
                )
            }
        }
    }

    if (manual) {
        ManualDialog(onDismiss = { manual = false }) { host, port ->
            manual = false
            onPair(host, port, "")
        }
    }
}

@Composable
private fun ManualDialog(onDismiss: () -> Unit, onOk: (String, Int) -> Unit) {
    var host by rememberSaveable { mutableStateOf("") }
    var port by rememberSaveable { mutableStateOf(DEFAULT_PORT.toString()) }
    val portNum = port.toIntOrNull()?.takeIf { it in 1..65535 }
    val valid = host.isNotBlank() && !host.contains('/') && !host.contains(' ') && portNum != null
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Omafon hinzufügen") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(host, { host = it.trim() }, label = { Text("Adresse") },
                    placeholder = { Text("192.168.178.40 oder omafon.local") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(port, { port = it.filter(Char::isDigit).take(5) }, label = { Text("Port") },
                        singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                }
            }
        },
        confirmButton = { TextButton(onClick = { onOk(host, portNum!!) }, enabled = valid) { Text("Weiter") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
