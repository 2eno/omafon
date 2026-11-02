// Omafon Festnetz – Ladeschale mit Lautsprecher (parametrisch)
// OpenSCAD 2021+.  Einzelteil über "teil" wählen:
//   openscad -D 'teil="schale"' -o ladeschale.stl omafon_ladeschale.scad
//
// Aufbau (siehe docs/festnetz-hardware.md):
//   schale          Gehäuse mit Steckschacht, Einführtrichter, Lautsprecherkammer
//   boden           Bodenplatte mit Gewichtskammer und Gummifüßen
//   kontakttraeger  Einsatz für 5 Federkontakte (Pogo-Pins) im Schachtboden
//   handteil_kontakte  Kontaktplatte für die Unterseite des Telefons
//   uebersicht      alles zusammen (Vorschau)
//
// Kontaktbelegung (von links, Blick von vorn): 1 +5V  2 GND  3 GND  4 LS+  5 LS-
// Die Kodierrippe hinten im Schacht passt nur zur Nut im Handteil – das Telefon
// kann nicht verkehrt herum eingesteckt werden und findet die Kontakte selbst.
//
// Druck: PETG, 0,2 mm, 3 Wände. Schale mit der Öffnung nach oben, ohne Stützen.

include <omafon_masse.scad>   // Handteil-Maße, Kontakte, Kodierung (gemeinsam mit dem Gehäuse)

/* [Auswahl] */
teil = "uebersicht"; // [uebersicht, schale, boden, kontakttraeger, handteil_kontakte]

/* [Handteil] – an das echte Gehäuse anpassen */
hand_b = gehaeuse_breite;   // Breite des Telefons (aus omafon_masse.scad)
hand_t = gehaeuse_dicke;    // Dicke je Variante
hand_r = gehaeuse_kante_r;  // Rundung im Querschnitt
spiel = 1.2;         // Luft rundherum
neigung = 15;        // Telefon lehnt nach hinten (Grad)
trichter = 7;        // Einführschräge oben je Seite – findet man blind
trichter_h = 10;     // Höhe der Einführschräge
// Kodierrippe hinten: kodier_b x kodier_t aus omafon_masse.scad (Nut im Handteil)

/* [Gehäuse] */
hoehe_vorn = 48;     // Einstecktiefe ergibt sich daraus (Echo in der Konsole)
wand = 2.4;
eck_r = 12;

/* [Lautsprecher] */
ls_d = 50;           // Ø Korb, z. B. 50-mm-Breitbänder 8 Ω
ls_tiefe = 16;       // Höhe der Schallführung unter dem Deckel
ls_loch = 3;         // Grilllöcher

/* [Kontakte] */
pins = kontakt_pins;
pin_raster = kontakt_raster;
pin_d = 2.05;        // Bohrung für Federkontakt Ø2 mm (Presspassung)
pad_d = kontakt_pad_d;
// Magnete magnet_d x magnet_h aus omafon_masse.scad

/* [Anschluss] */
usbc_b = 13;         // USB-C-Buchsenplatine (Breakout)
usbc_h = 7;

/* [Boden] */
boden_h = 4;
gewicht_h = 10;      // Kammer für Stahlscheiben (Standfestigkeit)

// Grundfläche wächst mit dem Handteil (Schacht + Trichter + Wände + Rand / Lautsprecher dahinter)
breite = hand_b + 2 * spiel + 2 * trichter + 2 * wand + 24;
tiefe = 18 + (hand_t + 2 * spiel) + trichter + 3 * wand
        + (hoehe_vorn + 10 - (boden_h + 6)) * tan(neigung) + ls_d + 6;

$fn = 64;

schacht_b = hand_b + 2 * spiel;
schacht_t = hand_t + 2 * spiel;
schacht_x = 0;
schacht_y = -tiefe / 2 + 18 + schacht_t / 2;   // vorne, Lautsprecher dahinter
schacht_boden = boden_h + 6;
hoehe_hinten = hoehe_vorn + 10;
// Lautsprecher hinter dem gekippten Schacht (Kippversatz oben mit einrechnen)
ls_y = schacht_y + schacht_t / 2 + trichter + wand + (hoehe_hinten - schacht_boden) * tan(neigung) + ls_d / 2 + wand + 1;
assert(ls_y + ls_d / 2 + wand < tiefe / 2 - wand, "Lautsprecher passt nicht hinter den Schacht – tiefe erhöhen");
// Höhe der schrägen Oberseite an Stelle y
function oben_z(y) = hoehe_vorn + (y + tiefe / 2 - eck_r) / (tiefe - 2 * eck_r) * (hoehe_hinten - hoehe_vorn);
ls_top = oben_z(ls_y);
// Einstecktiefe entlang der Schachtachse bis zur Oberkante
einsteck = (oben_z(schacht_y) - schacht_boden) / cos(neigung);
echo(str("Einstecktiefe ", round(einsteck), " mm, davon Trichter ", trichter_h, " mm"));

module rrect(w, d, r) { offset(r) square([w - 2 * r, d - 2 * r], center = true); }

// Oberseite: vorn niedrig, hinten höher (Pult)
module pult(r, hv, hh, z0 = 0) {   // Eckzylinder: vorn hv hoch, hinten hh
    hull() for (x = [-1, 1], y = [-1, 1])
        translate([x * (breite / 2 - eck_r), y * (tiefe / 2 - eck_r), z0])
            cylinder(r = r, h = (y < 0 ? hv : hh) - z0);
}
module aussenform() { pult(eck_r, hoehe_vorn, hoehe_hinten); }

module schacht_form() {
    // gekippter Schacht; Trichter oben
    translate([schacht_x, schacht_y, schacht_boden]) rotate([-neigung, 0, 0]) {
        difference() {
            union() {
                linear_extrude(einsteck + 30) rrect(schacht_b, schacht_t, hand_r + spiel);
                translate([0, 0, einsteck - trichter_h]) hull() {
                    linear_extrude(0.01) rrect(schacht_b, schacht_t, hand_r + spiel);
                    translate([0, 0, trichter_h]) linear_extrude(0.01)
                        rrect(schacht_b + 2 * trichter, schacht_t + 2 * trichter, hand_r + trichter);
                    translate([0, 0, trichter_h + 30]) linear_extrude(0.01)
                        rrect(schacht_b + 2 * trichter, schacht_t + 2 * trichter, hand_r + trichter);
                }
            }
            // Kodierrippe hinten mittig
            translate([-kodier_b / 2, schacht_t / 2 - kodier_t, -1]) cube([kodier_b, kodier_t + 0.01, einsteck - trichter_h + 1]);
        }
    }
}

module kontakt_tasche() {   // Aussparung für den Kontaktträger im Schachtboden
    translate([schacht_x, schacht_y, schacht_boden - 6]) rotate([-neigung, 0, 0])
        translate([0, 0, -0.01]) linear_extrude(6.5) rrect(pins * pin_raster + 6, 9, 1.5);
}

module grill() {
    for (x = [-ls_d / 2 + 4 : ls_loch * 1.8 : ls_d / 2 - 4], y = [-ls_d / 2 + 4 : ls_loch * 1.8 : ls_d / 2 - 4])
        if (x * x + y * y < (ls_d / 2 - 5) * (ls_d / 2 - 5))
            translate([x, ls_y + y, ls_top - 6]) cylinder(d = ls_loch, h = 30);
}

module schale() {
    difference() {
        aussenform();
        // innen hohl (oben geschlossen), unten offen für den Boden
        pult(eck_r - wand, hoehe_vorn - wand, hoehe_hinten - wand, -0.01);
        schacht_form();
        grill();
        // USB-C hinten unten
        translate([0, tiefe / 2 - wand / 2, boden_h + usbc_h / 2 + 2]) cube([usbc_b - 3.5, wand * 3, usbc_h - 3], center = true);
        // Tastmarke vorn: drei Rillen = "hier ist vorn"
        for (x = [-8, 0, 8]) translate([x, -tiefe / 2 - 0.5, hoehe_vorn - 10]) cube([2, 2, 8], center = true);
    }
    // Schacht als Wanne innen wieder schließen (Wände um den Schacht)
    difference() {
        intersection() {
            aussenform();
            translate([schacht_x, schacht_y, schacht_boden - 6]) rotate([-neigung, 0, 0])
                linear_extrude(einsteck + 40) rrect(schacht_b + 2 * trichter + 2 * wand, schacht_t + 2 * trichter + 2 * wand, hand_r + trichter + wand);
        }
        schacht_form();
        kontakt_tasche();
    }
    // Schallführung: Ring unter dem Grill, geht in den schrägen Deckel über.
    // Lautsprecher von unten bis an den Deckel schieben, mit Heißkleber fixieren.
    // Das geschlossene Gehäuse (mit Boden) ist das Rückvolumen.
    intersection() {
        aussenform();
        translate([0, ls_y, ls_top - ls_tiefe]) difference() {
            cylinder(d = ls_d + 0.6 + 2 * wand, h = ls_tiefe + 20);
            translate([0, 0, -1]) cylinder(d = ls_d + 0.6, h = ls_tiefe + 30);
        }
    }
    // USB-C-Halter
    translate([0, tiefe / 2 - wand - 6, boden_h]) difference() {
        translate([0, 0, (usbc_h + 4) / 2]) cube([usbc_b + 4, 12, usbc_h + 4], center = true);
        translate([0, 1, usbc_h / 2 + 2]) cube([usbc_b + 0.4, 14, 1.8], center = true); // Platinennut
    }
}

module boden() {
    difference() {
        linear_extrude(boden_h) rrect(breite - 2 * wand - 0.6, tiefe - 2 * wand - 0.6, eck_r - wand);
        // Gummifüße Ø10
        for (x = [-1, 1], y = [-1, 1]) translate([x * (breite / 2 - 16), y * (tiefe / 2 - 16), -0.01]) cylinder(d = 10.4, h = 1.2);
        // Schrauben M3 in die Schalenwand
        for (x = [-1, 1]) translate([x * (breite / 2 - 8), 0, -0.01]) cylinder(d = 3.4, h = boden_h + 1);
    }
    // Gewichtskammer (Stahlscheiben, mit Heißkleber fixieren)
    translate([0, ls_y - 4, boden_h]) difference() {
        linear_extrude(gewicht_h) rrect(70, 40, 4);
        translate([0, 0, 1]) linear_extrude(gewicht_h) rrect(70 - 2 * wand, 40 - 2 * wand, 3);
    }
}

module kontakttraeger() {
    w = pins * pin_raster + 6 - 0.4;
    difference() {
        linear_extrude(6) rrect(w, 9 - 0.4, 1.4);
        for (i = [0 : pins - 1]) translate([(i - (pins - 1) / 2) * pin_raster, 0, -0.01]) cylinder(d = pin_d, h = 7, $fn = 24);
        for (s = [-1, 1]) translate([s * (w / 2 + 1), 0, 6 - magnet_h]) cylinder(d = magnet_d, h = magnet_h + 0.01);
        // Kerbe: Kontakt 1 (+5V) markieren
        translate([-(pins - 1) / 2 * pin_raster, -9 / 2, 6 - 0.6]) cylinder(d = 1.6, h = 1, $fn = 16);
    }
    // Magnetaufnahmen seitlich
    for (s = [-1, 1]) translate([s * (w / 2 + 1), 0, 0]) difference() {
        cylinder(d = magnet_d + 2.4, h = 6);
        translate([0, 0, 6 - magnet_h]) cylinder(d = magnet_d, h = magnet_h + 0.01);
    }
}

module handteil_kontakte() {
    // Platte für die Unterseite des Telefons: Taschen für Kontaktscheiben,
    // Stahlscheiben über den Magneten, Kodiernut hinten.
    w = schacht_b - 2 * spiel;
    difference() {
        linear_extrude(3) rrect(w, hand_t, hand_r);
        for (i = [0 : pins - 1]) translate([(i - (pins - 1) / 2) * pin_raster, 0, -0.01]) {
            cylinder(d = pad_d + 0.3, h = 1.2);              // Messingscheibe
            cylinder(d = 1.5, h = 4, $fn = 16);              // Draht nach oben
        }
        for (s = [-1, 1]) translate([s * ((pins * pin_raster + 6) / 2 + 1), 0, -0.01]) cylinder(d = magnet_d, h = 1.6);
        translate([0, hand_t / 2 - kodier_t / 2, 1.5]) cube([kodier_b + 0.8, kodier_t + 0.8, 4], center = true);
    }
}

if (teil == "schale") schale();
else if (teil == "boden") boden();
else if (teil == "kontakttraeger") kontakttraeger();
else if (teil == "handteil_kontakte") handteil_kontakte();
else {
    color("#3a3a3a") schale();
    color("#555") translate([0, 0, -boden_h - 2]) boden();
    color("gold") translate([schacht_x, schacht_y, schacht_boden - 6]) rotate([-neigung, 0, 0]) kontakttraeger();
    // Telefon angedeutet
    color("white", 0.6) translate([schacht_x, schacht_y, schacht_boden]) rotate([-neigung, 0, 0])
        linear_extrude(gehaeuse_laenge) rrect(hand_b, hand_t, hand_r);
}
