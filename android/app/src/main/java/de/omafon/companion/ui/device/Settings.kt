package de.omafon.companion.ui.device

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SettingItem
import de.omafon.companion.data.SettingsSchema
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.CenteredProgress
import de.omafon.companion.ui.ErrorPanel
import de.omafon.companion.ui.LabeledFab
import de.omafon.companion.ui.SectionCard
import de.omafon.companion.ui.SectionTitle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlin.math.roundToInt

class SettingsViewModel(app: Application, id: String) : DeviceViewModel<SettingsSchema>(app, id) {
    /** Geänderte Werte (Schlüssel -> neuer Wert), noch nicht gespeichert. */
    val edits = MutableStateFlow<Map<String, JsonElement>>(emptyMap())
    val saving = MutableStateFlow(false)

    override suspend fun fetch(api: OmafonApi) = api.settings()

    fun set(item: SettingItem, value: JsonElement) {
        val unchanged = if (item.type == "secret") value.asText().isEmpty()   // leer = Kennwort behalten
                        else value == item.value
        edits.update { if (unchanged) it - item.key else it + (item.key to value) }
    }

    fun save() {
        val changes = edits.value
        if (changes.isEmpty()) return
        action(saving) { api ->
            val res = api.putSettings(changes)
            // Nur das Gespeicherte verwerfen: inzwischen Geändertes bleibt stehen
            edits.update { now -> now.filter { (k, v) -> changes[k] != v } }
            say(if (res.restart) "Gespeichert. Das Omafon startet kurz neu, sobald es in Ruhe ist."
                else "Gespeichert und sofort wirksam.")
            refresh(silent = true)
        }
    }
}

fun JsonElement?.asDouble(): Double? = (this as? JsonPrimitive)?.doubleOrNull
fun JsonElement?.asBool(): Boolean = (this as? JsonPrimitive)?.booleanOrNull ?: false
fun JsonElement?.asText(): String = (this as? JsonPrimitive)?.takeIf { this !is JsonNull }?.contentOrNull ?: ""
fun JsonElement?.asHours(): Pair<Int, Int> {
    val a = this as? JsonArray
    val from = (a?.getOrNull(0) as? JsonPrimitive)?.intOrNull ?: 22
    val to = (a?.getOrNull(1) as? JsonPrimitive)?.intOrNull ?: 7
    return from to to
}

/** Zahl so formatieren, wie das Omafon sie erwartet (int ohne Nachkommastellen). */
fun numberJson(item: SettingItem, v: Double): JsonPrimitive =
    if (item.type == "int") JsonPrimitive(v.roundToInt()) else JsonPrimitive((v * 100).roundToInt() / 100.0)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(deviceId: String, onBack: () -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: SettingsViewModel = viewModel(key = "settings-$deviceId") { SettingsViewModel(app, deviceId) }
    val state by vm.state.collectAsStateWithLifecycle()
    val edits by vm.edits.collectAsStateWithLifecycle()
    val saving by vm.saving.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }

    Scaffold(
        topBar = { BackTopBar("Einstellungen", onBack) },
        snackbarHost = { SnackbarHost(snack) },
        floatingActionButton = {
            if (edits.isNotEmpty()) {
                LabeledFab(if (saving) "Speichert …" else "Speichern (${edits.size})", Icons.Filled.Check) {
                    if (!saving) vm.save()
                }
            }
        },
    ) { pad ->
        val schema = state.data
        when {
            schema == null && state.loading -> CenteredProgress(Modifier.padding(pad))
            schema == null -> ErrorPanel(state.error ?: "Fehler", { vm.refresh() }, Modifier.padding(pad))
            else -> LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding(),
                    bottom = pad.calculateBottomPadding() + 96.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                schema.groups.forEach { group ->
                    item(key = "g-${group.title}") { SectionTitle(group.title) }
                    items(group.items, key = { it.key }) { item ->
                        SectionCard {
                            SettingEditor(item, edits[item.key] ?: item.value) { vm.set(item, it) }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingEditor(item: SettingItem, value: JsonElement?, onChange: (JsonElement) -> Unit) {
    val title: @Composable () -> Unit = { Text(item.label, style = MaterialTheme.typography.titleSmall) }
    val help: @Composable () -> Unit = {
        if (item.help.isNotBlank()) Text(item.help, style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    when (item.type) {
        // Ganze Zeile schaltbar: größere Fläche, TalkBack liest Bezeichnung + Zustand zusammen
        "bool" -> Row(
            Modifier.fillMaxWidth().toggleable(
                value = value.asBool(), role = Role.Switch,
                onValueChange = { onChange(JsonPrimitive(it)) },
            ),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) { title(); help() }
            Switch(checked = value.asBool(), onCheckedChange = null)
        }
        "int", "float" -> {
            val min = item.min ?: 0.0
            val max = item.max ?: 100.0
            val step = item.step ?: if (item.type == "int") 1.0 else 0.1
            val v = value.asDouble() ?: min
            val stepsCount = ((max - min) / step).roundToInt()
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { title() }
                Text(formatNumber(item, v), style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary)
            }
            if (stepsCount in 1..120) {
                Slider(
                    value = v.toFloat().coerceIn(min.toFloat(), max.toFloat()),
                    onValueChange = { f ->
                        val snapped = min + ((f - min) / step).roundToInt() * step
                        onChange(numberJson(item, snapped))
                    },
                    valueRange = min.toFloat()..max.toFloat(),
                    steps = (stepsCount - 1).coerceAtLeast(0),
                )
            } else {
                var text by remember(value) { mutableStateOf(formatPlain(item, v)) }
                OutlinedTextField(text, { t ->
                    text = t
                    t.replace(',', '.').toDoubleOrNull()?.takeIf { it in min..max }?.let { onChange(numberJson(item, it)) }
                }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    supportingText = { Text("${formatPlain(item, min)} bis ${formatPlain(item, max)} ${item.unit}") })
            }
            help()
        }
        "choice" -> {
            var open by remember { mutableStateOf(false) }
            val current = item.choices.firstOrNull { it.value == value.asText() }
            ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
                OutlinedTextField(
                    value = current?.label ?: value.asText(), onValueChange = {}, readOnly = true,
                    label = { Text(item.label) },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                    item.choices.forEach { c ->
                        DropdownMenuItem(text = { Text(c.label) }, onClick = {
                            open = false
                            onChange(JsonPrimitive(c.value))
                        })
                    }
                }
            }
            help()
        }
        "hours" -> {
            val (from, to) = value.asHours()
            title()
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                HourPicker("von", from, Modifier.weight(1f)) { onChange(JsonArray(listOf(JsonPrimitive(it), JsonPrimitive(to)))) }
                HourPicker("bis", to, Modifier.weight(1f)) { onChange(JsonArray(listOf(JsonPrimitive(from), JsonPrimitive(it)))) }
            }
            help()
        }
        "secret" -> {
            var shown by remember { mutableStateOf(false) }
            OutlinedTextField(
                value = value.asText(), onValueChange = { onChange(JsonPrimitive(it)) },
                label = { Text(item.label) }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text(if (item.isSet) "gespeichert – leer lassen = unverändert" else "nicht gesetzt") },
                visualTransformation = if (shown) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    IconButton(onClick = { shown = !shown }) {
                        Icon(if (shown) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            if (shown) "Verbergen" else "Anzeigen")
                    }
                },
            )
            help()
        }
        else -> {                                   // text und unbekannte Typen
            OutlinedTextField(value.asText(), { onChange(JsonPrimitive(it)) }, label = { Text(item.label) },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            help()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HourPicker(label: String, hour: Int, modifier: Modifier, onPick: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }, modifier = modifier) {
        OutlinedTextField("%02d:00".format(hour), {}, readOnly = true, label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable))
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            (0..23).forEach { h ->
                DropdownMenuItem(text = { Text("%02d:00".format(h)) }, onClick = { open = false; onPick(h) })
            }
        }
    }
}

private fun formatPlain(item: SettingItem, v: Double): String =
    if (item.type == "int") v.roundToInt().toString() else "%.1f".format(v).replace('.', ',')

fun formatNumber(item: SettingItem, v: Double): String {
    val n = formatPlain(item, v)
    return if (item.unit.isBlank()) n else "$n ${item.unit}"
}
