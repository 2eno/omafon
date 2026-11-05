package de.omafon.companion.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val Green = Color(0xFF1D5C4D)
private val Amber = Color(0xFFFFD54F)

private val Light = lightColorScheme(
    primary = Green, onPrimary = Color.White,
    primaryContainer = Color(0xFFA6F2DC), onPrimaryContainer = Color(0xFF002019),
    secondary = Color(0xFF7A5900), secondaryContainer = Color(0xFFFFDF9E),
    tertiary = Color(0xFF3F6375),
)
private val Dark = darkColorScheme(
    primary = Color(0xFF8AD6C0), onPrimary = Color(0xFF00382D),
    primaryContainer = Color(0xFF00513F), onPrimaryContainer = Color(0xFFA6F2DC),
    secondary = Amber, secondaryContainer = Color(0xFF5C4200),
    tertiary = Color(0xFFA7CCE1),
)

/** Material 3, ab Android 12 mit den Farben des Hintergrundbilds (Material You). */
@Composable
fun OmafonTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val scheme = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(LocalContext.current) else dynamicLightColorScheme(LocalContext.current)
        dark -> Dark
        else -> Light
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
