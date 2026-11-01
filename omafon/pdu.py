"""SMS-PDU-Kodierung nach 3GPP TS 23.040 / 23.038.

Nur was ein Telefon braucht:
  * SMS-DELIVER dekodieren (GSM-7, UCS-2, 8 Bit, mehrteilige SMS über UDH)
  * SMS-SUBMIT erzeugen (automatisch GSM-7 oder UCS-2, mehrteilig wenn nötig)
  * build_deliver() erzeugt DELIVER-PDUs für Simulation und Tests

PDU-Modus statt Textmodus, weil Umlaute, Emojis und lange SMS im Textmodus
der SIMCom-Module je nach Firmware unzuverlässig sind.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

# Grundtabelle GSM 03.38 (128 Zeichen, Index = Septett-Wert). 0x1B = Escape.
GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ"
    " !\"#¤%&'()*+,-./"
    "0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNO"
    "PQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmno"
    "pqrstuvwxyzäöñüà"
)
assert len(GSM7_BASIC) == 128

GSM7_EXT = {0x0A: "\f", 0x14: "^", 0x28: "{", 0x29: "}", 0x2F: "\\",
            0x3C: "[", 0x3D: "~", 0x3E: "]", 0x40: "|", 0x65: "€"}

_BASIC_REV = {ch: i for i, ch in enumerate(GSM7_BASIC) if i != 0x1B}
_EXT_REV = {ch: code for code, ch in GSM7_EXT.items()}


# --------------------------------------------------------------- Septette
def pack7(septets: list[int]) -> bytes:
    out, acc, bits = bytearray(), 0, 0
    for s in septets:
        acc |= (s & 0x7F) << bits
        bits += 7
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    if bits:
        out.append(acc & 0xFF)
    return bytes(out)


def unpack7(data: bytes, count: int) -> list[int]:
    out, acc, bits = [], 0, 0
    for b in data:
        acc |= b << bits
        bits += 8
        while bits >= 7 and len(out) < count:
            out.append(acc & 0x7F)
            acc >>= 7
            bits -= 7
    return out


def gsm7_encode(text: str) -> list[int] | None:
    """Text -> Septette, oder None wenn ein Zeichen nicht in GSM-7 passt."""
    out: list[int] = []
    for ch in text:
        if ch in _BASIC_REV:
            out.append(_BASIC_REV[ch])
        elif ch in _EXT_REV:
            out += [0x1B, _EXT_REV[ch]]
        else:
            return None
    return out


def gsm7_decode(septets: list[int]) -> str:
    out, esc = [], False
    for s in septets:
        if esc:
            out.append(GSM7_EXT.get(s, " "))
            esc = False
        elif s == 0x1B:
            esc = True
        else:
            out.append(GSM7_BASIC[s])
    return "".join(out)


def _header_septets(udh_len: int) -> int:
    """Anzahl Septette, die ein UDH (inkl. Längenbyte) samt Füllbits belegt."""
    return ((udh_len) * 8 + 6) // 7


# --------------------------------------------------------------- Adressen
def _bcd_swap(digits: str) -> bytes:
    if len(digits) % 2:
        digits += "F"
    return bytes(int(digits[i + 1] + digits[i], 16) for i in range(0, len(digits), 2))


def _bcd_unswap(data: bytes, ndigits: int) -> str:
    s = "".join(f"{b & 0x0F:X}{b >> 4:X}" for b in data)
    return s[:ndigits].replace("F", "")


def encode_address(number: str) -> bytes:
    number = number.strip().replace(" ", "")
    toa = 0x91 if number.startswith("+") else 0x81
    digits = number.lstrip("+")
    return bytes([len(digits), toa]) + _bcd_swap(digits)


def decode_address(data: bytes, pos: int) -> tuple[str, int]:
    ndigits, toa = data[pos], data[pos + 1]
    nbytes = (ndigits + 1) // 2
    raw = data[pos + 2: pos + 2 + nbytes]
    if (toa >> 4) & 0x07 == 0x05:  # alphanumerisch, z. B. "Telekom"
        addr = gsm7_decode(unpack7(raw, ndigits * 4 // 7))
    else:
        addr = _bcd_unswap(raw, ndigits)
        if (toa >> 4) & 0x07 == 0x01:
            addr = "+" + addr
    return addr, pos + 2 + nbytes


def _decode_scts(b: bytes) -> _dt.datetime | None:
    try:
        d = [int(f"{x & 0x0F}{x >> 4}") for x in b[:6]]
        return _dt.datetime(2000 + d[0], d[1], d[2], d[3], d[4], d[5])
    except (ValueError, IndexError):
        return None


# --------------------------------------------------------------- DELIVER
@dataclass
class Deliver:
    sender: str
    text: str
    timestamp: _dt.datetime | None = None
    concat_ref: int | None = None   # Referenz mehrteiliger SMS
    concat_total: int = 1
    concat_seq: int = 1
    raw: str = field(default="", repr=False)


def _alphabet(dcs: int) -> str:
    if dcs & 0xC0 == 0x00:
        return {0: "gsm7", 1: "8bit", 2: "ucs2"}.get((dcs >> 2) & 0x03, "gsm7")
    if dcs & 0xF0 == 0xF0:
        return "8bit" if dcs & 0x04 else "gsm7"
    if dcs & 0xF0 == 0xE0:
        return "ucs2"
    return "gsm7"


def decode_deliver(pdu_hex: str) -> Deliver:
    """Dekodiert eine PDU, wie sie AT+CMGR im PDU-Modus liefert (mit SMSC-Teil)."""
    data = bytes.fromhex(pdu_hex.strip())
    pos = 1 + data[0]                 # SMSC-Information überspringen
    first = data[pos]
    pos += 1
    if first & 0x03 != 0x00:
        raise ValueError("keine SMS-DELIVER-PDU")
    udhi = bool(first & 0x40)
    sender, pos = decode_address(data, pos)
    _pid, dcs = data[pos], data[pos + 1]
    pos += 2
    ts = _decode_scts(data[pos: pos + 7])
    pos += 7
    udl = data[pos]
    ud = data[pos + 1:]
    alphabet = _alphabet(dcs)

    ref, total, seq = None, 1, 1
    udh_len = 0
    if udhi:
        udh_len = ud[0] + 1
        i = 1
        while i < udh_len:
            iei, iel = ud[i], ud[i + 1]
            val = ud[i + 2: i + 2 + iel]
            if iei == 0x00 and iel == 3:
                ref, total, seq = val[0], val[1], val[2]
            elif iei == 0x08 and iel == 4:
                ref, total, seq = (val[0] << 8) | val[1], val[2], val[3]
            i += 2 + iel

    if alphabet == "gsm7":
        septets = unpack7(ud, udl)
        text = gsm7_decode(septets[_header_septets(udh_len):] if udhi else septets)
    elif alphabet == "ucs2":
        text = ud[udh_len:udl].decode("utf-16-be", errors="replace")
    else:
        text = ud[udh_len:udl].decode("latin-1", errors="replace")
    return Deliver(sender, text, ts, ref, total, seq, pdu_hex)


# --------------------------------------------------------------- SUBMIT
@dataclass
class Submit:
    pdu_hex: str      # mit vorangestelltem "00" (Standard-SMSC der SIM)
    tpdu_len: int     # Wert für AT+CMGS=<len>


def _split_gsm7(septets: list[int], size: int) -> list[list[int]]:
    parts, cur = [], []
    i = 0
    while i < len(septets):
        step = 2 if septets[i] == 0x1B else 1      # Escape-Paar nie trennen
        if len(cur) + step > size:
            parts.append(cur)
            cur = []
        cur += septets[i:i + step]
        i += step
    if cur:
        parts.append(cur)
    return parts


def _split_ucs2(text: str, size_units: int) -> list[str]:
    parts, cur, units = [], "", 0
    for ch in text:
        u = 2 if ord(ch) > 0xFFFF else 1           # Surrogatpaare nie trennen
        if units + u > size_units:
            parts.append(cur)
            cur, units = "", 0
        cur += ch
        units += u
    if cur:
        parts.append(cur)
    return parts


def encode_submit(number: str, text: str, ref: int = 0) -> list[Submit]:
    """Erzeugt eine oder mehrere SUBMIT-PDUs. ref = Referenz 0..255."""
    da = encode_address(number)
    septets = gsm7_encode(text)
    if septets is not None:
        dcs = 0x00
        chunks = [septets] if len(septets) <= 160 else _split_gsm7(septets, 153)
    else:
        dcs = 0x08
        units = len(text.encode("utf-16-be")) // 2
        chunks = [text] if units <= 70 else _split_ucs2(text, 67)

    total = len(chunks)
    out: list[Submit] = []
    for seq, chunk in enumerate(chunks, 1):
        udh = bytes([0x05, 0x00, 0x03, ref & 0xFF, total, seq]) if total > 1 else b""
        if dcs == 0x00:
            hs = _header_septets(len(udh)) if udh else 0
            ud = bytearray(pack7([0] * hs + chunk))
            ud[:len(udh)] = udh
            udl = hs + len(chunk)
        else:
            ud = bytearray(udh + chunk.encode("utf-16-be"))
            udl = len(ud)
        first = 0x11 | (0x40 if udh else 0)   # SUBMIT, Gültigkeit relativ, ggf. UDHI
        tpdu = bytes([first, 0x00]) + da + bytes([0x00, dcs, 0xAA, udl]) + bytes(ud)
        out.append(Submit("00" + tpdu.hex().upper(), len(tpdu)))
    return out


# --------------------------------------------------------------- nur Simulation/Test
def build_deliver(sender: str, text: str, when: _dt.datetime | None = None,
                  ref: int = 7) -> list[str]:
    """Baut DELIVER-PDUs (wie vom Netz empfangen). Für Simulator und Tests."""
    when = when or _dt.datetime(2026, 11, 1, 18, 0, 0)
    scts = _bcd_swap(when.strftime("%y%m%d%H%M%S")) + b"\x00"
    oa = encode_address(sender)
    out = []
    for sub in encode_submit(sender, text, ref):
        t = bytes.fromhex(sub.pdu_hex[2:])
        first = t[0]
        udhi = 0x40 if first & 0x40 else 0
        da_len = 2 + (t[2] + 1) // 2
        pos = 2 + da_len
        dcs = t[pos + 1]
        rest = t[pos + 3:]                       # UDL + UD (VP übersprungen)
        tpdu = bytes([0x04 | udhi]) + oa + bytes([0x00, dcs]) + scts + rest
        out.append("00" + tpdu.hex().upper())
    return out
