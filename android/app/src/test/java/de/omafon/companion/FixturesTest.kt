package de.omafon.companion

import de.omafon.companion.data.ApiJson
import de.omafon.companion.data.ClientList
import de.omafon.companion.data.ContactList
import de.omafon.companion.data.DeviceInfo
import de.omafon.companion.data.DeviceStatus
import de.omafon.companion.data.PairResponse
import de.omafon.companion.data.SettingsSchema
import de.omafon.companion.data.UpdateInfo
import de.omafon.companion.ui.device.asDouble
import de.omafon.companion.ui.device.asHours
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Die JSON-Dateien erzeugt das Omafon selbst (python3 -m tools.api_fixtures);
 * tests/test_admin.py prüft auf der Python-Seite, dass sie aktuell sind.
 */
class FixturesTest {
    private fun read(name: String): String =
        requireNotNull(javaClass.classLoader!!.getResource("api/$name")) { "api/$name fehlt" }.readText()

    @Test fun info() {
        val i = ApiJson.decodeFromString<DeviceInfo>(read("info.json"))
        assertEquals("omafon", i.app)
        assertEquals(1, i.api)
        assertEquals("sip", i.variant)
        assertTrue(i.pairingOpen)
    }

    @Test fun pair() {
        val p = ApiJson.decodeFromString<PairResponse>(read("pair.json"))
        assertTrue(p.token.isNotEmpty())
        assertEquals(36, p.deviceId.length)
    }

    @Test fun status() {
        val s = ApiJson.decodeFromString<DeviceStatus>(read("status.json"))
        assertEquals("idle", s.state)
        assertNotNull(s.battery)
        val u = requireNotNull(s.update)
        assertTrue(u.updateAvailable)
        assertEquals("0.10.0", u.available?.version)
        assertFalse(u.busy)
    }

    @Test fun update() {
        val u = ApiJson.decodeFromString<UpdateInfo>(read("update.json"))
        assertTrue(u.configured)
        assertFalse(u.canRollback)
    }

    @Test fun settingsFestnetz() {
        val s = ApiJson.decodeFromString<SettingsSchema>(read("settings_festnetz.json"))
        assertEquals("sip", s.variant)
        val items = s.groups.flatMap { it.items }.associateBy { it.key }
        assertFalse(s.groups.any { it.title == "Hybrid" })
        val types = items.values.map { it.type }.toSet()
        assertTrue("Die App kennt alle Typen: $types",
            setOf("int", "float", "bool", "choice", "text", "secret", "hours").containsAll(types))
        val pw = items.getValue("sip.password")
        assertNull(pw.value)
        assertTrue(pw.isSet)
        assertEquals(22 to 7, items.getValue("quiet_hours").value.asHours())
        val vol = items.getValue("volume")
        assertTrue(vol.live)
        assertEquals(4.0, vol.value.asDouble())
        assertTrue(items.getValue("default_route").choices.isNotEmpty())
    }

    @Test fun settingsHybrid() {
        val s = ApiJson.decodeFromString<SettingsSchema>(read("settings_hybrid.json"))
        assertEquals("hybrid", s.variant)
        assertTrue(s.groups.any { it.title == "Hybrid" })
    }

    @Test fun contacts() {
        val c = ApiJson.decodeFromString<ContactList>(read("contacts.json")).contacts
        assertTrue(c.isNotEmpty())
        assertTrue(c.any { it.emergency != null })
        assertTrue(c.any { it.speedDial != null })
        // telegram_chat_id: null darf nicht stören
        assertEquals("", c.first().telegramText)
    }

    @Test fun clients() {
        val c = ApiJson.decodeFromString<ClientList>(read("clients.json")).clients
        assertTrue(c.single().isThis)
    }
}
