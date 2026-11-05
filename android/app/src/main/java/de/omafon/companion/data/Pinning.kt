package de.omafon.companion.data

import android.annotation.SuppressLint
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

/**
 * Das Omafon hat ein selbst signiertes Zertifikat (omafon/admin.py). Statt einer
 * Zertifizierungsstelle zählt der SHA-256-Fingerabdruck: beim Koppeln wird er
 * gemerkt (Trust on first use), danach muss er genau stimmen.
 *
 * expected == null: nur beim ersten Kontakt vor dem Koppeln – jeder Fingerabdruck
 * wird akzeptiert und in [seen] festgehalten. Danach ist die Prüfung strenger als
 * mit einer CA: nur genau dieses eine Zertifikat gilt.
 */
@SuppressLint("CustomX509TrustManager")   // bewusst: Pinning statt CA, siehe oben
class PinningTrustManager(private val expected: String?) : X509TrustManager {
    @Volatile
    var seen: String? = null
        private set

    override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
        val leaf = chain?.firstOrNull() ?: throw CertificateException("Kein Zertifikat")
        val fp = fingerprint(leaf.encoded)
        seen = fp
        if (expected != null && !MessageDigest.isEqual(fp.toByteArray(), expected.lowercase().toByteArray())) {
            throw CertificateMismatch(expected, fp)
        }
    }

    override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) =
        throw CertificateException("Nicht vorgesehen")

    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()

    fun sslContext(): SSLContext = SSLContext.getInstance("TLS").apply { init(null, arrayOf(this@PinningTrustManager), null) }

    companion object {
        fun fingerprint(der: ByteArray): String =
            MessageDigest.getInstance("SHA-256").digest(der).joinToString("") { "%02x".format(it) }

        /** Kurzform zum Vergleichen mit dem Auge: "AB12 CD34 …" (erste 8 Byte). */
        fun short(fp: String): String = fp.take(16).uppercase().chunked(4).joinToString(" ")
    }
}

class CertificateMismatch(val expected: String, val actual: String) :
    CertificateException("Zertifikat des Omafon hat sich geändert")
