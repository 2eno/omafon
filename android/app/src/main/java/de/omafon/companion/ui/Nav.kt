package de.omafon.companion.ui

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import de.omafon.companion.ui.device.ClientsScreen
import de.omafon.companion.ui.device.ContactsScreen
import de.omafon.companion.ui.device.DashboardScreen
import de.omafon.companion.ui.device.SettingsScreen
import de.omafon.companion.ui.device.UpdateScreen
import de.omafon.companion.ui.devices.DevicesScreen
import de.omafon.companion.ui.devices.PairScreen

object Routes {
    const val DEVICES = "devices"
    const val PAIR = "pair?host={host}&port={port}&name={name}"
    fun pair(host: String, port: Int, name: String = "") =
        "pair?host=${Uri.encode(host)}&port=$port&name=${Uri.encode(name)}"
    const val DEVICE = "device/{id}"
    fun device(id: String, page: String = "") = "device/${Uri.encode(id)}" + if (page.isEmpty()) "" else "/$page"
}

@Composable
fun OmafonNavHost() {
    val nav = rememberNavController()
    val back: () -> Unit = { nav.popBackStack() }
    val idArg = listOf(navArgument("id") { type = NavType.StringType })
    NavHost(nav, startDestination = Routes.DEVICES) {
        composable(Routes.DEVICES) {
            DevicesScreen(
                onOpen = { nav.navigate(Routes.device(it)) },
                onPair = { host, port, name -> nav.navigate(Routes.pair(host, port, name)) },
            )
        }
        composable(
            Routes.PAIR,
            arguments = listOf(
                navArgument("host") { type = NavType.StringType },
                navArgument("port") { type = NavType.IntType },
                navArgument("name") { type = NavType.StringType; defaultValue = "" },
            ),
        ) { entry ->
            val a = entry.arguments!!
            PairScreen(
                host = a.getString("host")!!, port = a.getInt("port"), name = a.getString("name").orEmpty(),
                onBack = back,
                onPaired = { id ->
                    nav.navigate(Routes.device(id)) { popUpTo(Routes.DEVICES) }
                },
            )
        }
        composable(Routes.DEVICE, arguments = idArg) { entry ->
            val id = entry.arguments!!.getString("id")!!
            DashboardScreen(
                deviceId = id, onBack = back,
                onOpen = { page -> nav.navigate(Routes.device(id, page)) },
                onRepair = { host, port, name -> nav.navigate(Routes.pair(host, port, name)) },
                onRemoved = { nav.popBackStack(Routes.DEVICES, inclusive = false) },
            )
        }
        composable("device/{id}/settings", arguments = idArg) {
            SettingsScreen(it.arguments!!.getString("id")!!, onBack = back)
        }
        composable("device/{id}/contacts", arguments = idArg) {
            ContactsScreen(it.arguments!!.getString("id")!!, onBack = back)
        }
        composable("device/{id}/update", arguments = idArg) {
            UpdateScreen(it.arguments!!.getString("id")!!, onBack = back)
        }
        composable("device/{id}/clients", arguments = idArg) {
            ClientsScreen(it.arguments!!.getString("id")!!, onBack = back,
                onUnpairedSelf = { nav.popBackStack(Routes.DEVICES, inclusive = false) })
        }
    }
}
