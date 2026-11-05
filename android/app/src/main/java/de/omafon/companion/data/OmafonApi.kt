package de.omafon.companion.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.serializer
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/** Fehler mit verständlicher Meldung für die Oberfläche. */
class ApiException(val status: Int, message: String, cause: Throwable? = null) : Exception(message, cause) {
    val unauthorized get() = status == 401
    val certificateChanged get() = status == CERT_CHANGED
    val offline get() = status == OFFLINE

    companion object {
        const val OFFLINE = -1
        const val CERT_CHANGED = -2
    }
}

/**
 * Zugriff auf ein Omafon. [fingerprint] null = erster Kontakt (vor dem Koppeln);
 * den gesehenen Fingerabdruck liefert dann [seenFingerprint].
 */
class OmafonApi(
    val host: String,
    val port: Int,
    fingerprint: String?,
    private val token: String? = null,
    base: OkHttpClient = sharedClient,
    private val scheme: String = "https",
) {
    private val trust = PinningTrustManager(fingerprint)
    private val client = base.newBuilder()
        .sslSocketFactory(trust.sslContext().socketFactory, trust)
        .hostnameVerifier { _, _ -> true }          // ersetzt durch den Fingerabdruck
        .build()

    val seenFingerprint: String? get() = trust.seen

    suspend fun info(): DeviceInfo = get("info")
    suspend fun pair(code: String, clientName: String): PairResponse = post("pair", PairRequest(code, clientName))
    suspend fun status(): DeviceStatus = get("status")
    suspend fun settings(): SettingsSchema = get("settings")
    suspend fun putSettings(values: Map<String, kotlinx.serialization.json.JsonElement?>): RestartResult =
        send("PUT", "settings", SettingsUpdate(values))
    suspend fun contacts(): ContactList = get("contacts")
    suspend fun putContacts(contacts: List<Contact>): RestartResult = send("PUT", "contacts", ContactList(contacts))
    suspend fun speak(text: String): OkResult = post("speak", SpeakRequest(text))
    suspend fun restart(): OkResult = post("restart", null as Unit?)
    suspend fun update(): UpdateInfo = get("update")
    suspend fun updateCheck(): UpdateInfo = post("update/check", null as Unit?)
    suspend fun updateInstall(): UpdateInfo = post("update/install", null as Unit?)
    suspend fun updateRollback(): UpdateInfo = post("update/rollback", null as Unit?)
    suspend fun clients(): ClientList = get("clients")
    suspend fun removeClient(id: String): OkResult = call("DELETE", "clients/$id", null, serializer())

    // ------------------------------------------------------------------ intern
    private suspend inline fun <reified T> get(path: String): T = call("GET", path, null, serializer())

    private suspend inline fun <reified B, reified T> post(path: String, body: B?): T = send("POST", path, body)

    private suspend inline fun <reified B, reified T> send(method: String, path: String, body: B?): T {
        val json = if (body == null) "{}" else ApiJson.encodeToString(body)
        return call(method, path, json.toRequestBody(JSON), serializer())
    }

    private suspend fun <T> call(method: String, path: String, body: RequestBody?, ser: KSerializer<T>): T =
        withContext(Dispatchers.IO) {
            val url = HttpUrl.Builder().scheme(scheme).host(host).port(port)
                .addPathSegments("api/v1/$path").build()
            val req = Request.Builder().url(url).method(method, body)
                .header("Accept", "application/json")
                .apply { if (!token.isNullOrEmpty()) header("Authorization", "Bearer $token") }
                .build()
            try {
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        val msg = runCatching { ApiJson.decodeFromString<ApiErrorBody>(text).error }
                            .getOrDefault("Fehler ${resp.code}")
                        throw ApiException(resp.code, msg)
                    }
                    try {
                        ApiJson.decodeFromString(ser, text)
                    } catch (e: IllegalArgumentException) {
                        throw ApiException(0, "Unerwartete Antwort vom Omafon", e)
                    }
                }
            } catch (e: SSLException) {
                val mismatch = generateSequence<Throwable>(e) { it.cause }.filterIsInstance<CertificateMismatch>().firstOrNull()
                if (mismatch != null) {
                    throw ApiException(ApiException.CERT_CHANGED, "Das Zertifikat des Omafon hat sich geändert. " +
                        "Wurde es neu eingerichtet? Dann bitte neu koppeln.", mismatch)
                }
                throw ApiException(ApiException.OFFLINE, "Sichere Verbindung fehlgeschlagen", e)
            } catch (e: IOException) {
                throw ApiException(ApiException.OFFLINE, "Omafon nicht erreichbar ($host). Ist es im selben WLAN?", e)
            }
        }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        val sharedClient: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)        // update/check lädt das Manifest
            .callTimeout(40, TimeUnit.SECONDS)
            .build()
    }
}
