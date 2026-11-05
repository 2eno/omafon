package de.omafon.companion.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** JSON-Einstellungen für die Omafon-Schnittstelle (/api/v1, siehe omafon/admin.py). */
val ApiJson = Json {
    ignoreUnknownKeys = true      // neuere Omafon-Versionen dürfen Felder ergänzen
    explicitNulls = false
    encodeDefaults = true
}

@Serializable
data class DeviceInfo(
    val app: String,
    val api: Int,
    val version: String,
    @SerialName("device_id") val deviceId: String,
    val variant: String,
    @SerialName("pairing_open") val pairingOpen: Boolean = false,
)

@Serializable
data class PairRequest(val code: String, @SerialName("client_name") val clientName: String)

@Serializable
data class PairResponse(
    val token: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("client_id") val clientId: String = "",
)

@Serializable
data class UpdateInfo(
    val current: String,
    val previous: String = "",
    val pending: String = "",
    val phase: String = "idle",
    @SerialName("last_error") val lastError: String = "",
    val available: AvailableUpdate? = null,
    @SerialName("update_available") val updateAvailable: Boolean = false,
    val configured: Boolean = false,
    @SerialName("can_rollback") val canRollback: Boolean = false,
) {
    /** Läuft gerade etwas auf dem Telefon? */
    val busy: Boolean get() = phase in setOf("checking", "downloading", "verifying", "installing", "restarting")
}

@Serializable
data class AvailableUpdate(val version: String? = null, val notes: String? = null)

@Serializable
data class DeviceStatus(
    val version: String,
    val variant: String,
    @SerialName("owner_name") val ownerName: String = "",
    @SerialName("uptime_s") val uptimeS: Long = 0,
    val state: String = "",
    val battery: Int? = null,
    val charging: Boolean = false,
    val online: Boolean = true,
    val connection: String = "",
    val unread: Int = 0,
    val missed: Int = 0,
    @SerialName("restart_pending") val restartPending: Boolean = false,
    val update: UpdateInfo? = null,
)

@Serializable
data class SettingsSchema(val variant: String, val groups: List<SettingGroup>)

@Serializable
data class SettingGroup(val title: String, val items: List<SettingItem>)

@Serializable
data class Choice(val value: String, val label: String)

@Serializable
data class SettingItem(
    val key: String,
    val type: String,             // int, float, bool, choice, text, secret, hours
    val label: String,
    val help: String = "",
    val unit: String = "",
    val min: Double? = null,
    val max: Double? = null,
    val step: Double? = null,
    val live: Boolean = false,
    val choices: List<Choice> = emptyList(),
    val value: JsonElement? = null,
    @SerialName("is_set") val isSet: Boolean = false,
)

@Serializable
data class SettingsUpdate(val values: Map<String, JsonElement?>)

@Serializable
data class RestartResult(val restart: Boolean = false)

@Serializable
data class Contact(
    val name: String,
    val number: String,
    val spoken: List<String> = emptyList(),
    @SerialName("speed_dial") val speedDial: Int? = null,
    val emergency: Int? = null,
    val admin: Boolean = false,
    @SerialName("telegram_chat_id") val telegramChatId: JsonElement? = null,
    val email: String? = null,
) {
    /** Telegram-ID kommt als Zahl oder Text; in der App immer Text. */
    val telegramText: String
        get() = (telegramChatId as? JsonPrimitive)?.contentOrNull ?: ""
}

@Serializable
data class ContactList(val contacts: List<Contact>)

@Serializable
data class SpeakRequest(val text: String)

@Serializable
data class OkResult(val ok: Boolean = true)

@Serializable
data class PairedClient(
    val id: String,
    val name: String,
    val created: String = "",
    @SerialName("last_seen") val lastSeen: String = "",
    @SerialName("this") val isThis: Boolean = false,
)

@Serializable
data class ClientList(val clients: List<PairedClient>)

@Serializable
data class ApiErrorBody(val error: String)

/** Ein gekoppeltes Omafon, wie die App es speichert. */
@Serializable
data class SavedDevice(
    val id: String,               // device_id des Omafon
    val name: String,
    val host: String,
    val port: Int,
    val fingerprint: String,      // SHA-256 des Zertifikats (hex, klein)
    val variant: String = "sip",
    val token: String = "",       // im Speicher verschlüsselt, siehe DeviceStore
)

fun variantLabel(variant: String) = when (variant) {
    "hybrid" -> "Hybrid (Fritz!Box + Mobilfunk)"
    "sip" -> "Festnetz (Fritz!Box)"
    else -> variant
}

fun stateLabel(state: String) = when (state) {
    "idle" -> "Bereit"
    "entry" -> "Nummer wird eingegeben"
    "voice_dial" -> "Sprachwahl"
    "outgoing" -> "Ruft an"
    "in_call" -> "Im Gespräch"
    "ringing" -> "Klingelt"
    "reading" -> "Liest Nachrichten vor"
    "dictate", "confirm" -> "Diktiert Nachricht"
    "sos" -> "Notruf läuft"
    "" -> "–"
    else -> state.replace('_', ' ').replaceFirstChar { it.uppercase() }
}
