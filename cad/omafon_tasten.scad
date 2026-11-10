// Omafon – key caps and key front (parametric)
// OpenSCAD 2021+.  Choose a single part with "teil" and "ziffer" if needed.
// Command line, e.g.:
//   openscad -D 'teil="ziffer"' -D 'ziffer="5"' -o taste_5.stl omafon_tasten.scad
//   openscad -D 'teil="front"' -o front.stl omafon_tasten.scad
//   Two colors: export the same cap twice, with -D 'farbteil="kappe"' and
//   -D 'farbteil="zeichen"', load them in the slicer as two bodies of one object.
//
// Printing: caps with the top facing up, 0.12–0.16 mm layers, PETG or PLA.
// Legibility: symbols always in a contrasting color to the cap (suggestion below in FARBEN):
//   - multi-material printers: farbteil="kappe" + farbteil="zeichen" (two STLs)
//   - single-nozzle printers: a color change (M600) at the cap top edge (kappe_h) only works
//     cleanly for flat caps (nachricht, info). Digits sit in a dish –
//     better use multi-material there or color the raised symbol afterwards.
// Print ONE cap first and check the fit on the switch (stem_spiel).

/* [Selection] */
teil = "uebersicht"; // [uebersicht, ziffer, anrufen, auflegen, nachricht, info, notruf, front]
ziffer = "5";        // 0-9, * or #
braille = false;     // Braille cell at the top of the cap
farbteil = "alles";  // [alles, kappe, zeichen] – export separately for two-color printing

/* [Dimensions] */
raster = 24;         // key spacing center to center
kappe = 20;          // edge length of the digit cap at the top
kappe_h = 9;         // height above the bottom edge
eck_r = 3;           // corner radius
wand = 1.6;
relief_h = 1.0;      // height of the raised symbols
schrift = "Atkinson Hyperlegible:style=Bold"; // fallback: "Liberation Sans:style=Bold"
schrift_gr = 12;

/* [Cherry MX mount] */
stem_d = 5.6;
kreuz_l = 4.1;
kreuz_b = 1.25;      // original 1.17; 1.2–1.3 depending on the printer
stem_tiefe = 4.0;
stem_spiel = 0.0;    // extra width if too tight

/* [Front] */
platte = 1.5;        // MX clamping dimension – exactly 1.5 mm at the cut-outs
ausschnitt = 14.1;   // MX standard 14.0; printed holes come out smaller
steg_h = 3.0;        // height of the tactile ridges above the plate
steg_b = 2.0;
rand = 6;

$fn = 48;

// High-contrast color pairs [cap, symbol] – only for preview/3MF, STL has no color.
// White/black is the most legible for residual vision; yellow/black for the call key.
FARBEN = [
    ["ziffer",    ["white",   "black"]],
    ["anrufen",   ["#FFD100", "black"]],
    ["auflegen",  ["#222222", "white"]],
    ["nachricht", ["white",   "black"]],
    ["info",      ["white",   "black"]],
    ["notruf",    ["#D00000", "white"]],
];
function farben(art) = [for (e = FARBEN) if (e[0] == art) e[1]][0];

// Cap and symbol as separate bodies: children(0) = cap, children(1) = symbol.
// "kappe" leaves out the symbol so the two bodies don't overlap in the slicer.
module zweifarbig(art) {
    f = farben(art);
    if (farbteil == "alles") { color(f[0]) children(0); color(f[1]) children(1); }
    else if (farbteil == "kappe") color(f[0]) difference() { children(0); children(1); }
    else if (farbteil == "zeichen") color(f[1]) children(1);
}

// ------------------------------------------------------------ Basic shapes
module rrect(w, d, r) {
    offset(r) square([w - 2 * r, d - 2 * r], center = true);
}

module stem() {
    difference() {
        cylinder(d = stem_d, h = stem_tiefe);
        translate([0, 0, -0.01]) linear_extrude(stem_tiefe + 0.02) {
            square([kreuz_l + stem_spiel, kreuz_b + stem_spiel], center = true);
            square([kreuz_b + stem_spiel, kreuz_l + stem_spiel], center = true);
        }
    }
}

// cap body: slightly larger at the bottom than at the top, hollow for the switch housing
module koerper(w, d, oben = "mulde") {
    unten_w = w + 1.5; unten_d = d + 1.5;
    difference() {
        hull() {
            linear_extrude(0.01) rrect(unten_w, unten_d, eck_r);
            translate([0, 0, kappe_h - 0.01]) linear_extrude(0.01) rrect(w, d, eck_r);
        }
        // cavity (the switch housing moves into it when pressed)
        translate([0, 0, -0.01]) hull() {
            linear_extrude(0.01) rrect(unten_w - 2 * wand, unten_d - 2 * wand, 1);
            translate([0, 0, kappe_h - 3]) linear_extrude(0.01) rrect(w - 2 * wand, d - 2 * wand, 1);
        }
        if (oben == "mulde")  // shallow spherical dish centers the finger
            translate([0, 0, kappe_h + 60 - 0.8]) sphere(r = 60, $fn = 120);
        if (oben == "rinne")  // cross groove (hang up)
            translate([0, 0, kappe_h + 30 - 1.4]) rotate([0, 90, 0]) cylinder(r = 30, h = w + 2, center = true, $fn = 120);
    }
    if (oben == "kuppel")     // domed outwards (call)
        intersection() {
            translate([0, 0, kappe_h - 0.01]) linear_extrude(3) rrect(w, d, eck_r);
            translate([0, 0, kappe_h - 40 + 2.2]) sphere(r = 40, $fn = 120);
        }
    // stem in the middle, connected to the top
    translate([0, 0, kappe_h - 3 - stem_tiefe]) stem();
}

function oberkante(oben) = oben == "kuppel" ? kappe_h + 2.2 : (oben == "mulde" ? kappe_h - 0.8 : kappe_h - 1.4);

// ------------------------------------------------------------ Relief
module relief_text(t, gr = schrift_gr, y = 0) {
    translate([0, y, 0]) linear_extrude(relief_h)
        text(t, size = gr, font = schrift, halign = "center", valign = "center");
}

// Braille: dots 1-2-3 left, 4-5-6 right. Digits = number sign + a..j
BRAILLE = [["1", [1]], ["2", [1, 2]], ["3", [1, 4]], ["4", [1, 4, 5]], ["5", [1, 5]],
           ["6", [1, 2, 4]], ["7", [1, 2, 4, 5]], ["8", [1, 2, 5]], ["9", [2, 4]], ["0", [2, 4, 5]]];
function bpunkte(z) = [for (e = BRAILLE) if (e[0] == z) e[1]][0];
// height of the dish surface at (x, y) – dots sit on the surface
function mulde_z(x, y) = min(kappe_h, kappe_h - 0.8 + 60 - sqrt(max(0, 3600 - x * x - y * y)));
module bzelle(punkte, x0, y0) {
    for (p = punkte) {
        x = x0 + (p <= 3 ? 0 : 2.5);
        y = y0 - ((p - 1) % 3) * 2.5;
        translate([x, y, mulde_z(x, y) - 0.05]) scale([1, 1, 0.6]) sphere(d = 1.5, $fn = 16);
    }
}
module braille_ziffer(z, y0 = 8.2) {
    if (bpunkte(z) != undef) {
        bzelle([3, 4, 5, 6], -4.6, y0);   // number sign
        bzelle(bpunkte(z), 1.6, y0);
    }
}

// ------------------------------------------------------------ Caps
module kappe_ziffer(z) {
    zweifarbig("ziffer") {
        union() {
            koerper(kappe, kappe, "mulde");
            if (z == "5")  // tactile dot like on every phone keypad (in the cap color)
                translate([0, braille ? -8 : -6.2, kappe_h - 0.9]) scale([1, 1, 0.7]) sphere(d = 2.2);
            if (braille) braille_ziffer(z);
        }
        translate([0, 0, kappe_h - 0.9])
            relief_text(z, braille ? 9.5 : schrift_gr, braille ? -2.8 : (z == "5" ? 1.5 : 0));
    }
}

module hoerer2d() {   // telephone handset: bar at the top, ear and mouth piece at the bottom
    translate([0, -2.5]) {
        intersection() {
            difference() { circle(r = 9.2); circle(r = 6.4); }
            polygon([[0, 0], [16, 7], [16, 16], [-16, 16], [-16, 7]]);
        }
        for (s = [-1, 1]) hull() {
            translate([s * 6.9, 4.4]) circle(r = 2.2);
            translate([s * 8.4, -0.6]) circle(r = 2.9);
        }
    }
}

module kappe_anrufen() {
    zweifarbig("anrufen") {
        koerper(kappe, kappe, "kuppel");
        translate([0, 1.5, kappe_h + 1.4]) linear_extrude(relief_h + 0.6) scale(0.95) hoerer2d();
    }
}

module kappe_auflegen() {
    zweifarbig("auflegen") {
        koerper(kappe, kappe, "rinne");
        // raised cross bar in the groove – feels different from the call key
        translate([0, 0, kappe_h - 1.6]) linear_extrude(relief_h + 0.9) rrect(14, 3.2, 1.4);
    }
}

module kappe_nachricht() {   // same size but flat – feels different from dome and groove
    zweifarbig("nachricht") {
    koerper(kappe, kappe, "flach");
    translate([0, 0, kappe_h - 0.02]) linear_extrude(relief_h) difference() {
        union() {
            difference() { square([16, 11], center = true); square([13.6, 8.6], center = true); }
            intersection() {
                square([16, 11], center = true);
                for (s = [-1, 1]) translate([0, 5.5]) rotate(-s * 34) translate([s * 5, 0]) square([10.5, 1.2], center = true);
            }
        }
    }
    }
}

module kappe_info() {
    b = 34; d = 17;
    zweifarbig("info") {
        union() {
            difference() {
                hull() { for (s = [-1, 1]) translate([s * (b - d) / 2, 0, 0]) cylinder(d1 = d + 1.5, d2 = d, h = kappe_h); }
                translate([0, 0, -0.01]) hull() { for (s = [-1, 1]) translate([s * (b - d) / 2, 0, 0]) cylinder(d = d - 2 * wand, h = kappe_h - 3); }
            }
            translate([0, 0, kappe_h - 3 - stem_tiefe]) stem();
        }
        for (y = [-4, 0, 4]) translate([0, y, kappe_h - 0.02]) linear_extrude(relief_h) rrect(22, 1.4, 0.6);
    }
    // 34 mm on one switch is still fine. If it wobbles too much: fit a 2u stabilizer
    // (Cherry, plate mount) and add the cut-outs in the front.
}

module kappe_notruf() {   // round button with nubs, sits recessed under the cover
    d = 18;
    zweifarbig("notruf") {
        union() {
            difference() {
                cylinder(d1 = d + 1.2, d2 = d, h = kappe_h);
                translate([0, 0, -0.01]) cylinder(d = d - 2 * wand, h = kappe_h - 3);
            }
            translate([0, 0, kappe_h - 3 - stem_tiefe]) stem();
        }
        for (a = [0:60:359], r = [0, 5.2]) if (r > 0 || a == 0)   // nubs in a contrasting color
            translate([r * cos(a), r * sin(a), kappe_h]) sphere(d = 2.4, $fn = 16);
    }
}

// ------------------------------------------------------------ Key front
// plate with MX cut-outs and tactile ridges between the keys.
POS = [ // [x, y, type]
    [-1, 0, "a"], [0, 0, "n"], [1, 0, "x"],
    [-1, -1, "1"], [0, -1, "2"], [1, -1, "3"],
    [-1, -2, "4"], [0, -2, "5"], [1, -2, "6"],
    [-1, -3, "7"], [0, -3, "8"], [1, -3, "9"],
    [-1, -4, "*"], [0, -4, "0"], [1, -4, "#"],
    [0, -5, "i"]];

front_b = 3 * raster + 2 * rand;
front_h = 6 * raster + 2 * rand;

// for other files (use <omafon_tasten.scad>): dimensions and key positions
function tastenfront_mass() = [front_b, front_h, raster, platte, steg_h];
function tastenpositionen() = POS;

module front() {
    difference() {
        union() {
            translate([0, -2.5 * raster, platte / 2]) cube([front_b, front_h, platte], center = true);
            // ridges: grid between the keys, for feeling along
            translate([0, -2.5 * raster, platte]) linear_extrude(steg_h) difference() {
                square([front_b, front_h], center = true);
                for (p = POS) translate([p[0] * raster, (p[1] + 2.5) * raster])
                    if (p[2] == "i") rrect(40, raster - steg_b, 4);
                    else rrect(raster - steg_b, raster - steg_b, 3);
            }
        }
        for (p = POS) translate([p[0] * raster, p[1] * raster, -1])
            cube([ausschnitt, ausschnitt, 10], center = true);
    }
}

// ------------------------------------------------------------ Selection
module kappe_fuer(art) {   // colors come from FARBEN (two-color)
    if (art == "a") kappe_anrufen();
    else if (art == "x") kappe_auflegen();
    else if (art == "n") kappe_nachricht();
    else if (art == "i") kappe_info();
    else kappe_ziffer(art);
}

if (teil == "ziffer") kappe_ziffer(ziffer);
else if (teil == "anrufen") kappe_anrufen();
else if (teil == "auflegen") kappe_auflegen();
else if (teil == "nachricht") kappe_nachricht();
else if (teil == "info") kappe_info();
else if (teil == "notruf") kappe_notruf();
else if (teil == "front") front();
else {
    color("#333") front();
    for (p = POS) translate([p[0] * raster, p[1] * raster, platte + 5]) kappe_fuer(p[2]);
}
