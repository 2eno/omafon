package de.omafon.companion

import de.omafon.companion.data.Contact
import de.omafon.companion.data.SettingItem
import de.omafon.companion.data.stateLabel
import de.omafon.companion.ui.device.ContactRules
import de.omafon.companion.ui.device.formatNumber
import de.omafon.companion.ui.device.numberJson
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RulesTest {
    @Test fun numbersAreCleanedLikeOnTheOmafon() {
        assertEquals("+4930123456", ContactRules.cleanNumber("+49 (30) 123-456"))
        assertTrue(ContactRules.problems(Contact("Peter", "0171 / 1234567"), emptyList()).isEmpty())
        assertTrue(ContactRules.problems(Contact("Peter", "abc"), emptyList()).isNotEmpty())
        assertTrue(ContactRules.problems(Contact("", "0171"), emptyList()).isNotEmpty())
    }

    @Test fun speedDialAndEmergencyMustBeUnique() {
        val others = listOf(Contact("Maria", "0301", speedDial = 2, emergency = 1))
        assertTrue(ContactRules.problems(Contact("Peter", "0171", speedDial = 2), others).any { "Kurzwahl" in it })
        assertTrue(ContactRules.problems(Contact("Peter", "0171", emergency = 1), others).any { "Notruf" in it })
        assertTrue(ContactRules.problems(Contact("Peter", "0171", speedDial = 3, emergency = 2), others).isEmpty())
    }

    @Test fun spokenWords() {
        assertEquals(listOf("peter", "sohn"), ContactRules.words("Peter, Sohn"))
        assertTrue(ContactRules.problems(Contact("P", "0171", spoken = listOf("p3ter")), emptyList()).isNotEmpty())
    }

    @Test fun numbersKeepTheirType() {
        val i = SettingItem("volume", "int", "Lautstärke", min = 1.0, max = 5.0, step = 1.0)
        val f = SettingItem("speech_rate", "float", "Tempo", unit = "s")
        assertEquals(JsonPrimitive(3), numberJson(i, 3.0000001))
        assertEquals(JsonPrimitive(1.3), numberJson(f, 1.30000004))
        assertEquals("3", formatNumber(i, 3.0))
    }

    @Test fun statesFromPhonePy() {
        // Namen aus class S in omafon/phone.py
        listOf("idle", "entry", "voice_dial", "outgoing", "in_call", "ringing", "reading", "dictate", "confirm", "sos")
            .forEach { assertTrue(it, stateLabel(it) != it) }
    }
}
