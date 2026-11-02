// Omafon – Gehäuse des Handteils (parametrisch, alle Varianten)
// OpenSCAD 2021+.  Teil und Variante wählen:
//   openscad -D 'variante="hybrid"' -D 'teil="wanne"' -o wanne.stl omafon_gehaeuse.scad
//
// Teile (STL-Ausgabe liegt bereits in Druckrichtung):
//   deckel           Oberschale: Fenster für die Tastenplatte, Hörer, LED, Mikrofon
//   wanne            Unterschale: Notrufmulde, Lautsprecher, Akkufach, Ladekontakte,
//                    Kodiernut, Lautstärketasten, Pi-Halter, Schraubdome
//   tastenplatte     Schalterplatte mit Taststegen (aus omafon_tasten.scad) + Kragen
//   akkudeckel       Deckel fürs Akkufach (1 Schraube M2,5)
//   notrufklappe     Klappe über dem Notrufknopf (Scharnierstift 1,75-mm-Filament,
//                    Magnet 5 x 1 mm für den Klappenschalter)
//   lautstaerke_plus / lautstaerke_minus   seitliche Tasten (fühlbar verschieden)
//   uebersicht       zusammengebaut mit Tastenkappen (nur Vorschau)
//   schnitt          Längsschnitt zur Kontrolle (nur Vorschau)
//
// Koordinaten (Zusammenbau): x quer, y längs (+y = oben/Hörer), z Dicke
// (z = 0 Rückseite, z = Dicke Vorderseite).

include <omafon_masse.scad>
use <omafon_tasten.scad>

/* [Auswahl] */
teil = "uebersicht"; // [uebersicht, schnitt, deckel, wanne, tastenplatte, akkudeckel, notrufklappe, lautstaerke_plus, lautstaerke_minus, hoermuschel]

/* [Aufbau] */
deckel_h = 5;          // Höhe der Oberschale; der Rest gehört zur Wanne
falz_h = 1.6;          // Zentrierfalz zwischen Wanne und Deckel
falz_b = 1.0;
spalt = 0.2;
oben_bereich = 32;     // Platz über der Tastenplatte (Hörer, LED, Notruf)
kragen = 2.5;          // Kragen der Tastenplatte unter dem Deckel
fenster_spiel = 0.4;

/* [Einbauteile] – an die echten Teile anpassen */
hoerer_d = 15.6;       // Hörkapsel Ø15
mik_d = 10.2;          // Elektretkapsel Ø9,7–10
ls_d = 28.6;           // Lautsprecher Ø28 im Handteil
led_d = 5.2;
gnss_b = 25.4;         // aktive GNSS-Keramikantenne 25 x 25 (mobil/hybrid)
schraube_d = 2.9;      // M2,5 durch
einsatz_d = 3.6;       // Gewindeeinsatz M2,5 (Einschmelzmutter)
einsatz_t = 3.8;       // kurze Einsätze (M2,5 x 3,5) – der Deckel ist nur 5 mm hoch

$fn = 40;

// ------------------------------------------------------------ abgeleitete Maße
B = gehaeuse_breite; L = gehaeuse_laenge; D = gehaeuse_dicke;
ER = gehaeuse_eck_r; KR = gehaeuse_kante_r; W = gehaeuse_wand;
ZS = D - deckel_h;                       // Trennebene Wanne/Deckel
TF = tastenfront_mass();
FB = TF[0]; FH = TF[1]; RASTER = TF[2]; PLATTE = TF[3]; STEG_H = TF[4];
fenster_oben = L / 2 - oben_bereich;
fenster_y = fenster_oben - FH / 2;       // Mitte des Tastenfensters
platte_z = D - W - PLATTE;               // Unterkante Tastenplatte
mobil = variante != "festnetz";

// Akku [Breite, Länge, Dicke]: Festnetz 3000 mAh, Mobil/Hybrid 5000 mAh (Beispiel)
AK = mobil ? [60, 70, 12] : [60, 75, 10];
akku_y0 = -L / 2 + kodier_nut_l + 6;     // Unterkante Akkufach, über der Kodiernut
akku_x = -B / 2 + W + 3 + AK[0] / 2;     // links; rechts daneben Platz für Platinen
akku_oeff = [AK[0] + 6, AK[1] + 6];
akku_mitte = [akku_x, akku_y0 + AK[1] / 2];
// zwei Schrauben M2,5: unten links (neben der Kodiernut), oben rechts
akku_schrauben = [[akku_mitte[0] - 18, akku_mitte[1] - akku_oeff[1] / 2 - 3.5],
                  [akku_mitte[0] + 18, akku_mitte[1] + akku_oeff[1] / 2 + 3.5]];

// Positionen
ohr_y = L / 2 - 16;
// Erhabene Hörmuschel (eigenes Teil, am besten TPU): führt das Ohr, dichtet ab
muschel_innen = 16;      // freier Schallweg (Hörerlöcher liegen innerhalb r = 5,5)
muschel_aussen = 24;     // bleibt auf der ebenen Deckelfläche
muschel_h = 3.5;         // über der Vorderseite
muschel_einsatz = 1.0;   // so tief sitzt sie in der Mulde des Deckels
led_pos = [-25, L / 2 - 14];
gnss_pos = [22.5, L / 2 - 19];           // rechts oben unter dem Deckel (mobil/hybrid)
mik_y = -L / 2 + 11;
sos_y = L / 2 - 20;                      // Notrufmulde (Rückseite), Klappe bleibt auf der ebenen Fläche
sos_oeff = 21;                           // Kappe Ø19,2 geht durch
sos_tiefe = 13.6;                        // Kappe 9 + Schalter 6,6 – 2 mm versenkt
sos_klappe = 29;
ls_pos = [-20, -L / 2 + 22];             // Lautsprecher Rückseite unten
laut_y = [L / 2 - 55, L / 2 - 75];       // Lautstärke + / − (linke Seite)
laut_z = ZS / 2 + 2;
pi_mitte = [0, 45];                      // Pi Zero 2 W, 65 x 30
dome = [[-1, L / 2 - 9], [1, L / 2 - 9], [-1, -L / 2 + 9], [1, -L / 2 + 9]];
dom_x = B / 2 - 7;

// ------------------------------------------------------------ Grundformen
module rrect(w, d, r) { offset(r) square([w - 2 * r, d - 2 * r], center = true); }

module ecke(r, kr, h) {
    rotate_extrude($fn = 40) hull() {
        square([0.01, h]);
        translate([r - kr, kr]) circle(kr, $fn = 24);
        translate([r - kr, h - kr]) circle(kr, $fn = 24);
    }
}

// Außenkörper, um "off" nach innen versetzt (für Innenraum/Falz)
module koerper(off = 0) {
    hull() for (x = [-1, 1], y = [-1, 1])
        translate([x * (B / 2 - ER), y * (L / 2 - ER), off])
            ecke(ER - off, max(0.6, KR - off), D - 2 * off);
}

module schale() { difference() { koerper(0); koerper(W); } }

module zwischen(z0, z1) { translate([-B, -L, z0]) cube([2 * B, 2 * L, z1 - z0]); }

// ------------------------------------------------------------ Deckel (Oberschale)
module deckel() {
    difference() {
        union() {
            intersection() { schale(); zwischen(ZS, D + 1); }
        // Hörer-, Mikrofon- und LED-Halter unter der Oberfläche
            translate([0, ohr_y, D - W - 2.5]) ring(hoerer_d, 2.5);
            translate([0, mik_y, D - W - 2.5]) ring(mik_d, 2.5);
            translate([led_pos[0], led_pos[1], D - W - 4]) ring(led_d, 4);
            if (mobil) translate([gnss_pos[0], gnss_pos[1], D - W - 2]) linear_extrude(2)
                difference() { square(gnss_b + 1.6, center = true); square(gnss_b, center = true); }
            // Schraubdome mit Gewindeeinsatz
            for (d = dome) translate([d[0] * dom_x, d[1], ZS + 0.1]) cylinder(d = 7, h = D - W - ZS - 0.1 + 0.01);
            // Rasthaken für die Tastenplatte (oben/unten)
            for (s = [-1, 1], x = [-40, 0, 40]) rasthaken(x, fenster_y + s * (FH / 2 + kragen + 0.2), s);
        }
        // Ringmulde für die Hörmuschel (Vorderseite bleibt plan fürs Druckbett)
        translate([0, ohr_y, D - muschel_einsatz]) difference() {
            cylinder(d = muschel_aussen + 0.4, h = muschel_einsatz + 1, $fn = 64);
            translate([0, 0, -1]) cylinder(d = muschel_innen - 0.4, h = muschel_einsatz + 3, $fn = 64);
        }
        // Tastenfenster
        translate([0, fenster_y, D - W - 1]) linear_extrude(W + 2) rrect(FB + fenster_spiel, FH + fenster_spiel, 1);
        // Hörer-Löcher, Mikrofon-Löcher, LED
        for (p = loch_muster(5.5, 1.6)) translate([p[0], ohr_y + p[1], D - W - 1]) cylinder(d = 1.6, h = W + 2, $fn = 12);
        for (p = loch_muster(3, 1.2)) translate([p[0], mik_y + p[1], D - W - 1]) cylinder(d = 1.2, h = W + 2, $fn = 12);
        translate([led_pos[0], led_pos[1], D - W - 5]) cylinder(d = led_d, h = W + 6);
        // Falz-Aufnahme (Wand innen dünner)
        intersection() { difference() { koerper(W - falz_b - spalt); koerper(W + 0.5); } zwischen(ZS - 0.01, ZS + falz_h); }
        // Einsätze in den Domen
        for (d = dome) translate([d[0] * dom_x, d[1], ZS - 0.01]) cylinder(d = einsatz_d, h = min(einsatz_t, D - ZS - 1.2));
    }
}

module ring(innen, h, breite = 1.6) {
    difference() { cylinder(d = innen + 2 * breite, h = h); translate([0, 0, -0.01]) cylinder(d = innen, h = h + 0.02); }
}

// Löcher auf Kreisen (Radius bis r, Abstand a)
function loch_muster(r, a) = [for (x = [-r : a * 1.6 : r + 0.01], y = [-r : a * 1.6 : r + 0.01])
    if (x * x + y * y <= r * r) [x, y]];

module rasthaken(x, y, s) {   // s = +1 oben, −1 unten; Haken greift unter den Kragen
    translate([x - 3, y + (s > 0 ? 0 : -1.2), platte_z - 0.9]) cube([6, 1.2, D - W - platte_z + 0.9]);
    hull() {
        translate([x - 3, y + (s > 0 ? -0.8 : 0), platte_z - 0.9]) cube([6, 0.8 + 1.2, 0.5]);
        translate([x - 3, y + (s > 0 ? 0 : -0.01), platte_z - 0.01]) cube([6, 1.21, 0.01]);
    }
}

// ------------------------------------------------------------ Wanne (Unterschale)
module wanne() {
    difference() {
        union() {
            intersection() { schale(); zwischen(-1, ZS); }
            // Zentrierfalz
            intersection() { difference() { koerper(W - falz_b); koerper(W); } zwischen(ZS - 0.01, ZS + falz_h - 0.2); }
            // Schraubdome
            for (d = dome) translate([d[0] * dom_x, d[1], 0]) intersection() { cylinder(d = 7, h = ZS); koerper(0.01); }
            sos_mulde_koerper();
            // Lautsprecherhalter
            translate([ls_pos[0], ls_pos[1], W - 0.01]) ring(ls_d, 3);
            // Dom für die Akkudeckelschraube
            for (a = akku_schrauben) translate([a[0], a[1], 0]) cylinder(d = 7, h = W + 6);
            // Verstärkung an Ladekontakten und Kodiernut
            intersection() {
                koerper(0.01);
                union() {
                    translate([-24, -L / 2, D / 2 - 7]) cube([48, W + 2.5, 14]);
                    translate([-(kodier_b / 2 + 2.4), -L / 2, 0]) cube([kodier_b + 4.8, kodier_nut_l + 2, kodier_t + 0.6 + 1.4]);
                }
            }
            // Pi Zero 2 W: 4 Abstandshalter (M2,5), Lochabstand 58 x 23
            for (x = [-29, 29], y = [-11.5, 11.5]) translate([pi_mitte[0] + x, pi_mitte[1] + y, W - 0.01])
                difference() { cylinder(d = 5.5, h = 3); cylinder(d = 2.2, h = 4); }
            lautstaerke_fuehrungen();
            // Kabelbinder-Brücken im Platinenfeld rechts neben dem Akku
            for (y = [akku_y0 + 10, akku_y0 + 40]) translate([B / 2 - W - 14, y, W - 0.01]) kabelbinder_bruecke();
        }
        // Notrufmulde: Öffnung, Klappenvertiefung, Scharnier, Schalteröffnung, Reedkontakt
        sos_mulde_aussparung();
        // Lautsprechergitter
        for (p = loch_muster(10, 1.8)) translate([ls_pos[0] + p[0], ls_pos[1] + p[1], -1]) cylinder(d = 1.8, h = W + 2, $fn = 12);
        // Akkufach: Öffnung + Falz für den Deckel
        akku_aussparung();
        for (a = akku_schrauben) {
            translate([a[0], a[1], 1.2]) cylinder(d = einsatz_d, h = W + 6);
            translate([a[0], a[1], -1]) cylinder(d = schraube_d, h = 4);
        }
        // Ladekontakte unten: Messingscheiben, Drahtlöcher, Stahlscheiben über den Magneten
        for (i = [0 : kontakt_pins - 1]) translate([(i - (kontakt_pins - 1) / 2) * kontakt_raster, -L / 2 - 1, D / 2])
            rotate([-90, 0, 0]) { cylinder(d = kontakt_pad_d + 0.3, h = 1 + 1.2); cylinder(d = 1.6, h = 10, $fn = 12); }
        for (s = [-1, 1]) translate([s * magnet_x(), -L / 2 - 1, D / 2]) rotate([-90, 0, 0]) cylinder(d = magnet_d, h = 1 + 1.6);
        // Kodiernut hinten (passt zur Rippe im Ladeschacht)
        translate([-(kodier_b + 0.8) / 2, -L / 2 - 1, -1]) cube([kodier_b + 0.8, kodier_nut_l + 1, kodier_t + 0.6 + 1]);
        // Lautstärketasten links
        for (y = laut_y) translate([-B / 2 - 1, y, laut_z]) rotate([0, 90, 0]) linear_extrude(W + 2) rrect(8, 8, 1.5);
        // Dome: Schraube von hinten, Senkung für den Kopf
        for (d = dome) translate([d[0] * dom_x, d[1], -1]) {
            cylinder(d = schraube_d, h = ZS + 2);
            cylinder(d = 5, h = 1 + 2.5);
        }
    }
}

module sos_mulde_koerper() {
    // Rohr der Mulde + Verstärkung um die Klappe
    translate([0, sos_y, 0]) {
        intersection() {
            koerper(0.01);
            translate([0, 0, 0]) linear_extrude(4.6) rrect(sos_klappe + 8, sos_klappe + 8, 3);
        }
        linear_extrude(sos_tiefe + PLATTE) rrect(sos_oeff + 3.2, sos_oeff + 3.2, 3);
    }
}

module sos_mulde_aussparung() {
    translate([0, sos_y, 0]) {
        // Mulde bis zur Schalterplatte
        translate([0, 0, -1]) linear_extrude(sos_tiefe + 1) rrect(sos_oeff, sos_oeff, 2);
        // MX-Ausschnitt in der Schalterplatte (1,5 mm)
        translate([0, 0, sos_tiefe - 0.01]) linear_extrude(PLATTE + 1) square(14, center = true);
        // Klappenvertiefung, Griffmulde unten
        translate([0, 0, -1]) linear_extrude(1 + 1.8) rrect(sos_klappe, sos_klappe, 3);
        translate([0, -sos_klappe / 2, -1]) cylinder(d = 12, h = 1 + 1.8);
        // Scharnierkanal oben + Stiftloch (Filament 1,75 mm)
        translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) {
            cylinder(d = 3.9, h = sos_klappe + 0.4, center = true);
            cylinder(d = 1.85, h = sos_klappe + 8, center = true, $fn = 16);
        }
        // Reedkontakt längs neben der Mulde (Magnet in der Klappe darüber)
        translate([13.4, -14, 3.4]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 22, $fn = 16);
    }
}

module akku_aussparung() {
    translate([akku_mitte[0], akku_mitte[1], -1]) {
        linear_extrude(W + 2) rrect(akku_oeff[0], akku_oeff[1], 3);
        // Falz außen: Deckel 1,2 mm, oben und unten je 6 mm länger (Schrauben)
        linear_extrude(1 + 1.2) rrect(akku_oeff[0] + 4, akku_oeff[1] + 4 + 12, 4);
    }
}

module lautstaerke_fuehrungen() {
    // Schienen für eine Lochrasterplatine 14 x 16 mit 6x6-Taster
    x1 = -B / 2 + W + 1.2;
    for (y = laut_y, s = [-1, 1]) translate([x1 + 5.2, y + s * 7.9 - (s > 0 ? 0 : 1.6), W - 0.01])
        difference() {
            cube([3.2, 1.6, laut_z + 8 - W]);
            translate([-0.01, s > 0 ? -0.01 : 0.6, laut_z - 8 - W]) cube([1.7, 1.01, laut_z + 8]);
        }
}

module kabelbinder_bruecke() {
    difference() { translate([-5, -2, 0]) cube([10, 4, 3]); translate([-3.5, -3, -0.01]) cube([7, 6, 1.8]); }
}

// ------------------------------------------------------------ Kleinteile
module tastenplatte() {
    union() {
        front();
        translate([0, -2.5 * RASTER, 0]) linear_extrude(PLATTE) difference() {
            rrect(FB + 2 * kragen, FH + 2 * kragen, 2);
            square([FB - 0.2, FH - 0.2], center = true);
        }
    }
}

module akkudeckel() {
    // im Zusammenbau-Koordinatensystem; Außenfläche z = 0
    translate([akku_mitte[0], akku_mitte[1], 0]) difference() {
        union() {
            linear_extrude(1.2 - 0.05) rrect(akku_oeff[0] + 3.6, akku_oeff[1] + 3.6 + 12, 3.8);
            linear_extrude(W) rrect(akku_oeff[0] - 0.4, akku_oeff[1] - 0.4, 2.8);
        }
        for (a = akku_schrauben) translate([a[0] - akku_mitte[0], a[1] - akku_mitte[1], -0.01]) {
            cylinder(d = schraube_d, h = 5);
            cylinder(d1 = 5.2, d2 = schraube_d, h = 1.2);    // Senkkopf
        }
        for (i = [-2 : 2]) translate([i * 4, akku_oeff[1] / 2 - 10, -0.01]) cube([1.2, 14, 0.5], center = true);
    }
}

module notrufklappe() {
    // Zusammenbau-Koordinaten: liegt in der Vertiefung um die Notrufmulde
    translate([0, sos_y, 0]) difference() {
        union() {
            translate([0, 0, 0.05]) linear_extrude(1.7) rrect(sos_klappe - 0.6, sos_klappe - 0.6, 2.7);
            translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) cylinder(d = 3.4, h = sos_klappe - 0.8, center = true);
            // Noppen außen: fühlbar "hier ist der Notruf"
            for (x = [-7, 0, 7], y = [-7, 0, 7]) translate([x, y, 0.06]) scale([1, 1, 0.6]) sphere(d = 3, $fn = 16);
        }
        translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) cylinder(d = 1.95, h = sos_klappe + 1, center = true, $fn = 16);
        // Magnet 5 x 1 innen, über dem Reedkontakt
        translate([11.4, -6, 1.75 - 1.1]) cylinder(d = 5.2, h = 1.2);
    }
}

module hoermuschel() {
    // Druckrichtung: flache Unterseite aufs Bett, Rundung oben
    r1 = muschel_innen / 2; r2 = muschel_aussen / 2; h = muschel_einsatz + muschel_h; k = 1.6;
    rotate_extrude($fn = 64) hull() {
        translate([r1, 0]) square([r2 - r1, 0.01]);
        translate([r1 + k, h - k]) circle(k, $fn = 24);
        translate([r2 - k, h - k]) circle(k, $fn = 24);
        translate([r1, 0]) square([0.01, h - k]);
        translate([r2 - 0.01, 0]) square([0.01, h - k]);
    }
}

module lautstaerke(plus) {
    // Druckrichtung: Kragen unten
    difference() {
        union() {
            linear_extrude(1.2) rrect(10.5, 10.5, 2);
            linear_extrude(1.2 + W + 1.3) rrect(7.4, 7.4, 1.2);
            // Zeichen erhaben: + (Kreuz) oder − (Balken)
            translate([0, 0, 1.2 + W + 1.3 - 0.01]) linear_extrude(0.8) {
                square([5, 1.4], center = true);
                if (plus) square([1.4, 5], center = true);
            }
        }
    }
}

// ------------------------------------------------------------ Vorschau
module zusammenbau(kappen = true) {
    color("#e8e8e8") wanne();
    color("#d0d0d0") deckel();
    color("#222") translate([0, ohr_y, D - muschel_einsatz]) hoermuschel();
    color("#333") translate([0, fenster_y + 2.5 * RASTER, platte_z]) tastenplatte();
    color("#cc0000") notrufklappe();
    color("#bbb") akkudeckel();
    for (y = laut_y) color("#444") translate([-B / 2 - 1.3, y, laut_z]) rotate([0, -90, 0]) rotate([0, 0, 0])
        translate([0, 0, -1.2 - W]) lautstaerke(y == laut_y[0]);
    if (kappen) {
        TP = tastenpositionen();
        for (p = TP) translate([p[0] * RASTER, fenster_y + 2.5 * RASTER + p[1] * RASTER, platte_z + PLATTE + 5])
            kappe_fuer(p[2]);
    }
}

// Druckrichtung: größte ebene Fläche aufs Bett
module druck(name) {
    if (name == "deckel") translate([0, 0, D]) mirror([0, 0, 1]) deckel();
    else if (name == "wanne") wanne();
    else if (name == "tastenplatte") tastenplatte();
    else if (name == "akkudeckel") akkudeckel();
    // stehend auf der Scharnierkante: Noppen außen und Röhrchen innen brauchen so keine Stützen
    else if (name == "notrufklappe") translate([0, 0, sos_klappe / 2 - 0.2]) rotate([-90, 0, 0]) translate([0, -sos_y, 0]) notrufklappe();
    else if (name == "lautstaerke_plus") lautstaerke(true);
    else if (name == "lautstaerke_minus") lautstaerke(false);
    else if (name == "hoermuschel") hoermuschel();
}

echo(str("Variante ", variante, ": Handteil ", B, " x ", L, " x ", D, " mm, Akku ", AK[0], " x ", AK[1], " x ", AK[2]));

if (teil == "uebersicht") zusammenbau();
else if (teil == "schnitt") intersection() { zusammenbau(false); translate([0, -L, -1]) cube([B, 2 * L, D + 30]); }
else druck(teil);
