// Omafon – handset housing (parametric, all variants)
// OpenSCAD 2021+.  Choose part and variant:
//   openscad -D 'variante="hybrid"' -D 'teil="wanne"' -o wanne.stl omafon_gehaeuse.scad
//
// Parts (the STL output is already in print orientation):
//   deckel           top shell with built-in switch plate (16 Cherry MX switches
//                    clip in from the front), earpiece, microphone
//   wanne            bottom shell: emergency recess, speaker, battery bay, charging contacts,
//                    coding groove, volume keys, Pi holder, screw bosses
//   tastengitter     optional tactile ridges between the keys (glued on)
//   hoererkopf       raised head part with sound tube and LED (glued on)
//   hoermuschel      soft ring on the head part (TPU)
//   akkudeckel       battery bay cover (2 countersunk screws M2.5)
//   notrufklappe     cover over the emergency button (hinge pin of 1.75 mm filament,
//                    magnet 5 x 1 mm for the cover switch)
//   lautstaerke_plus / lautstaerke_minus   side keys (feel different)
//   uebersicht       assembled with key caps (preview only)
//   schnitt          longitudinal section for checking (preview only)
//
// Coordinates (assembly): x across, y along (+y = top/earpiece), z thickness
// (z = 0 back, z = thickness front).

include <omafon_masse.scad>
use <omafon_tasten.scad>

/* [Selection] */
teil = "uebersicht"; // [uebersicht, schnitt, pruefstueck, deckel, wanne, tastengitter, akkudeckel, notrufklappe, lautstaerke_plus, lautstaerke_minus, hoererkopf, hoermuschel]

/* [Build] */
deckel_h = 5;          // height of the top shell; the rest belongs to the bottom shell
falz_h = 1.6;          // centering lip between bottom shell and top
falz_b = 1.0;
spalt = 0.3;           // clearance between printed parts (per side)
oben_bereich = 32;     // space above the keys (earpiece, LED, emergency)

/* [Switches] */
mx_platte = 1.6;       // plate thickness at the switches: MX 1.5 ± 0.1; 1.6 = 8 layers of 0.2 mm
mx_ausschnitt = 14.1;  // MX standard 14.0 – printed holes come out smaller
mx_tasche = 15.6;      // inside around each switch, room for the clamping springs
gitter_h = 1.2;        // optional tactile ridges: low enough that pressed caps stay clear
gitter_b = 1.6;

/* [Built-in parts] – adapt to the real parts */
hoerer_d = 15.6;       // earpiece capsule Ø15
mik_d = 10.2;          // electret capsule Ø9.7–10
ls_d = 28.6;           // speaker Ø28 in the handset
led_d = 5.2;
gnss_b = 25.4;         // active GNSS ceramic antenna 25 x 25 (hybrid)
schraube_d = 2.9;      // M2.5 through
einsatz_d = 3.6;       // threaded insert M2.5 (heat-set nut)
einsatz_t = 3.8;       // short inserts (M2.5 x 3.5) – the top is only 5 mm high
schraube_l = gehaeuse_dicke <= 30 ? 25 : 30;   // cylinder head screw M2.5 x 25 or x 30

$fn = 40;

// ------------------------------------------------------------ derived dimensions
B = gehaeuse_breite; L = gehaeuse_laenge; D = gehaeuse_dicke;
ER = gehaeuse_eck_r; KR = gehaeuse_kante_r; W = gehaeuse_wand;
ZS = D - deckel_h;                       // parting plane bottom shell/top
senk_t = max(2.5, ZS + 3 - schraube_l);  // head counterbore: 3 mm of thread in the insert
TF = tastenfront_mass();
FB = TF[0]; FH = TF[1]; RASTER = TF[2]; PLATTE = TF[3]; STEG_H = TF[4];
fenster_oben = L / 2 - oben_bereich;
fenster_y = fenster_oben - FH / 2;       // center of the key window
platte_z = D - mx_platte;                // bottom edge of the switch plate in the top
function tasten_xy() = [for (p = tastenpositionen())
    [p[0] * RASTER, fenster_y + 2.5 * RASTER + p[1] * RASTER, p[2]]];
modem = variante == "hybrid";       // SIM7600 HAT, GNSS antenna, larger battery

// battery [width, length, thickness]: landline 3000 mAh, hybrid 5000 mAh (example)
AK = modem ? [60, 70, 12] : [60, 75, 10];
akku_y0 = -L / 2 + kodier_nut_l + 6;     // bottom edge of the battery bay, above the coding groove
akku_x = -B / 2 + W + 3 + AK[0] / 2;     // left; room for boards to the right
akku_oeff = [AK[0] + 6, AK[1] + 6];
akku_mitte = [akku_x, akku_y0 + AK[1] / 2];
// two M2.5 screws: bottom left (next to the coding groove), top right
akku_schrauben = [[akku_mitte[0] - 22, akku_mitte[1] - akku_oeff[1] / 2 - 3.5],
                  [akku_mitte[0] + 22, akku_mitte[1] + akku_oeff[1] / 2 + 3.5]];
akku_polster = 7.6;    // hole in the wall for the 2.2 mm pad of the cover

// positions
ohr_y = L / 2 - 16;
// Head part: raised head above the keys. Ear and ear cup sit higher than
// the key caps (approx. 12–15 mm) – so the cheek doesn't press a key.
kopf_h = 18;             // above the front (highest cap: call key approx. 17.6 mm)
kopf_y0 = L / 2 - oben_bereich + 3.5;   // distance to the top key row stays graspable
kopf_y1 = L / 2 - gehaeuse_kante_r;     // only on the flat top surface
kopf_x = 38;             // half width
kopf_r = 8;              // corners in top view
kopf_kante = 1.2;        // rounding at the top
kopf_wand = 2;
rohr_aussen = 22;        // sound tube earpiece -> top of the head, centered in the top's recess
rohr_innen = 16;
// ear cup (separate part, ideally TPU) on the head
muschel_innen = 14;      // free sound path (earpiece holes lie within r = 6.3)
muschel_aussen = 19.6;   // stays on the flat head surface
muschel_h = 3;           // above the head
muschel_einsatz = 1.0;   // this is how deep it sits in the head's recess
led_pos = [-25, L / 2 - 14];
gnss_pos = [22.5, L / 2 - 19];           // top right under the top shell (hybrid)
mik_y = -L / 2 + 11;
sos_y = L / 2 - 32;                      // emergency recess (back): the switch stays clear under the earpiece holder
sos_oeff = 21;                           // cap Ø19.2 goes through
sos_tiefe = 13.6;                        // cap 9 + switch 6.6 – recessed 2 mm (68 layers of 0.2)
sos_klappe = 29;
ls_pos = [-20, -L / 2 + 22];             // speaker at the bottom of the back
laut_y = [L / 2 - 55, L / 2 - 75];       // volume + / − (left side)
laut_z = ZS / 2 + 2;
pi_mitte = [0, 45];                      // Pi Zero 2 W, 65 x 30
dome = [[-1, L / 2 - 9], [1, L / 2 - 9], [-1, -L / 2 + 9], [1, -L / 2 + 9]];
dom_x = B / 2 - 7;

// ------------------------------------------------------------ Basic shapes
module rrect(w, d, r) { offset(r) square([w - 2 * r, d - 2 * r], center = true); }

// 45° chamfer instead of a rounding at front and back: both shells lie on the bed
// with this side, where a rounding would be a steep overhang.
module ecke(r, kr, h) {
    rotate_extrude($fn = 40) polygon([[0, 0], [r - kr, 0], [r, kr], [r, h - kr], [r - kr, h], [0, h]]);
}

// outer body, offset inwards by "off" (for the interior/lip)
module koerper(off = 0) {
    hull() for (x = [-1, 1], y = [-1, 1])
        translate([x * (B / 2 - ER), y * (L / 2 - ER), off])
            ecke(ER - off, max(0.6, KR - off), D - 2 * off);
}

module schale() { difference() { koerper(0); koerper(W); } }

module zwischen(z0, z1) { translate([-B, -L, z0]) cube([2 * B, 2 * L, z1 - z0]); }

// ------------------------------------------------------------ Top (upper shell)
module deckel() {
    difference() {
        union() {
            intersection() { schale(); zwischen(ZS, D + 1); }
        // earpiece, microphone and LED holders under the surface
            translate([0, ohr_y, D - W - 2.5]) ring(hoerer_d, 2.5);
            translate([0, mik_y, D - W - 2.5]) ring(mik_d, 2.5);
            translate([led_pos[0], led_pos[1], D - W - 4]) ring(led_d, 4);
            if (modem) translate([gnss_pos[0], gnss_pos[1], D - W - 2]) linear_extrude(2)
                difference() { square(gnss_b + 1.6, center = true); square(gnss_b, center = true); }
            // screw bosses with threaded inserts
            for (d = dome) translate([d[0] * dom_x, d[1], ZS + 0.1]) cylinder(d = 7, h = D - W - ZS - 0.1 + 0.01);
        }
        // switch plate: cut-out through, pocket inside down to mx_platte
        for (t = tasten_xy()) translate([t[0], t[1], 0]) {
            translate([0, 0, D - W - 1]) linear_extrude(W + 2) square(mx_ausschnitt, center = true);
            translate([0, 0, D - W - 1]) linear_extrude(1 + W - mx_platte) square(mx_tasche, center = true);
        }
        // ring recess: centers the sound tube of the head part (the front stays flat)
        translate([0, ohr_y, D - 1]) difference() {
            cylinder(d = rohr_aussen + 0.4, h = 2, $fn = 64);
            translate([0, 0, -1]) cylinder(d = rohr_innen - 0.4, h = 4, $fn = 64);
        }
        // earpiece holes, microphone holes, LED
        for (p = loch_muster(5.5, 1.6)) translate([p[0], ohr_y + p[1], D - W - 1]) cylinder(d = 1.6, h = W + 2, $fn = 12);
        for (p = loch_muster(3, 1.2)) translate([p[0], mik_y + p[1], D - W - 1]) cylinder(d = 1.2, h = W + 2, $fn = 12);
        translate([led_pos[0], led_pos[1], D - W - 5]) cylinder(d = led_d, h = W + 6);
        // lip seat (wall thinner inside)
        intersection() { difference() { koerper(W - falz_b - spalt); koerper(W + 0.5); } zwischen(ZS - 0.01, ZS + falz_h); }
        // inserts in the bosses
        for (d = dome) translate([d[0] * dom_x, d[1], ZS - 0.01]) cylinder(d = einsatz_d, h = min(einsatz_t, D - ZS - 1.2));
    }
}

module ring(innen, h, breite = 1.6) {
    difference() { cylinder(d = innen + 2 * breite, h = h); translate([0, 0, -0.01]) cylinder(d = innen, h = h + 0.02); }
}

// holes on circles (radius up to r, spacing a)
function loch_muster(r, a) = [for (x = [-r : a * 1.6 : r + 0.01], y = [-r : a * 1.6 : r + 0.01])
    if (x * x + y * y <= r * r) [x, y]];

// ------------------------------------------------------------ Bottom shell
module wanne() {
    difference() {
        union() {
            intersection() { schale(); zwischen(-1, ZS); }
            // centering lip
            intersection() { difference() { koerper(W - falz_b); koerper(W); } zwischen(ZS - 0.01, ZS + falz_h - 0.2); }
            // screw bosses
            for (d = dome) translate([d[0] * dom_x, d[1], 0]) intersection() { cylinder(d = 7, h = ZS); koerper(0.01); }
            sos_mulde_koerper();
            // speaker holder
            translate([ls_pos[0], ls_pos[1], W - 0.01]) ring(ls_d, 3);
            // boss for the battery cover screw
            // wider than the pad hole so it rests on the wall (prints as a bridge)
            for (a = akku_schrauben) translate([a[0], a[1], 0]) cylinder(d = akku_polster + 3.4, h = W + 6);
            // reinforcement at the charging contacts and the coding groove
            intersection() {
                koerper(0.01);
                union() {
                    translate([-24, -L / 2, D / 2 - 7]) cube([48, W + 2.5, 14]);
                    translate([-(kodier_b / 2 + 2.4), -L / 2, 0]) cube([kodier_b + 4.8, kodier_nut_l + 2, kodier_t + 0.6 + 1.4]);
                }
            }
            // Pi Zero 2 W: 4 standoffs (M2.5), hole spacing 58 x 23
            for (x = [-29, 29], y = [-11.5, 11.5]) translate([pi_mitte[0] + x, pi_mitte[1] + y, W - 0.01])
                difference() { cylinder(d = 5.5, h = 3); cylinder(d = 2.2, h = 4); }
            lautstaerke_fuehrungen();
            // cable tie bridges in the board area to the right of the battery
            for (y = [akku_y0 + 10, akku_y0 + 40]) translate([B / 2 - W - 14, y, W - 0.01]) kabelbinder_bruecke();
        }
        // emergency recess: opening, cover recess, hinge, switch opening, reed contact
        sos_mulde_aussparung();
        // speaker grille
        for (p = loch_muster(10, 1.8)) translate([ls_pos[0] + p[0], ls_pos[1] + p[1], -1]) cylinder(d = 1.8, h = W + 2, $fn = 12);
        // battery bay: opening + lip for the cover
        akku_aussparung();
        for (a = akku_schrauben) {
            translate([a[0], a[1], -1]) cylinder(d = akku_polster, h = 1 + W);   // pad of the cover
            translate([a[0], a[1], W - 0.01]) cylinder(d = einsatz_d, h = 6.2);   // insert from the outside
        }
        // charging contacts at the bottom: brass discs, wire holes, steel discs over the magnets
        for (i = [0 : kontakt_pins - 1]) translate([(i - (kontakt_pins - 1) / 2) * kontakt_raster, -L / 2 - 1, D / 2])
            rotate([-90, 0, 0]) { cylinder(d = kontakt_pad_d + 0.3, h = 1 + 1.2); cylinder(d = 1.6, h = 10, $fn = 12); }
        for (s = [-1, 1]) translate([s * magnet_x(), -L / 2 - 1, D / 2]) rotate([-90, 0, 0]) cylinder(d = magnet_d, h = 1 + 1.6);
        // coding groove at the back (fits the rib in the dock slot)
        translate([-(kodier_b + 0.8) / 2, -L / 2 - 1, -1]) cube([kodier_b + 0.8, kodier_nut_l + 1, kodier_t + 0.6 + 1]);
        // volume keys on the left
        for (y = laut_y) translate([-B / 2 - 1, y, laut_z]) rotate([0, 90, 0]) linear_extrude(W + 2) rrect(8, 8, 1.5);
        // bosses: screw from the back, counterbore for the head
        for (d = dome) translate([d[0] * dom_x, d[1], -1]) {
            cylinder(d = schraube_d, h = ZS + 2);
            cylinder(d = 5, h = 1 + senk_t);
        }
    }
}

module sos_mulde_koerper() {
    // tube of the recess + reinforcement around the cover
    translate([0, sos_y, 0]) {
        intersection() {
            koerper(0.01);
            translate([0, 0, 0]) linear_extrude(4.6) rrect(sos_klappe + 8, sos_klappe + 8, 3);
        }
        linear_extrude(sos_tiefe + mx_platte) rrect(sos_oeff + 3.2, sos_oeff + 3.2, 3);
    }
}

module sos_mulde_aussparung() {
    translate([0, sos_y, 0]) {
        // recess down to the switch plate
        translate([0, 0, -1]) linear_extrude(sos_tiefe + 1) rrect(sos_oeff, sos_oeff, 2);
        // MX cut-out in the switch plate (1.5 mm)
        translate([0, 0, sos_tiefe - 0.01]) linear_extrude(mx_platte + 1) square(mx_ausschnitt, center = true);
        // detents for the cover (light click, opens with one finger)
        for (s = [-1, 1]) translate([s * sos_klappe / 2, -sos_klappe / 2 + 5, 0.9]) sphere(d = 1.3, $fn = 12);
        // cover recess, finger grip at the bottom
        translate([0, 0, -1]) linear_extrude(1 + 1.8) rrect(sos_klappe, sos_klappe, 3);
        translate([0, -sos_klappe / 2, -1]) cylinder(d = 12, h = 1 + 1.8);
        // hinge channel at the top + pin hole (filament 1.75 mm)
        translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) {
            cylinder(d = 3.9, h = sos_klappe + 0.4, center = true);
            cylinder(d = 1.85, h = sos_klappe + 8, center = true, $fn = 16);
        }
        // reed contact lengthwise next to the recess (magnet in the cover above it)
        translate([13.4, -14, 3.4]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 22, $fn = 16);
    }
}

module akku_aussparung() {
    translate([akku_mitte[0], akku_mitte[1], -1]) {
        linear_extrude(W + 2) rrect(akku_oeff[0], akku_oeff[1], 3);
        // lip outside: cover 1.2 mm, 6 mm longer at the top and bottom (screws)
        linear_extrude(1 + 1.2) rrect(akku_oeff[0] + 4, akku_oeff[1] + 4 + 12, 4);
    }
}

module lautstaerke_fuehrungen() {
    // rails for a perfboard 14 x 16 with a 6x6 switch
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

// ------------------------------------------------------------ Small parts
module tastengitter() {
    // assembly: lies on the front (z = D) around the keys
    translate([0, 0, D]) linear_extrude(gitter_h) difference() {
        translate([0, fenster_y]) rrect(FB, FH, 3);
        for (t = tasten_xy()) translate([t[0], t[1]])
            if (t[2] == "i") rrect(40, RASTER - gitter_b, 4);
            else rrect(RASTER - gitter_b, RASTER - gitter_b, 3);
    }
}

module akkudeckel() {
    // in the assembly coordinate system; outer surface z = 0
    translate([akku_mitte[0], akku_mitte[1], 0]) difference() {
        union() {
            linear_extrude(1.2 - 0.05) rrect(akku_oeff[0] + 4 - 2 * spalt, akku_oeff[1] + 4 + 12 - 2 * spalt, 3.7);
            linear_extrude(W) rrect(akku_oeff[0] - 2 * spalt, akku_oeff[1] - 2 * spalt, 2.7);
            // 2.2 mm thick pads around the screws (the countersunk head needs material)
            for (a = akku_schrauben) translate([a[0] - akku_mitte[0], a[1] - akku_mitte[1], 0])
                cylinder(d = akku_polster - 2 * spalt, h = W);
        }
        for (a = akku_schrauben) translate([a[0] - akku_mitte[0], a[1] - akku_mitte[1], -0.01]) {
            cylinder(d = schraube_d, h = 5);
            cylinder(d1 = 5.4, d2 = schraube_d, h = 1.3);    // countersunk head 90°
        }
        for (i = [-2 : 2]) translate([i * 4, akku_oeff[1] / 2 - 10, -0.01]) cube([1.2, 14, 0.5], center = true);
    }
}

module notrufklappe() {
    // assembly coordinates: lies in the recess around the emergency well
    translate([0, sos_y, 0]) difference() {
        union() {
            translate([0, 0, 0.05]) linear_extrude(1.7) rrect(sos_klappe - 2 * spalt, sos_klappe - 2 * spalt, 2.7);
            // detent nubs at the sides (engage the dimples in the bottom shell, 0.25 mm oversize)
            for (s = [-1, 1]) translate([s * (sos_klappe / 2 - spalt), -sos_klappe / 2 + 5, 0.9]) sphere(d = 1.1, $fn = 12);
            translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) cylinder(d = 3.4, h = sos_klappe - 0.8, center = true);
            // nubs outside: feels like "this is the emergency button"
            for (x = [-7, 0, 7], y = [-7, 0, 7]) translate([x, y, 0.06]) scale([1, 1, 0.6]) sphere(d = 3, $fn = 16);
        }
        translate([0, sos_klappe / 2 - 1.9, 1.9]) rotate([0, 90, 0]) cylinder(d = 1.95, h = sos_klappe + 1, center = true, $fn = 16);
        // magnet 5 x 1 inside, above the reed contact
        translate([11.4, -6, 1.75 - 1.1]) cylinder(d = 5.2, h = 1.2);
    }
}

// head shape in assembly coordinates (stands on z = D), "off" = offset inwards
module kopf_form(off = 0, h = kopf_h) {
    hull() for (x = [-1, 1], y = [kopf_y0 + kopf_r, kopf_y1 - kopf_r])
        translate([x * (kopf_x - kopf_r), y, D]) rotate_extrude($fn = 40) hull() {
            square([kopf_r - off, 0.01]);
            square([0.01, h - off]);
            translate([kopf_r - off - kopf_kante, h - off - kopf_kante]) circle(kopf_kante, $fn = 16);
        }
}

module hoererkopf() {
    difference() {
        union() {
            difference() {
                kopf_form();
                translate([0, 0, -0.01]) kopf_form(kopf_wand);
            }
            intersection() {
                kopf_form();
                union() {
                    // sound tube up to the top of the head
                    translate([0, ohr_y, D]) ring(rohr_innen, kopf_h, (rohr_aussen - rohr_innen) / 2);
                    // light pipe for the LED (sits at the top of the head)
                    translate([led_pos[0], led_pos[1], D]) ring(6, kopf_h, 1.5);
                }
            }
            // centering stub: 1 mm in the ring recess of the top
            translate([0, ohr_y, D - 1 + 0.1]) ring(rohr_innen + 0.2, 1, (rohr_aussen - rohr_innen - 0.6) / 2);
        }
        // earpiece holes at the top, recess for the ear cup
        for (p = loch_muster(5.5, 1.6)) translate([p[0], ohr_y + p[1], D + kopf_h - kopf_wand - 1]) cylinder(d = 1.6, h = kopf_wand + 2, $fn = 12);
        translate([0, ohr_y, D + kopf_h - muschel_einsatz]) difference() {
            cylinder(d = muschel_aussen + 0.4, h = muschel_einsatz + 1, $fn = 64);
            translate([0, 0, -1]) cylinder(d = muschel_innen - 0.4, h = muschel_einsatz + 3, $fn = 64);
        }
        // LED: Ø5 head looks out at the top, the collar rests inside
        translate([led_pos[0], led_pos[1], D + kopf_h - kopf_wand - 1]) cylinder(d = led_d, h = kopf_wand + 2);
    }
}

module hoermuschel() {
    // print orientation: flat underside on the bed, rounding on top
    r1 = muschel_innen / 2; r2 = muschel_aussen / 2; h = muschel_einsatz + muschel_h; k = 1.6;
    rotate_extrude($fn = 64) hull() {
        translate([r1, 0]) square([r2 - r1, 0.01]);
        translate([r1 + k, h - k]) circle(k, $fn = 24);
        translate([r2 - k, h - k]) circle(k, $fn = 24);
        translate([r1, 0]) square([0.01, h - k]);
        translate([r2 - 0.01, 0]) square([0.01, h - k]);
    }
}

// test print before the big parts (approx. 20 min): two switch cut-outs exactly as in the
// top (plate, pocket), one boss with an insert hole, an emergency cap fits into the ring.
module pruefstueck() {
    difference() {
        union() {
            linear_extrude(W) rrect(60, 32, 3);
            translate([22, 0, W - 0.01]) cylinder(d = 7, h = 4);
        }
        for (x = [-17, 7]) translate([x, 0, -1]) {
            linear_extrude(W + 2) square(mx_ausschnitt, center = true);
            translate([0, 0, 1 + mx_platte]) linear_extrude(W) square(mx_tasche, center = true);
        }
        translate([22, 0, W + 4 - einsatz_t]) cylinder(d = einsatz_d, h = einsatz_t + 1);
        translate([22, 0, -1]) cylinder(d = schraube_d, h = W + 2);
        // hole size of the volume key (8 x 8) for a test fit
        translate([22, -11, -1]) linear_extrude(W + 2) rrect(8, 8, 1.5);
    }
}

module lautstaerke(plus) {
    // print orientation: collar at the bottom
    difference() {
        union() {
            linear_extrude(1.2) rrect(10.5, 10.5, 2);
            linear_extrude(1.2 + W + 1.3) rrect(7.4, 7.4, 1.2);
            // raised symbol: + (cross) or − (bar)
            translate([0, 0, 1.2 + W + 1.3 - 0.01]) linear_extrude(0.8) {
                square([5, 1.4], center = true);
                if (plus) square([1.4, 5], center = true);
            }
        }
    }
}

// ------------------------------------------------------------ Preview
module zusammenbau(kappen = true) {
    color("#e8e8e8") wanne();
    color("#d0d0d0") deckel();
    color("#c8c8c8") hoererkopf();
    color("#222") translate([0, ohr_y, D + kopf_h - muschel_einsatz]) hoermuschel();
    color("#333") tastengitter();
    color("#cc0000") notrufklappe();
    color("#bbb") akkudeckel();
    for (y = laut_y) color("#444") translate([-B / 2 - 1.3, y, laut_z]) rotate([0, -90, 0]) rotate([0, 0, 0])
        translate([0, 0, -1.2 - W]) lautstaerke(y == laut_y[0]);
    if (kappen) {
        // MX: cap bottom edge approx. 5.6 mm above the plate top (= front)
        for (t = tasten_xy()) translate([t[0], t[1], D + 5.6]) kappe_fuer(t[2]);
    }
}

// print orientation: largest flat surface on the bed
module druck(name) {
    if (name == "deckel") translate([0, 0, D]) mirror([0, 0, 1]) deckel();
    else if (name == "wanne") wanne();
    else if (name == "pruefstueck") pruefstueck();
    else if (name == "tastengitter") translate([0, 0, -D]) tastengitter();
    else if (name == "akkudeckel") akkudeckel();
    // standing on the hinge edge: nubs outside and tubes inside need no supports this way
    else if (name == "notrufklappe") translate([0, 0, sos_klappe / 2 - 0.2]) rotate([-90, 0, 0]) translate([0, -sos_y, 0]) notrufklappe();
    else if (name == "lautstaerke_plus") lautstaerke(true);
    else if (name == "lautstaerke_minus") lautstaerke(false);
    else if (name == "hoermuschel") hoermuschel();
    // top side on the bed: walls and tubes grow freely upwards
    else if (name == "hoererkopf") translate([0, 0, D + kopf_h]) mirror([0, 0, 1]) hoererkopf();
}

echo(str("variant ", variante, ": handset ", B, " x ", L, " x ", D, " mm, battery ", AK[0], " x ", AK[1], " x ", AK[2]));

if (teil == "uebersicht") zusammenbau();
else if (teil == "schnitt") intersection() { zusammenbau(false); translate([0, -L, -1]) cube([B, 2 * L, D + 30]); }
else druck(teil);
