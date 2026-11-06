package de.omafon.companion

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.view.View
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.ComposeTimeoutException
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.printToString
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import de.omafon.companion.data.DeviceStore
import de.omafon.companion.data.FoundDevice
import de.omafon.companion.data.PinningTrustManager
import de.omafon.companion.data.SavedDevice
import de.omafon.companion.data.TokenCipher
import de.omafon.companion.ui.OmafonNavHost
import de.omafon.companion.ui.theme.OmafonTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowLooper
import java.io.File
import java.util.Collections

/**
 * Die Oberfläche wirklich bedienen – auf der JVM (Robolectric), gegen ein
 * nachgebautes Omafon über HTTPS mit selbst signiertem Zertifikat, das die
 * JSON-Beispiele des echten Omafon liefert (tools/api_fixtures.py).
 *
 * Bildschirmfotos landen in app/build/screenshots/ (CI: Artefakt android-berichte).
 *
 * Robolectric-Eigenheit: Ein Dialog mit Textfeld gerät bei jeder anderen als der
 * Standardgröße (320 × 470 dp) in eine endlose Mess-Schleife (AppNotIdleException).
 * Tests mit Dialog laufen darum in der Standardgröße – ein kleines Handy, als
 * Prüfung fürs Layout sogar nützlich –, die übrigen groß (GROSS).
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class UiFlowTest {
    companion object {
        const val GROSS = "w411dp-h891dp-xhdpi"
        const val GROSS_NACHT = "w411dp-h891dp-night-xhdpi"   // Reihenfolge laut Android: night vor dpi
    }

    @get:Rule
    val compose = createAndroidComposeRule<ComponentActivity>()

    private lateinit var server: MockWebServer
    private lateinit var cert: HeldCertificate
    private lateinit var scope: CoroutineScope
    private lateinit var store: DeviceStore
    private val writes = Collections.synchronizedList(mutableListOf<Pair<String, String>>())
    private val found = MutableStateFlow<List<FoundDevice>>(emptyList())   // statt mDNS

    /** Im Test kein Android-Keystore: Tokens nur markieren statt verschlüsseln. */
    private object PlainCipher : TokenCipher {
        override fun encrypt(plain: String) = "test:$plain"
        override fun decrypt(stored: String) = stored.removePrefix("test:")
    }

    private fun fixture(name: String) =
        requireNotNull(javaClass.classLoader!!.getResource("api/$name")).readText()

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    private fun respond(r: RecordedRequest): MockResponse {
        val path = r.path.orEmpty().removePrefix("/api/v1/").substringBefore('?')
        val body = r.body.readUtf8()
        if (r.method != "GET") writes.add("${r.method} $path" to body)
        return when ("${r.method} $path") {
            "GET info" -> json(fixture("info.json"))
            "POST pair" -> if ("\"123456\"" in body) json(fixture("pair.json"))
                           else json("""{"error":"Code falsch"}""", 403)
            "GET status" -> json(fixture("status.json"))
            "GET settings" -> json(fixture("settings_festnetz.json"))
            "PUT settings", "PUT contacts" -> json("""{"restart":true}""")
            "GET contacts" -> json(fixture("contacts.json"))
            "GET update", "POST update/check" -> json(fixture("update.json"))
            "GET clients" -> json(fixture("clients.json"))
            else -> json("""{"error":"Unbekannter Pfad"}""", 404)
        }
    }

    @Before
    fun setUp() {
        cert = HeldCertificate.Builder().commonName("omafon").build()
        server = MockWebServer().apply {
            useHttps(HandshakeCertificates.Builder().heldCertificate(cert).build().sslSocketFactory(), false)
            dispatcher = object : Dispatcher() {
                override fun dispatch(request: RecordedRequest) = respond(request)
            }
            start()
        }
        val app = ApplicationProvider.getApplicationContext<OmafonApp>()
        scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        val file = File(app.cacheDir, "geraete-${System.nanoTime()}.preferences_pb")
        store = DeviceStore(PreferenceDataStoreFactory.create(scope = scope, produceFile = { file }), PlainCipher)
        app.container = AppContainer(app, store, discovery = { found })
    }

    @After
    fun tearDown() {
        server.shutdown()
        scope.cancel()
    }

    // ------------------------------------------------------------------ Hilfen
    private fun start() = compose.setContent { OmafonTheme(dynamic = false) { OmafonNavHost() } }

    private fun waitFor(text: String, timeoutMs: Long = 8_000) {
        try {
            compose.waitUntil(timeoutMs) {
                // waitUntil schläft nur – unter Robolectric läuft der Hauptlooper dabei nicht,
                // fällige Nachrichten (Ergebnisse von Koroutinen) also selbst abarbeiten
                ShadowLooper.idleMainLooper()
                compose.onAllNodes(label(text, substring = true)).fetchSemanticsNodes().isNotEmpty()
            }
        } catch (e: ComposeTimeoutException) {
            shot("FEHLER_wartet_auf_${text.take(20).replace(Regex("[^A-Za-z0-9]"), "_")}")
            val tree = runCatching { compose.onAllNodes(isRoot()).printToString(maxDepth = 30) }
                .getOrElse { "Baum nicht lesbar: $it" }
            throw AssertionError("\"$text\" erscheint nicht. Semantik:\n$tree", e)
        }
    }

    private fun node(m: SemanticsMatcher): SemanticsNodeInteraction = compose.onNode(m, useUnmergedTree = false)

    /** Sichtbarer Text oder – wie TalkBack es liest – contentDescription. */
    private fun label(text: String, substring: Boolean = false) =
        hasText(text, substring = substring) or hasContentDescription(text, substring = substring)

    private fun button(text: String) = node(label(text) and hasClickAction())

    /** Wie ein Mensch: erst hinscrollen, falls nötig, dann tippen. */
    private fun tap(text: String) {
        val b = button(text)
        runCatching { b.performScrollTo() }               // ohne scrollbaren Rahmen: einfach tippen
        b.performClick()
    }

    private fun field(label: String) = node(hasText(label) and hasSetTextAction())

    /**
     * Fenster dieser Aktivität (sie selbst + ihre Dialoge), oberstes zuletzt – erkannt am
     * Kontext (Dialoge haben ein eigenes Fenster-Token). Robolectric lässt Fenster früherer Tests registriert,
     * und sie mitzuzeichnen hielte deren Compose-Wurzeln am Leben (nie "idle").
     */
    @Suppress("UNCHECKED_CAST")
    private fun rootViews(): List<View> {
        val wmg = Class.forName("android.view.WindowManagerGlobal")
        val instance = wmg.getMethod("getInstance").invoke(null)
        val views = wmg.getDeclaredField("mViews").apply { isAccessible = true }.get(instance) as List<View>
        fun Context.activity(): Activity? =
            generateSequence(this) { (it as? ContextWrapper)?.baseContext }.filterIsInstance<Activity>().firstOrNull()
        return views.filter { it.isShown && it.width > 0 && it.height > 0 && it.context.activity() === compose.activity }
    }

    /**
     * Bildschirmfoto durch Zeichnen der Fenster in ein Bitmap. captureToImage()
     * erzwingt unter Robolectric keinen neuen Frame und läuft in eine Zeitgrenze.
     * Dialoge (eigene Fenster) werden zentriert über die abgedunkelte Seite gelegt.
     */
    private fun shot(name: String) {
        ShadowLooper.idleMainLooper()
        compose.waitForIdle()
        val base = compose.activity.window.decorView
        val bmp = Bitmap.createBitmap(base.width, base.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        base.draw(canvas)
        for (v in rootViews().filter { it !== base }) {
            canvas.drawColor(Color.argb(110, 0, 0, 0))
            canvas.save()
            canvas.translate((base.width - v.width) / 2f, (base.height - v.height) / 2f)
            v.draw(canvas)
            canvas.restore()
        }
        val dir = File("build/screenshots").apply { mkdirs() }
        File(dir, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun paired() = runBlocking {
        store.save(SavedDevice("00000000-0000-4000-8000-000000000000", "Omafon von Oma Erika",
            server.hostName, server.port, PinningTrustManager.fingerprint(cert.certificate.encoded),
            "sip", "PLATZHALTER_TOKEN"))
    }

    private fun openDashboard() {
        paired()
        start()
        waitFor("Omafon von Oma Erika")
        node(hasText("Omafon von Oma Erika") and hasClickAction()).performClick()
        waitFor("Testansage")
    }

    // ------------------------------------------------------------------ Abläufe
    @Test
    fun pairingFromManualAddressToDashboard() {
        start()
        waitFor("Adresse eingeben")
        shot("01_geraete_leer")
        button("Adresse eingeben").performClick()
        field("Adresse").performTextInput(server.hostName)
        field("Port").performTextClearance()
        field("Port").performTextInput(server.port.toString())
        shot("02_adresse")
        tap("Weiter")
        waitFor("So geht's")
        shot("03_koppeln")

        node(hasSetTextAction()).performTextInput("000000")          // falscher Code
        tap("Koppeln")
        waitFor("Code falsch")
        shot("04_code_falsch")

        node(hasSetTextAction()).performTextClearance()
        node(hasSetTextAction()).performTextInput("123456")
        tap("Koppeln")
        waitFor("Testansage")
        waitFor("80 %")
        shot("05_uebersicht")
        compose.onNodeWithText("Omafon von Oma Erika").assertExists()  // Name aus owner_name
        val pair = writes.first { it.first == "POST pair" }.second
        assertTrue(pair, "\"client_name\"" in pair)
        val saved = runBlocking { store.all() }.single()
        assertEquals("PLATZHALTER_TOKEN", saved.token)
        assertEquals(PinningTrustManager.fingerprint(cert.certificate.encoded), saved.fingerprint)
    }

    @Test
    @Config(qualifiers = GROSS)
    fun foundInWlanThenPair() {
        start()
        found.value = listOf(FoundDevice("Omafon auf omafon", server.hostName, server.port))
        waitFor("Omafon auf omafon")
        shot("01b_gefunden")
        node(hasText("Omafon auf omafon") and hasClickAction()).performClick()
        waitFor("So geht's")
        node(hasSetTextAction()).performTextInput("123456")
        tap("Koppeln")
        waitFor("80 %")
        assertEquals(1, runBlocking { store.all() }.size)
    }

    @Test
    @Config(qualifiers = GROSS)
    fun settingsToggleAndSave() {
        openDashboard()
        button("Einstellungen").performClick()
        waitFor("Ton und Sprache")
        shot("06_einstellungen")
        node(hasScrollAction()).performScrollToNode(hasText("LED blinkt bei neuen Nachrichten"))
        node(hasText("LED blinkt bei neuen Nachrichten") and hasClickAction()).performClick()
        waitFor("Speichern (1)")
        shot("07_einstellungen_geaendert")
        button("Speichern (1)").performClick()
        waitFor("startet kurz neu")
        shot("08_gespeichert")
        val put = writes.single { it.first == "PUT settings" }.second
        assertEquals("""{"values":{"news_led":false}}""", put)
    }

    @Test
    fun contactsAndDialog() {
        openDashboard()
        tap("Kontakte")
        waitFor("+491711234567")                  // Nummer aus der Liste – "Peter" stünde auch im Platzhalter
        shot("09_kontakte")
        node(hasText("Peter") and hasClickAction()).performClick()
        waitFor("Kontakt bearbeiten")
        shot("10_kontakt_dialog")
    }

    @Test
    @Config(qualifiers = GROSS)
    fun updatesScreen() {
        openDashboard()
        button("Updates").performClick()
        waitFor("Version 0.10.0")
        shot("11_updates")
        assertTrue(compose.onAllNodes(hasText("Installieren")).fetchSemanticsNodes().isNotEmpty())
    }

    @Test
    @Config(qualifiers = GROSS)
    fun clientsScreen() {
        openDashboard()
        button("Gekoppelte Apps").performScrollTo().performClick()     // liegt unter dem sichtbaren Teil
        waitFor("dieses Handy")
        shot("12_apps")
    }

    @Test
    @Config(qualifiers = GROSS_NACHT)
    fun dashboardDark() {
        openDashboard()
        waitFor("80 %")
        shot("13_uebersicht_dunkel")
    }

    @Test
    @Config(qualifiers = "w320dp-h640dp-mdpi")
    fun dashboardSmallPhone() {
        openDashboard()
        waitFor("80 %")
        shot("14_uebersicht_klein")
    }
}
