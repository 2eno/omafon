// Omafon – charging cradle with speaker (parametric)
// OpenSCAD 2021+.  Choose a single part with "teil":
//   openscad -D 'teil="schale"' -o ladeschale.stl omafon_ladeschale.scad
//
// Structure (see docs/festnetz-hardware.md):
//   schale          housing with dock slot, entry funnel, speaker chamber
//   boden           base plate with weight chamber and rubber feet
//   kontakttraeger  insert for 5 spring contacts (pogo pins) in the slot floor
//   handteil_kontakte  contact plate for the underside of the phone
//   uebersicht      everything together (preview)
//
// Contact assignment (from the left, seen from the front): 1 +5V  2 GND  3 GND  4 LS+  5 LS-
// The coding rib at the back of the slot only fits the groove in the handset – the phone
// can't be inserted the wrong way round and finds the contacts by itself.
//
// Printing: PETG, 0.2 mm, 3 walls. Cradle with the opening up, no supports.

include <omafon_masse.scad>   // handset dimensions, contacts, coding (shared with the housing)

/* [Selection] */
teil = "uebersicht"; // [uebersicht, schale, boden, kontakttraeger, handteil_kontakte]

/* [Handset] – adapt to the real housing */
hand_b = gehaeuse_breite;   // width of the phone (from omafon_masse.scad)
hand_t = gehaeuse_dicke;    // thickness per variant
hand_r = gehaeuse_kante_r;  // rounding of the cross-section
spiel = 1.2;         // clearance all around
neigung = 15;        // phone leans backwards (degrees)
trichter = 7;        // entry chamfer at the top per side – can be found blind
trichter_h = 10;     // height of the entry chamfer
// coding rib at the back: kodier_b x kodier_t from omafon_masse.scad (groove in the handset)

/* [Housing] */
hoehe_vorn = 48;     // insertion depth follows from this (echo in the console)
wand = 2.4;
eck_r = 12;

/* [Speaker] */
ls_d = 50;           // Ø basket, e.g. 50 mm full-range driver 8 Ω
ls_tiefe = 16;       // height of the sound guide under the lid
ls_loch = 3;         // grille holes

/* [Contacts] */
pins = kontakt_pins;
pin_raster = kontakt_raster;
pin_d = 2.05;        // hole for spring contact Ø2 mm (press fit)
pad_d = kontakt_pad_d;
// magnets magnet_d x magnet_h from omafon_masse.scad

/* [Connector] */
usbc_b = 13;         // USB-C socket board (breakout)
usbc_h = 7;

/* [Base] */
boden_h = 4;
gewicht_h = 10;      // chamber for steel discs (stability)

// footprint grows with the handset (slot + funnel + walls + margin / speaker behind it)
breite = hand_b + 2 * spiel + 2 * trichter + 2 * wand + 24;
tiefe = 18 + (hand_t + 2 * spiel) + trichter + 3 * wand
        + (hoehe_vorn + 10 - (boden_h + 6)) * tan(neigung) + ls_d + 6;

$fn = 64;

schacht_b = hand_b + 2 * spiel;
schacht_t = hand_t + 2 * spiel;
schacht_x = 0;
schacht_y = -tiefe / 2 + 18 + schacht_t / 2;   // front, speaker behind it
schacht_boden = boden_h + 6;
hoehe_hinten = hoehe_vorn + 10;
// speaker behind the tilted slot (include the tilt offset at the top)
ls_y = schacht_y + schacht_t / 2 + trichter + wand + (hoehe_hinten - schacht_boden) * tan(neigung) + ls_d / 2 + wand + 1;
assert(ls_y + ls_d / 2 + wand < tiefe / 2 - wand, "speaker does not fit behind the slot – increase tiefe");
// height of the sloped top at position y
function oben_z(y) = hoehe_vorn + (y + tiefe / 2 - eck_r) / (tiefe - 2 * eck_r) * (hoehe_hinten - hoehe_vorn);
ls_top = oben_z(ls_y);
// insertion depth along the slot axis up to the top edge
einsteck = (oben_z(schacht_y) - schacht_boden) / cos(neigung);
echo(str("insertion depth ", round(einsteck), " mm, of which funnel ", trichter_h, " mm"));

module rrect(w, d, r) { offset(r) square([w - 2 * r, d - 2 * r], center = true); }

// top: low at the front, higher at the back (desk)
module pult(r, hv, hh, z0 = 0) {   // corner cylinders: hv high at the front, hh at the back
    hull() for (x = [-1, 1], y = [-1, 1])
        translate([x * (breite / 2 - eck_r), y * (tiefe / 2 - eck_r), z0])
            cylinder(r = r, h = (y < 0 ? hv : hh) - z0);
}
module aussenform() { pult(eck_r, hoehe_vorn, hoehe_hinten); }

module schacht_form() {
    // tilted slot; funnel at the top
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
            // coding rib at the back, centered
            translate([-kodier_b / 2, schacht_t / 2 - kodier_t, -1]) cube([kodier_b, kodier_t + 0.01, einsteck - trichter_h + 1]);
        }
    }
}

module kontakt_tasche() {   // recess for the contact carrier in the slot floor
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
        // hollow inside (closed at the top), open at the bottom for the base
        pult(eck_r - wand, hoehe_vorn - wand, hoehe_hinten - wand, -0.01);
        schacht_form();
        grill();
        // USB-C at the bottom rear
        translate([0, tiefe / 2 - wand / 2, boden_h + usbc_h / 2 + 2]) cube([usbc_b - 3.5, wand * 3, usbc_h - 3], center = true);
        // tactile mark at the front: three grooves = "this is the front"
        for (x = [-8, 0, 8]) translate([x, -tiefe / 2 - 0.5, hoehe_vorn - 10]) cube([2, 2, 8], center = true);
    }
    // close the slot again as a tub inside (walls around the slot)
    difference() {
        intersection() {
            aussenform();
            translate([schacht_x, schacht_y, schacht_boden - 6]) rotate([-neigung, 0, 0])
                linear_extrude(einsteck + 40) rrect(schacht_b + 2 * trichter + 2 * wand, schacht_t + 2 * trichter + 2 * wand, hand_r + trichter + wand);
        }
        schacht_form();
        kontakt_tasche();
    }
    // sound guide: ring under the grille, merges into the sloped lid.
    // push the speaker from below up to the lid, fix it with hot glue.
    // the closed housing (with base) is the back volume.
    intersection() {
        aussenform();
        translate([0, ls_y, ls_top - ls_tiefe]) difference() {
            cylinder(d = ls_d + 0.6 + 2 * wand, h = ls_tiefe + 20);
            translate([0, 0, -1]) cylinder(d = ls_d + 0.6, h = ls_tiefe + 30);
        }
    }
    // USB-C holder
    translate([0, tiefe / 2 - wand - 6, boden_h]) difference() {
        translate([0, 0, (usbc_h + 4) / 2]) cube([usbc_b + 4, 12, usbc_h + 4], center = true);
        translate([0, 1, usbc_h / 2 + 2]) cube([usbc_b + 0.4, 14, 1.8], center = true); // board groove
    }
}

module boden() {
    difference() {
        linear_extrude(boden_h) rrect(breite - 2 * wand - 0.6, tiefe - 2 * wand - 0.6, eck_r - wand);
        // rubber feet Ø10
        for (x = [-1, 1], y = [-1, 1]) translate([x * (breite / 2 - 16), y * (tiefe / 2 - 16), -0.01]) cylinder(d = 10.4, h = 1.2);
        // M3 screws into the cradle wall
        for (x = [-1, 1]) translate([x * (breite / 2 - 8), 0, -0.01]) cylinder(d = 3.4, h = boden_h + 1);
    }
    // weight chamber (steel discs, fix with hot glue)
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
        // notch: mark contact 1 (+5V)
        translate([-(pins - 1) / 2 * pin_raster, -9 / 2, 6 - 0.6]) cylinder(d = 1.6, h = 1, $fn = 16);
    }
    // magnet seats at the sides
    for (s = [-1, 1]) translate([s * (w / 2 + 1), 0, 0]) difference() {
        cylinder(d = magnet_d + 2.4, h = 6);
        translate([0, 0, 6 - magnet_h]) cylinder(d = magnet_d, h = magnet_h + 0.01);
    }
}

module handteil_kontakte() {
    // plate for the underside of the phone: pockets for contact discs,
    // steel discs over the magnets, coding groove at the back.
    w = schacht_b - 2 * spiel;
    difference() {
        linear_extrude(3) rrect(w, hand_t, hand_r);
        for (i = [0 : pins - 1]) translate([(i - (pins - 1) / 2) * pin_raster, 0, -0.01]) {
            cylinder(d = pad_d + 0.3, h = 1.2);              // brass disc
            cylinder(d = 1.5, h = 4, $fn = 16);              // wire upwards
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
    // phone indicated
    color("white", 0.6) translate([schacht_x, schacht_y, schacht_boden]) rotate([-neigung, 0, 0])
        linear_extrude(gehaeuse_laenge) rrect(hand_b, hand_t, hand_r);
}
