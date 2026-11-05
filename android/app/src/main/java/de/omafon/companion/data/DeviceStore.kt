package de.omafon.companion.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.builtins.ListSerializer
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Verschlüsselt Tokens, bevor sie gespeichert werden. */
interface TokenCipher {
    fun encrypt(plain: String): String
    fun decrypt(stored: String): String
}

/** AES-GCM mit einem Schlüssel im Android Keystore (verlässt das Gerät nie). */
class KeystoreCipher(private val alias: String = "omafon_tokens") : TokenCipher {
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return gen.generateKey()
    }

    override fun encrypt(plain: String): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val out = c.iv + c.doFinal(plain.toByteArray())
        return Base64.encodeToString(out, Base64.NO_WRAP)
    }

    override fun decrypt(stored: String): String {
        val raw = Base64.decode(stored, Base64.NO_WRAP)
        val c = Cipher.getInstance("AES/GCM/NoPadding")
            .apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw, 0, 12)) }
        return String(c.doFinal(raw, 12, raw.size - 12))
    }
}

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "omafon")

/** Gekoppelte Geräte (JSON-Liste in DataStore, Tokens verschlüsselt). */
class DeviceStore(private val store: DataStore<Preferences>, private val cipher: TokenCipher) {
    constructor(context: Context) : this(context.dataStore, KeystoreCipher())

    private val key = stringPreferencesKey("devices")
    private val ser = ListSerializer(SavedDevice.serializer())

    val devices: Flow<List<SavedDevice>> = store.data.map { prefs ->
        prefs[key]?.let { decode(it) } ?: emptyList()
    }

    suspend fun all(): List<SavedDevice> = devices.first()

    suspend fun get(id: String): SavedDevice? = all().firstOrNull { it.id == id }

    suspend fun save(device: SavedDevice) = mutate { list -> list.filterNot { it.id == device.id } + device }

    suspend fun remove(id: String) = mutate { list -> list.filterNot { it.id == id } }

    private suspend fun mutate(f: (List<SavedDevice>) -> List<SavedDevice>) {
        store.edit { prefs ->
            val list = prefs[key]?.let { decode(it) } ?: emptyList()
            prefs[key] = encode(f(list))
        }
    }

    private fun decode(text: String): List<SavedDevice> =
        runCatching { ApiJson.decodeFromString(ser, text) }.getOrDefault(emptyList()).map { d ->
            // Token nicht entschlüsselbar (z. B. App-Daten wiederhergestellt) -> neu koppeln
            d.copy(token = runCatching { cipher.decrypt(d.token) }.getOrDefault(""))
        }

    private fun encode(list: List<SavedDevice>): String =
        ApiJson.encodeToString(ser, list.map { it.copy(token = if (it.token.isEmpty()) "" else cipher.encrypt(it.token)) })
}
