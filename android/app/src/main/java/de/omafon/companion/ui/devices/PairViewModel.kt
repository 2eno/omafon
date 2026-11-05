package de.omafon.companion.ui.devices

import android.app.Application
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.omafon.companion.OmafonApp
import de.omafon.companion.data.DeviceInfo
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SavedDevice
import de.omafon.companion.ui.userMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class PairUi(
    val info: DeviceInfo? = null,
    val fingerprint: String? = null,
    val loading: Boolean = true,
    val pairing: Boolean = false,
    val error: String? = null,
    val pairedId: String? = null,
)

class PairViewModel(app: Application, private val host: String, private val port: Int, private val name: String) :
    AndroidViewModel(app) {
    private val store = (app as OmafonApp).container.store
    private val _ui = MutableStateFlow(PairUi())
    val ui: StateFlow<PairUi> = _ui.asStateFlow()

    init { probe() }

    /** Erster Kontakt: Ist das ein Omafon? Zertifikat merken (TOFU). */
    fun probe() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            val api = OmafonApi(host, port, null)
            runCatching { api.info() }
                .onSuccess { info ->
                    if (info.app != "omafon") {
                        _ui.update { it.copy(loading = false, error = "Unter $host antwortet kein Omafon.") }
                    } else {
                        _ui.update { it.copy(loading = false, info = info, fingerprint = api.seenFingerprint) }
                    }
                }
                .onFailure { e -> _ui.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    fun pair(code: String) {
        val fp = _ui.value.fingerprint ?: return
        _ui.update { it.copy(pairing = true, error = null) }
        viewModelScope.launch {
            val api = OmafonApi(host, port, fp)   // dasselbe Zertifikat wie beim ersten Kontakt
            runCatching {
                val res = api.pair(code, clientName())
                val authed = OmafonApi(host, port, fp, res.token)
                val owner = runCatching { authed.status().ownerName }.getOrDefault("")
                val label = when {
                    owner.isNotBlank() -> "Omafon von $owner"
                    name.isNotBlank() -> name
                    else -> "Omafon ($host)"
                }
                store.save(SavedDevice(res.deviceId, label, host, port, fp, _ui.value.info?.variant ?: "sip", res.token))
                res.deviceId
            }.onSuccess { id -> _ui.update { it.copy(pairing = false, pairedId = id) } }
                .onFailure { e -> _ui.update { it.copy(pairing = false, error = e.userMessage()) } }
        }
    }

    private fun clientName(): String {
        val model = listOf(Build.MANUFACTURER, Build.MODEL).filter { !it.isNullOrBlank() }.distinct()
        return model.joinToString(" ").ifBlank { "Android" }.take(40)
    }
}
