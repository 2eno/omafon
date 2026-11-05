package de.omafon.companion

import de.omafon.companion.data.ApiException
import de.omafon.companion.data.Contact
import de.omafon.companion.data.OmafonApi
import de.omafon.companion.data.PinningTrustManager
import de.omafon.companion.ui.needsRepair
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** Gegen einen echten TLS-Server mit selbst signiertem Zertifikat – wie das Omafon. */
class ApiTest {
    private lateinit var server: MockWebServer
    private lateinit var cert: HeldCertificate
    private val base = OkHttpClient()

    @Before fun setUp() {
        cert = HeldCertificate.Builder().commonName("omafon").build()
        server = MockWebServer()
        server.useHttps(HandshakeCertificates.Builder().heldCertificate(cert).build().sslSocketFactory(), false)
        server.start()
    }

    @After fun tearDown() = server.shutdown()

    private val fp get() = PinningTrustManager.fingerprint(cert.certificate.encoded)

    private fun api(pin: String?, token: String? = null) = OmafonApi(server.hostName, server.port, pin, token, base)

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    private val info = """{"app":"omafon","api":1,"version":"0.9.0","device_id":"d","variant":"sip","pairing_open":true,"neu":1}"""

    @Test fun firstContactRecordsFingerprint() = runTest {
        server.enqueue(json(info))
        val a = api(null)
        assertEquals("omafon", a.info().app)
        assertEquals(fp, a.seenFingerprint)
    }

    @Test fun pinnedCertificateIsAccepted() = runTest {
        server.enqueue(json(info))
        assertEquals("d", api(fp).info().deviceId)
    }

    @Test fun changedCertificateIsRejected() = runTest {
        server.enqueue(json(info))
        try {
            api("00".repeat(32)).info()
            fail("Falsches Zertifikat angenommen")
        } catch (e: ApiException) {
            assertTrue(e.certificateChanged)
            assertTrue("Neu koppeln anbieten", e.needsRepair())
        }
    }

    @Test fun tokenIsSentAndErrorsAreReadable() = runTest {
        server.enqueue(json("""{"error":"Unbekannte App – bitte neu koppeln"}""", 401))
        try {
            api(fp, "geheim").status()
            fail()
        } catch (e: ApiException) {
            assertTrue(e.unauthorized)
            assertTrue(e.needsRepair())
            assertEquals("Unbekannte App – bitte neu koppeln", e.message)
        }
        assertEquals("Bearer geheim", server.takeRequest().getHeader("Authorization"))
    }

    @Test fun putContactsSendsWhatTheOmafonExpects() = runTest {
        server.enqueue(json("""{"restart":true}"""))
        val res = api(fp, "t").putContacts(listOf(
            Contact("Peter", "+491711234567", listOf("peter"), speedDial = 1, emergency = 1,
                telegramChatId = JsonPrimitive("42")),
            Contact("Maria", "0301234567"),
        ))
        assertTrue(res.restart)
        val req = server.takeRequest()
        assertEquals("PUT", req.method)
        assertEquals("/api/v1/contacts", req.path)
        val body = Json.parseToJsonElement(req.body.readUtf8()).jsonObject
        val list = body["contacts"].toString()
        assertTrue(list, list.contains("\"speed_dial\":1"))
        assertTrue(list, list.contains("\"telegram_chat_id\":\"42\""))
        assertTrue("null-Felder weglassen: $list", !list.contains("null"))
    }

    @Test fun putSettingsKeepsNumberTypes() = runTest {
        server.enqueue(json("""{"restart":false}"""))
        api(fp, "t").putSettings(mapOf("volume" to JsonPrimitive(3), "speech_rate" to JsonPrimitive(1.3)))
        val body = server.takeRequest().body.readUtf8()
        assertEquals("""{"values":{"volume":3,"speech_rate":1.3}}""", body)
    }

    @Test fun offlineIsReported() = runTest {
        server.shutdown()
        try {
            api(fp).info()
            fail()
        } catch (e: ApiException) {
            assertTrue(e.offline)
            assertTrue("offline: nochmal versuchen, nicht neu koppeln", !e.needsRepair())
        }
    }
}
