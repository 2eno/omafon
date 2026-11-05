package de.omafon.companion.ui.device

import android.app.Application
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Emergency
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.omafon.companion.data.Contact
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.ui.BackTopBar
import de.omafon.companion.ui.CenteredProgress
import de.omafon.companion.ui.ErrorPanel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.json.JsonPrimitive

class ContactsViewModel(app: Application, id: String) : DeviceViewModel<List<Contact>>(app, id) {
    /** Bearbeitete Liste; null = unverändert. */
    val draft = MutableStateFlow<List<Contact>?>(null)
    val saving = MutableStateFlow(false)

    override suspend fun fetch(api: OmafonApi) = api.contacts().contacts

    private fun current() = draft.value ?: state.value.data.orEmpty()

    fun put(index: Int?, c: Contact) {
        val list = current().toMutableList()
        if (index == null) list.add(c) else list[index] = c
        draft.value = list
    }

    fun remove(index: Int) { draft.value = current().filterIndexed { i, _ -> i != index } }

    fun save() {
        val list = draft.value ?: return
        action(saving) { api ->
            api.putContacts(list)
            if (draft.value == list) draft.value = null
            say("Kontakte gespeichert. Das Omafon startet kurz neu, sobald es in Ruhe ist.")
            refresh(silent = true)
        }
    }
}

/** Prüft wie omafon/admin.py validate_contacts – Fehler schon in der App zeigen. */
object ContactRules {
    private val number = Regex("^\\+?[0-9*#]{2,20}$")
    private val word = Regex("^[a-zäöüß]{2,20}$")

    fun cleanNumber(n: String) = n.replace(Regex("[\\s/()-]"), "")
    fun words(text: String) = text.split(',', ' ', ';').map { it.trim().lowercase() }.filter { it.isNotEmpty() }

    fun problems(c: Contact, others: List<Contact>): List<String> = buildList {
        if (c.name.isBlank() || c.name.length > 40) add("Name fehlt oder ist zu lang")
        if (!number.matches(cleanNumber(c.number))) add("Telefonnummer ungültig")
        if (c.spoken.any { !word.matches(it) }) add("Sprachwahl: nur Wörter aus Buchstaben")
        if (c.speedDial != null && others.any { it.speedDial == c.speedDial }) add("Kurzwahl ${c.speedDial} ist schon vergeben")
        if (c.emergency != null && others.any { it.emergency == c.emergency }) add("Notruf-Platz ${c.emergency} ist schon vergeben")
    }
}

@Composable
fun ContactsScreen(deviceId: String, onBack: () -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: ContactsViewModel = viewModel(key = "contacts-$deviceId") { ContactsViewModel(app, deviceId) }
    val state by vm.state.collectAsStateWithLifecycle()
    val draft by vm.draft.collectAsStateWithLifecycle()
    val saving by vm.saving.collectAsStateWithLifecycle()
    val device by vm.device.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    var editing by remember { mutableStateOf<Pair<Int?, Contact>?>(null) }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }

    val list = draft ?: state.data
    Scaffold(
        topBar = {
            BackTopBar("Kontakte", onBack) {
                if (draft != null) TextButton(onClick = { if (!saving) vm.save() }) {
                    Icon(Icons.Filled.Check, null)
                    Text(if (saving) " Speichert …" else " Speichern")
                }
            }
        },
        snackbarHost = { SnackbarHost(snack) },
        floatingActionButton = {
            if (list != null && list.size < 50) ExtendedFloatingActionButton(
                onClick = { editing = null to Contact("", "") },
                icon = { Icon(Icons.Filled.PersonAdd, null) }, text = { Text("Kontakt") })
        },
    ) { pad ->
        when {
            list == null && state.loading -> CenteredProgress(Modifier.padding(pad))
            list == null -> ErrorPanel(state.error ?: "Fehler", { vm.refresh() }, Modifier.padding(pad))
            else -> LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = pad.calculateTopPadding() + 8.dp,
                    bottom = pad.calculateBottomPadding() + 96.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (list.isEmpty()) item { Text("Noch keine Kontakte.", Modifier.padding(16.dp)) }
                itemsIndexed(list) { i, c ->
                    Card(Modifier.fillMaxWidth().clickable { editing = i to c }) {
                        ListItem(
                            leadingContent = { Icon(if (c.emergency != null) Icons.Outlined.Emergency else Icons.Outlined.Person, null) },
                            headlineContent = { Text(c.name, style = MaterialTheme.typography.titleMedium) },
                            supportingContent = {
                                Column {
                                    Text(c.number)
                                    val tags = buildList {
                                        c.speedDial?.let { add("Kurzwahl $it") }
                                        c.emergency?.let { add("Notruf $it.") }
                                        if (c.spoken.isNotEmpty()) add("„${c.spoken.joinToString(" / ")}“")
                                    }
                                    if (tags.isNotEmpty()) Text(tags.joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.primary)
                                }
                            },
                        )
                    }
                }
            }
        }
    }

    editing?.let { (index, contact) ->
        val others = list.orEmpty().filterIndexed { i, _ -> i != index }
        ContactDialog(contact, others, hybrid = device?.variant == "hybrid",
            isNew = index == null,
            onDismiss = { editing = null },
            onDelete = { index?.let(vm::remove); editing = null },
            onSave = { vm.put(index, it); editing = null })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ContactDialog(
    initial: Contact, others: List<Contact>, hybrid: Boolean, isNew: Boolean,
    onDismiss: () -> Unit, onDelete: () -> Unit, onSave: (Contact) -> Unit,
) {
    var name by remember { mutableStateOf(initial.name) }
    var number by remember { mutableStateOf(initial.number) }
    var spoken by remember { mutableStateOf(initial.spoken.joinToString(", ")) }
    var speed by remember { mutableStateOf(initial.speedDial) }
    var emergency by remember { mutableStateOf(initial.emergency) }
    var admin by remember { mutableStateOf(initial.admin) }
    var email by remember { mutableStateOf(initial.email.orEmpty()) }
    var telegram by remember { mutableStateOf(initial.telegramText) }

    val contact = Contact(
        name = name.trim(), number = ContactRules.cleanNumber(number), spoken = ContactRules.words(spoken),
        speedDial = speed, emergency = emergency, admin = admin && hybrid,
        email = email.trim().ifEmpty { null },
        telegramChatId = telegram.trim().ifEmpty { null }?.let { JsonPrimitive(it) },
    )
    val problems = ContactRules.problems(contact, others)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isNew) "Neuer Kontakt" else "Kontakt bearbeiten") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it.take(40) }, label = { Text("Name (wird angesagt)") }, singleLine = true)
                OutlinedTextField(number, { number = it }, label = { Text("Telefonnummer") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
                OutlinedTextField(spoken, { spoken = it }, label = { Text("Sprachwahl-Wörter") }, singleLine = true,
                    supportingText = { Text("z. B. peter, sohn – damit „Peter anrufen“ klappt") })
                NumberPicker("Kurzwahl (Taste lang)", speed, 1..9, others.mapNotNull { it.speedDial }.toSet()) { speed = it }
                NumberPicker("Platz in der Notrufkette", emergency, 1..20, others.mapNotNull { it.emergency }.toSet()) { emergency = it }
                if (hybrid) Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Darf per SMS „STATUS“ abfragen")
                        Text("Nur Hybrid", style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(admin, { admin = it })
                }
                OutlinedTextField(email, { email = it }, label = { Text("E-Mail für Hinweise (optional)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
                OutlinedTextField(telegram, { telegram = it }, label = { Text("Telegram-Chat-ID (optional)") }, singleLine = true)
                problems.forEach { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                if (!isNew) AssistChip(onClick = onDelete, label = { Text("Kontakt löschen") },
                    leadingIcon = { Icon(Icons.Outlined.Delete, null) })
            }
        },
        confirmButton = { TextButton(onClick = { onSave(contact) }, enabled = problems.isEmpty()) { Text("Übernehmen") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NumberPicker(label: String, value: Int?, range: IntRange, taken: Set<Int>, onPick: (Int?) -> Unit) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(value?.toString() ?: "keine", {}, readOnly = true, label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable))
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            DropdownMenuItem(text = { Text("keine") }, onClick = { open = false; onPick(null) })
            range.filter { it !in taken }.forEach { n ->
                DropdownMenuItem(text = { Text(n.toString()) }, onClick = { open = false; onPick(n) })
            }
        }
    }
}
