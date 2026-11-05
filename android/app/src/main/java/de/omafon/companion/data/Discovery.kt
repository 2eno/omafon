package de.omafon.companion.data

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import java.util.concurrent.Executors

/** Ein per mDNS gefundenes Omafon (_omafon._tcp, systemd/omafon.avahi.xml). */
data class FoundDevice(val name: String, val host: String, val port: Int)

/** Sucht Omafone im WLAN, solange der Flow gesammelt wird. Liefert die aktuelle Liste. */
fun discoverOmafons(context: Context): Flow<List<FoundDevice>> = callbackFlow {
    val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    val lock = wifi.createMulticastLock("omafon-suche").apply { setReferenceCounted(false); acquire() }
    val found = linkedMapOf<String, FoundDevice>()
    val executor = Executors.newSingleThreadExecutor()
    val pending = ArrayDeque<NsdServiceInfo>()
    var resolving = false

    fun publish() { trySend(found.values.toList()) }

    fun resolved(info: NsdServiceInfo) {
        val host = hostOf(info) ?: return
        synchronized(found) {
            found[info.serviceName] = FoundDevice(info.serviceName, host, info.port)
            publish()
        }
    }

    fun resolveNext() {
        val next = synchronized(pending) {
            if (resolving || pending.isEmpty()) return
            resolving = true
            pending.removeFirst()
        }
        @Suppress("DEPRECATION")
        nsd.resolveService(next, object : NsdManager.ResolveListener {
            override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) = done()
            override fun onServiceResolved(info: NsdServiceInfo) {
                resolved(info)
                done()
            }

            private fun done() {
                synchronized(pending) { resolving = false }
                resolveNext()
            }
        })
    }

    val listener = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(serviceType: String) {}
        override fun onDiscoveryStopped(serviceType: String) {}
        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
            close(IllegalStateException("mDNS-Suche startet nicht ($errorCode)"))
        }
        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
        override fun onServiceLost(info: NsdServiceInfo) {
            synchronized(found) { if (found.remove(info.serviceName) != null) publish() }
        }

        override fun onServiceFound(info: NsdServiceInfo) {
            if (Build.VERSION.SDK_INT >= 34) {
                nsd.registerServiceInfoCallback(info, executor, object : NsdManager.ServiceInfoCallback {
                    override fun onServiceInfoCallbackRegistrationFailed(errorCode: Int) {}
                    override fun onServiceUpdated(updated: NsdServiceInfo) {
                        resolved(updated)
                        runCatching { nsd.unregisterServiceInfoCallback(this) }
                    }
                    override fun onServiceLost() {}
                    override fun onServiceInfoCallbackUnregistered() {}
                })
            } else {
                // Vor Android 14 kann NsdManager nur eine Auflösung gleichzeitig –
                // eine zweite scheitert mit FAILURE_ALREADY_ACTIVE. Darum nacheinander.
                synchronized(pending) { pending.addLast(info) }
                resolveNext()
            }
        }
    }
    trySend(emptyList())
    nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
    awaitClose {
        runCatching { nsd.stopServiceDiscovery(listener) }
        lock.release()
        executor.shutdown()
    }
}

private fun hostOf(info: NsdServiceInfo): String? {
    val addr = if (Build.VERSION.SDK_INT >= 34) {
        info.hostAddresses.firstOrNull { it is java.net.Inet4Address } ?: info.hostAddresses.firstOrNull()
    } else {
        @Suppress("DEPRECATION") info.host
    }
    return addr?.hostAddress?.substringBefore('%')
}

const val SERVICE_TYPE = "_omafon._tcp."
const val DEFAULT_PORT = 8443
