// Omafon – shared dimensions for housing and cradle.
// Included with "include". Change them only here, then phone and cradle
// keep fitting together. Choose the variant with -D 'variante="hybrid"'.

/* [Variant] */
variante = "festnetz"; // [festnetz, hybrid]
// the check is at the bottom (after all assignments) so that -D 'variante=…' applies.

// outer dimensions of the handset (without key caps). Width/length follow from the
// key front (3 x 24 mm grid + margin = 84 x 156 mm) plus frame.
gehaeuse_breite = 94;
gehaeuse_laenge = 210;
// landline without a modem is thinner; hybrid carries the SIM7600 HAT on the Pi.
function dicke_fuer(v) = v == "festnetz" ? 30 : 36;
gehaeuse_dicke = dicke_fuer(variante);
gehaeuse_eck_r = 10;     // corners in top view
gehaeuse_kante_r = 5;    // rounding front/back to the sides
gehaeuse_wand = 2.2;

// charging contacts (underside of the handset <-> spring contacts in the cradle)
kontakt_pins = 5;        // 1 +5V, 2 GND, 3 GND, 4 LS+, 5 LS-  (from the left, looking at the front)
kontakt_raster = 5.0;
kontakt_pad_d = 5.0;     // brass discs in the handset
magnet_d = 8.2;          // 2 magnets (cradle) / 2 steel discs (handset)
magnet_h = 3.2;
function magnet_x() = (kontakt_pins * kontakt_raster + 6 - 0.4) / 2 + 1;

// coding: rib at the back of the slot <-> groove at the back of the handset
kodier_b = 6;
kodier_t = 2.5;
kodier_nut_l = 40;       // groove length on the handset from the bottom edge

assert(variante == "festnetz" || variante == "hybrid",
       str("variante must be \"festnetz\" or \"hybrid\" (the pure mobile phone no longer exists), not \"", variante, "\""));
