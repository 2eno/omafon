package de.omafon.companion.ui.device

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.omafon.companion.OmafonApp
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SavedDevice
import de.omafon.companion.ui.Loadable
import de.omafon.companion.ui.needsRepair
import de.omafon.companion.ui.userMessage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Gemeinsame Grundlage der Geräte-Bildschirme: Gerät laden, API, Meldungen. */
abstract class DeviceViewModel<T>(app: Application, val deviceId: String) : AndroidViewModel(app) {
    protected val container = (app as OmafonApp).container
    protected val _state = MutableStateFlow(Loadable<T>(loading = true))
    val state: StateFlow<Loadable<T>> = _state.asStateFlow()
    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val messages: SharedFlow<String> = _messages.asSharedFlow()
    val device = MutableStateFlow<SavedDevice?>(null)
    private var loadJob: Job? = null           // vor init deklarieren, sonst überschreibt null den Job

    protected abstract suspend fun fetch(api: OmafonApi): T

    // Erst laden, wenn auch die Felder der Unterklasse initialisiert sind:
    // Dispatchers.Main (nicht .immediate) läuft erst nach dem Konstruktor.
    init { viewModelScope.launch(Dispatchers.Main) { refresh() } }

    protected suspend fun api(): OmafonApi {
        val d = device.value ?: container.store.get(deviceId) ?: throw IllegalStateException("Gerät nicht gespeichert")
        device.value = d
        return container.api(d)
    }

    fun refresh(silent: Boolean = false) {
        loadJob?.cancel()
        if (!silent) _state.update { it.copy(loading = true, error = null) }
        loadJob = viewModelScope.launch {
            runCatching { fetch(api()) }
                .onSuccess { data -> _state.value = Loadable(data) }
                .onFailure { e ->
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    _state.update { it.copy(loading = false, error = e.userMessage(), unauthorized = e.needsRepair()) }
                }
        }
    }

    protected fun say(msg: String) { _messages.tryEmit(msg) }

    /**
     * Aktion mit Fehlermeldung als Snackbar. [busy] wird während der Aktion
     * true und danach immer wieder false – auch wenn das Omafon nicht antwortet.
     */
    protected fun action(busy: MutableStateFlow<Boolean>? = null, block: suspend (OmafonApi) -> Unit) {
        if (busy?.value == true) return            // doppelt getippt
        busy?.value = true
        viewModelScope.launch {
            try {
                block(api())
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                say(e.userMessage())
            } finally {
                busy?.value = false
            }
        }
    }

    fun forget(done: () -> Unit) {
        viewModelScope.launch {
            container.store.remove(deviceId)
            done()
        }
    }
}
