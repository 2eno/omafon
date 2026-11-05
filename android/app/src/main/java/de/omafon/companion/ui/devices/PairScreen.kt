package de.omafon.companion.ui.devices

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material.icons.outlined.Dialpad
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.PinningTrustManager
import de.omafon.companion.data.variantLabel
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.ErrorPanel
import de.omafon.companion.ui.SectionCard

@Composable
fun PairScreen(host: String, port: Int, name: String, onBack: () -> Unit, onPaired: (String) -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: PairViewModel = viewModel(key = "pair-$host-$port") { PairViewModel(app, host, port, name) }
    val ui by vm.ui.collectAsStateWithLifecycle()
    var code by rememberSaveable { mutableStateOf("") }

    LaunchedEffect(ui.pairedId) { ui.pairedId?.let(onPaired) }

    Scaffold(topBar = { BackTopBar("Koppeln", onBack) }) { pad ->
        Column(
            Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            when {
                ui.loading -> Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(Modifier.size(24.dp))
                    Text("Verbinde mit $host …")
                }
                ui.info == null -> ErrorPanel(ui.error ?: "Unbekannter Fehler", onRetry = vm::probe)
                else -> {
                    val info = ui.info!!
                    SectionCard {
                        Text(name.ifBlank { "Omafon" }, style = MaterialTheme.typography.titleLarge)
                        Text("${variantLabel(info.variant)} · Version ${info.version}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        ui.fingerprint?.let {
                            Row(verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Icon(Icons.Outlined.Lock, null, Modifier.size(16.dp))
                                Text("Zertifikat ${PinningTrustManager.short(it)}",
                                    style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                            }
                        }
                    }
                    SectionCard {
                        Row(verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Icon(Icons.Outlined.Dialpad, null, Modifier.size(32.dp),
                                tint = MaterialTheme.colorScheme.primary)
                            Text("So geht's", style = MaterialTheme.typography.titleMedium)
                        }
                        Text("1. Am Omafon die Raute-Taste # lang drücken.")
                        Text("2. Das Omafon sagt einen sechsstelligen Code zweimal an.")
                        Text("3. Den Code hier eingeben. Er gilt fünf Minuten.")
                    }
                    OutlinedTextField(
                        value = code,
                        onValueChange = { code = it.filter(Char::isDigit).take(6) },
                        label = { Text("Code vom Omafon") },
                        singleLine = true,
                        textStyle = MaterialTheme.typography.headlineMedium.copy(
                            fontFamily = FontFamily.Monospace, letterSpacing = 8.sp, textAlign = TextAlign.Center),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword,
                            imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { if (code.length == 6) vm.pair(code) }),
                        modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Sechsstelliger Code" },
                        isError = ui.error != null,
                        supportingText = { ui.error?.let { Text(it) } },
                    )
                    Button(
                        onClick = { vm.pair(code) },
                        enabled = code.length == 6 && !ui.pairing,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (ui.pairing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        else Text("Koppeln")
                    }
                }
            }
        }
    }
}
