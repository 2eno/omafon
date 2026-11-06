package de.omafon.companion

import android.app.Application
import androidx.annotation.VisibleForTesting
import de.omafon.companion.data.DeviceStore
import de.omafon.companion.data.FoundDevice
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.SavedDevice
import de.omafon.companion.data.discoverOmafons
import kotlinx.coroutines.flow.Flow

/** Einfache Abhängigkeiten ohne DI-Framework. Tests setzen eigene ein. */
class AppContainer(
    val app: Application,
    val store: DeviceStore = DeviceStore(app),
    /** Omafone im WLAN suchen (mDNS); Tests liefern eine feste Liste. */
    val discovery: () -> Flow<List<FoundDevice>> = { discoverOmafons(app) },
) {
    fun api(d: SavedDevice) = OmafonApi(d.host, d.port, d.fingerprint, d.token)
}

class OmafonApp : Application() {
    @set:VisibleForTesting
    lateinit var container: AppContainer

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
