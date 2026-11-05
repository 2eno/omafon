package de.omafon.companion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import de.omafon.companion.ui.OmafonNavHost
import de.omafon.companion.ui.theme.OmafonTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            OmafonTheme {
                OmafonNavHost()
            }
        }
    }
}
