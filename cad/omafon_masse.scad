// Omafon – gemeinsame Maße für Gehäuse und Ladeschale.
// Wird mit "include" eingebunden. Ändern nur hier, dann passen Telefon und
// Schale weiter zusammen. Variante per -D 'variante="hybrid"' wählen.

/* [Variante] */
variante = "festnetz"; // [festnetz, mobil, hybrid]

// Außenmaße des Handteils (ohne Tastenkappen). Die Breite/Länge folgen aus der
// Tastenfront (3 x 24 mm Raster + Rand = 84 x 156 mm) plus Rahmen.
gehaeuse_breite = 94;
gehaeuse_laenge = 210;
// Festnetz ohne Modem ist dünner; Mobil/Hybrid tragen den SIM7600-HAT auf dem Pi.
function dicke_fuer(v) = v == "festnetz" ? 30 : 36;
gehaeuse_dicke = dicke_fuer(variante);
gehaeuse_eck_r = 10;     // Ecken in der Draufsicht
gehaeuse_kante_r = 5;    // Rundung Vorder-/Rückseite zu den Seiten
gehaeuse_wand = 2.2;

// Ladekontakte (Unterseite Handteil <-> Federkontakte in der Schale)
kontakt_pins = 5;        // 1 +5V, 2 GND, 3 GND, 4 LS+, 5 LS-  (von links, Blick auf die Vorderseite)
kontakt_raster = 5.0;
kontakt_pad_d = 5.0;     // Messingscheiben im Handteil
magnet_d = 8.2;          // 2 Magnete (Schale) / 2 Stahlscheiben (Handteil)
magnet_h = 3.2;
function magnet_x() = (kontakt_pins * kontakt_raster + 6 - 0.4) / 2 + 1;

// Kodierung: Rippe hinten im Schacht <-> Nut hinten am Handteil
kodier_b = 6;
kodier_t = 2.5;
kodier_nut_l = 40;       // Nutlänge am Handteil ab Unterkante
