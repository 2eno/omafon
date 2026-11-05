package de.omafon.companion

import android.app.Application
import de.omafon.companion.data.DeviceStore
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SavedDevice

/** Einfache Abhängigkeiten ohne DI-Framework. */
class AppContainer(val app: Application) {
    val store = DeviceStore(app)
    fun api(d: SavedDevice) = OmafonApi(d.host, d.port, d.fingerprint, d.token)
}

class OmafonApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
