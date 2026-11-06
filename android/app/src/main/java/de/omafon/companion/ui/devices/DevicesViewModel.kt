package de.omafon.companion.ui.devices

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.omafon.companion.OmafonApp
import de.omafon.companion.data.FoundDevice
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SavedDevice
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class DevicesUi(
    val saved: List<SavedDevice> = emptyList(),
    val found: List<FoundDevice> = emptyList(),   // noch nicht gekoppelt
    val searchError: String? = null,              // mDNS geht nicht (z. B. kein WLAN)
)

class DevicesViewModel(app: Application) : AndroidViewModel(app) {
    private val container = (app as OmafonApp).container
    private val store = container.store
    private val checked = mutableSetOf<String>()
    private val _foundSaved = MutableStateFlow<Map<String, String>>(emptyMap())   // host:port -> device_id
    private val searchError = MutableStateFlow<String?>(null)

    private val discovery = container.discovery()
        .onEach { list -> searchError.value = null; list.forEach { matchSaved(it) } }
        .catch { e ->
            // Technische Meldung ins Log, für Menschen ein klarer Satz
            android.util.Log.w("Omafon", "mDNS-Suche gescheitert", e)
            searchError.value = "Die Suche im WLAN geht auf diesem Handy gerade nicht"
            emit(emptyList())
        }

    val ui: StateFlow<DevicesUi> = combine(store.devices, discovery, _foundSaved, searchError) { saved, found, known, err ->
        val savedIds = saved.map { it.id }.toSet()
        DevicesUi(
            saved = saved,
            found = found.filter { f -> known["${f.host}:${f.port}"]?.let { it !in savedIds } ?: true },
            searchError = err,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DevicesUi())

    /**
     * Neue IP-Adresse eines bekannten Omafon (DHCP)? Gefundene Geräte fragen und
     * bei passender device_id und gleichem Zertifikat die Adresse übernehmen.
     */
    private fun matchSaved(f: FoundDevice) {
        val key = "${f.host}:${f.port}"
        if (!checked.add(key)) return
        viewModelScope.launch {
            val probe = OmafonApi(f.host, f.port, null)
            val info = runCatching { probe.info() }.getOrNull() ?: return@launch
            _foundSaved.value = _foundSaved.value + (key to info.deviceId)
            val saved = store.get(info.deviceId) ?: return@launch
            if (saved.fingerprint == probe.seenFingerprint && (saved.host != f.host || saved.port != f.port)) {
                store.save(saved.copy(host = f.host, port = f.port))
            }
        }
    }
}
