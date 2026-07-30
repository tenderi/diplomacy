"""The DAIDE token vocabulary: the fixed 2-byte alphabet the wire protocol is
built from.

A DAIDE message body is a stream of 2-byte tokens (see ``wire.py`` for the
4-byte frame header they ride inside). Every token is one of three kinds,
unified here by a single :class:`Token` type:

- A **named** token from the protocol's fixed vocabulary -- powers, provinces,
  unit types, order keywords, commands, and so on. Looked up by exact string
  or exact 2 bytes in the registry built below.
- An **ASCII escape** -- a single Latin-1 character with no assigned token
  (used inside free text such as player names). Byte 0 is the reserved
  ``ASCII_MARKER``; byte 1 is the character's code point.
- A **signed integer** in ``[-8192, 8191]`` -- packed directly into the 2
  bytes with no registry lookup at all (byte 0's top two bits are always
  zero, i.e. byte 0 < 0x40, which is how a reader tells it apart from a named
  token or an ASCII escape).

The specific string↔bytes assignments below are not this module's invention:
they are the external DAIDE specification, and any compliant client or
server must use the same values to interoperate. (`old_implementation`'s
`diplomacy/daide/tokens.py` documents the same table and was used, read-only,
to cross-check every value here -- see Track D's Ground Rules in
`docs/specs/done_fixes.md` for why this codebase can't simply import that file.)

Province coverage is scoped to `maps/standard.map` (map variants are out of
scope for this track). This module does **not** hand-maintain a second
province list: `verify_standard_map_coverage()` below loads the real map
topology via `engine.map_loader.load_standard_map()` and asserts this table's
provinces match it exactly, so a future edit to the map file can never
silently drift from the token table. That check does file I/O, so it is not
run at import time (this module stays free of I/O on import, like the rest
of the protocol layer) -- the test suite calls it explicitly.

Three provinces need a translation between this engine's internal 3-letter
code and the string the DAIDE spec assigns, because the spec's short code was
already spoken for elsewhere in the vocabulary:

- engine ``ENG`` (English Channel) -> DAIDE ``ECH`` (``ENG`` is the power
  token for England).
- engine ``BOT`` (Gulf of Bothnia) -> DAIDE ``GOB``.
- engine ``LYO`` (Gulf of Lyon) -> DAIDE ``GOL``.

``daide_province_token()`` applies that translation; everywhere else, an
engine province code and its DAIDE token string are identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ASCII_MARKER = 0x4B

_STR_TO_TOKEN: dict[str, "Token"] = {}
_BYTES_TO_TOKEN: dict[bytes, "Token"] = {}


def _encode_int14(number: int) -> bytes:
    """Pack a signed integer in ``[-8192, 8191]`` into its 2-byte token."""
    if not -8192 <= number <= 8191:
        raise ValueError(f"DAIDE integer tokens must be in [-8192, 8191], got {number}")
    unsigned = number & 0x3FFF  # 14-bit two's complement; top 2 bits of byte 0 stay zero.
    return bytes((unsigned >> 8, unsigned & 0xFF))


def _decode_int14(raw: bytes) -> int:
    """Inverse of `_encode_int14`. Caller must have already checked ``raw[0] < 0x40``."""
    unsigned = (raw[0] << 8) | raw[1]
    return unsigned - 0x4000 if unsigned & 0x2000 else unsigned


@dataclass(frozen=True)
class Token:
    """One 2-byte unit of the DAIDE wire vocabulary.

    ``text`` is the DAIDE string form (a mnemonic like ``"HLO"``, a single
    character for an ASCII escape, or the decimal form of an integer).
    ``number`` is set only for integer tokens.
    """

    text: str
    raw: bytes
    number: Optional[int] = None

    def __post_init__(self) -> None:
        if len(self.raw) != 2:
            raise ValueError(f"a DAIDE token is exactly 2 bytes, got {self.raw!r}")

    @property
    def is_ascii_escape(self) -> bool:
        return self.raw[0] == ASCII_MARKER

    @property
    def is_integer(self) -> bool:
        return self.number is not None and not self.is_ascii_escape

    def __bytes__(self) -> bytes:
        return self.raw

    def __str__(self) -> str:
        return self.text

    def __int__(self) -> int:
        if self.number is None:
            raise ValueError(f"token {self.text!r} carries no integer value")
        return self.number

    @staticmethod
    def from_str(text: str) -> "Token":
        """Look up a named token, falling back to an ASCII escape."""
        known = _STR_TO_TOKEN.get(text)
        if known is not None:
            return known
        if len(text) == 1 and ord(text) <= 255:
            return Token(text=text, raw=bytes((ASCII_MARKER, ord(text))))
        raise ValueError(f"{text!r} is not a known DAIDE token or a single ASCII character")

    @staticmethod
    def from_int(number: int) -> "Token":
        """Build the integer token for ``number`` (no registry lookup)."""
        return Token(text=str(number), raw=_encode_int14(number), number=number)

    @staticmethod
    def from_bytes(raw: bytes) -> "Token":
        """Decode 2 raw bytes into a named token, ASCII escape, or integer."""
        raw = bytes(raw)
        if len(raw) != 2:
            raise ValueError(f"a DAIDE token is exactly 2 bytes, got {raw!r}")
        known = _BYTES_TO_TOKEN.get(raw)
        if known is not None:
            return known
        if raw[0] == ASCII_MARKER:
            return Token(text=chr(raw[1]), raw=raw)
        if raw[0] < 0x40:
            number = _decode_int14(raw)
            return Token(text=str(number), raw=raw, number=number)
        raise ValueError(f"{raw!r} does not decode to a known token, escape, or integer")


def _register(text: str, byte0: int, byte1: int) -> Token:
    raw = bytes((byte0, byte1))
    if text in _STR_TO_TOKEN:
        raise ValueError(f"DAIDE token text {text!r} registered twice")
    if raw in _BYTES_TO_TOKEN:
        raise ValueError(f"DAIDE token bytes {raw!r} registered twice (text {text!r})")
    token = Token(text=text, raw=raw)
    _STR_TO_TOKEN[text] = token
    _BYTES_TO_TOKEN[raw] = token
    return token


# ---------------------------------------------------------------------------
# Symbols (category byte 0x40)
# ---------------------------------------------------------------------------

OPEN_PAREN: Token = _register("(", 0x40, 0x00)
CLOSE_PAREN: Token = _register(")", 0x40, 0x01)

SYMBOL_TOKENS: tuple[Token, ...] = (OPEN_PAREN, CLOSE_PAREN)

# ---------------------------------------------------------------------------
# Powers (0x41) -- the 7 standard-map powers
# ---------------------------------------------------------------------------

AUS: Token = _register("AUS", 0x41, 0x00)
ENG: Token = _register("ENG", 0x41, 0x01)
FRA: Token = _register("FRA", 0x41, 0x02)
GER: Token = _register("GER", 0x41, 0x03)
ITA: Token = _register("ITA", 0x41, 0x04)
RUS: Token = _register("RUS", 0x41, 0x05)
TUR: Token = _register("TUR", 0x41, 0x06)

POWER_TOKENS: tuple[Token, ...] = (AUS, ENG, FRA, GER, ITA, RUS, TUR)

# Engine power name (from `engine.types.STANDARD_POWERS`) -> DAIDE power token.
POWER_TOKEN_BY_ENGINE_NAME: dict[str, Token] = {
    "AUSTRIA": AUS,
    "ENGLAND": ENG,
    "FRANCE": FRA,
    "GERMANY": GER,
    "ITALY": ITA,
    "RUSSIA": RUS,
    "TURKEY": TUR,
}

# DAIDE power token text -> engine power name (D2's reverse direction).
_ENGINE_NAME_BY_POWER_TOKEN_TEXT: dict[str, str] = {
    tok.text: name for name, tok in POWER_TOKEN_BY_ENGINE_NAME.items()
}


def engine_power_name(token: Token) -> str:
    """The `engine.types` power name (e.g. ``"FRANCE"``) for a DAIDE power `Token`.

    Raises ``ValueError`` for any token that is not one of the 7 standard-map
    power tokens (including, deliberately, ``UNO`` -- "unknown power" is a
    valid *unit-clause* placeholder in `clauses.py`, but it is never a real
    engine power, so callers that need a real power must not accept it here).
    """
    try:
        return _ENGINE_NAME_BY_POWER_TOKEN_TEXT[token.text]
    except KeyError:
        raise ValueError(f"{token.text!r} is not a DAIDE power token") from None


# ---------------------------------------------------------------------------
# Unit types (0x42)
# ---------------------------------------------------------------------------

AMY: Token = _register("AMY", 0x42, 0x00)
FLT: Token = _register("FLT", 0x42, 0x01)

UNIT_TOKENS: tuple[Token, ...] = (AMY, FLT)

# ---------------------------------------------------------------------------
# Orders (0x43)
# ---------------------------------------------------------------------------

CTO: Token = _register("CTO", 0x43, 0x20)
CVY: Token = _register("CVY", 0x43, 0x21)
HLD: Token = _register("HLD", 0x43, 0x22)
MTO: Token = _register("MTO", 0x43, 0x23)
SUP: Token = _register("SUP", 0x43, 0x24)
VIA: Token = _register("VIA", 0x43, 0x25)
DSB: Token = _register("DSB", 0x43, 0x40)
RTO: Token = _register("RTO", 0x43, 0x41)
BLD: Token = _register("BLD", 0x43, 0x80)
REM: Token = _register("REM", 0x43, 0x81)
WVE: Token = _register("WVE", 0x43, 0x82)

MOVEMENT_ORDER_TOKENS: tuple[Token, ...] = (HLD, MTO, SUP, CVY, CTO)
RETREAT_ORDER_TOKENS: tuple[Token, ...] = (RTO, DSB)
BUILD_ORDER_TOKENS: tuple[Token, ...] = (BLD, REM, WVE)
ORDER_TOKENS: tuple[Token, ...] = MOVEMENT_ORDER_TOKENS + RETREAT_ORDER_TOKENS + BUILD_ORDER_TOKENS

# ---------------------------------------------------------------------------
# Order-note tokens returned in THX (per-order acknowledgement) (0x44)
# ---------------------------------------------------------------------------

MBV: Token = _register("MBV", 0x44, 0x00)
BPR: Token = _register("BPR", 0x44, 0x01)
CST: Token = _register("CST", 0x44, 0x02)
ESC: Token = _register("ESC", 0x44, 0x03)
FAR: Token = _register("FAR", 0x44, 0x04)
HSC: Token = _register("HSC", 0x44, 0x05)
NAS: Token = _register("NAS", 0x44, 0x06)
NMB: Token = _register("NMB", 0x44, 0x07)
NMR: Token = _register("NMR", 0x44, 0x08)
NRN: Token = _register("NRN", 0x44, 0x09)
NRS: Token = _register("NRS", 0x44, 0x0A)
NSA: Token = _register("NSA", 0x44, 0x0B)
NSC: Token = _register("NSC", 0x44, 0x0C)
NSF: Token = _register("NSF", 0x44, 0x0D)
NSP: Token = _register("NSP", 0x44, 0x0E)
NSU: Token = _register("NSU", 0x44, 0x10)
NVR: Token = _register("NVR", 0x44, 0x11)
NYU: Token = _register("NYU", 0x44, 0x12)
YSC: Token = _register("YSC", 0x44, 0x13)

THX_NOTE_TOKENS: tuple[Token, ...] = (
    MBV,
    BPR,
    CST,
    ESC,
    FAR,
    HSC,
    NAS,
    NMB,
    NMR,
    NRN,
    NRS,
    NSA,
    NSC,
    NSF,
    NSP,
    NSU,
    NVR,
    NYU,
    YSC,
)

# ---------------------------------------------------------------------------
# Order-result tokens returned in ORD (post-resolution) (0x45)
# ---------------------------------------------------------------------------

SUC: Token = _register("SUC", 0x45, 0x00)
BNC: Token = _register("BNC", 0x45, 0x01)
CUT: Token = _register("CUT", 0x45, 0x02)
DSR: Token = _register("DSR", 0x45, 0x03)
FLD: Token = _register("FLD", 0x45, 0x04)
NSO: Token = _register("NSO", 0x45, 0x05)
RET: Token = _register("RET", 0x45, 0x06)

ORD_RESULT_TOKENS: tuple[Token, ...] = (SUC, BNC, CUT, DSR, FLD, NSO, RET)

# ---------------------------------------------------------------------------
# Coasts (0x46) -- the full 8-way DAIDE coast vocabulary. The standard map
# only ever needs NCS/SCS/ECS (BUL/SPA/STP), but MDF map definitions are
# allowed to describe any coast, so all 8 are registered for completeness.
# ---------------------------------------------------------------------------

NCS: Token = _register("NCS", 0x46, 0x00)
NEC: Token = _register("NEC", 0x46, 0x02)
ECS: Token = _register("ECS", 0x46, 0x04)
SEC: Token = _register("SEC", 0x46, 0x06)
SCS: Token = _register("SCS", 0x46, 0x08)
SWC: Token = _register("SWC", 0x46, 0x0A)
WCS: Token = _register("WCS", 0x46, 0x0C)
NWC: Token = _register("NWC", 0x46, 0x0E)

COAST_TOKENS: tuple[Token, ...] = (NCS, NEC, ECS, SEC, SCS, SWC, WCS, NWC)

# `engine.types.Location.coast` spelling ("NC"/"SC"/"EC"/"WC") -> DAIDE coast token.
COAST_TOKEN_BY_ENGINE_SUFFIX: dict[str, Token] = {
    "NC": NCS,
    "SC": SCS,
    "EC": ECS,
    "WC": WCS,
}

# DAIDE coast token text -> `engine.types.Location.coast` spelling (D2's reverse
# direction). Only the 4 the standard map actually uses (NCS/SCS/ECS/WCS) have an
# engine-side meaning; SEC/SWC/NEC/NWC are registered above for MDF completeness
# but have no engine coast suffix to map back to.
_ENGINE_COAST_SUFFIX_BY_TOKEN_TEXT: dict[str, str] = {
    tok.text: suffix for suffix, tok in COAST_TOKEN_BY_ENGINE_SUFFIX.items()
}


def engine_coast_suffix(token: Token) -> str:
    """The `engine.types.Location.coast` spelling for a DAIDE coast `Token`.

    Raises ``ValueError`` for a coast token the standard map never uses
    (``SEC``/``SWC``/``NEC``/``NWC``) or for a non-coast token entirely.
    """
    try:
        return _ENGINE_COAST_SUFFIX_BY_TOKEN_TEXT[token.text]
    except KeyError:
        raise ValueError(
            f"{token.text!r} is not one of this map's coast tokens (NCS/SCS/ECS/WCS)"
        ) from None


# ---------------------------------------------------------------------------
# Seasons / phases (0x47)
# ---------------------------------------------------------------------------

SPR: Token = _register("SPR", 0x47, 0x00)
SUM: Token = _register("SUM", 0x47, 0x01)
FAL: Token = _register("FAL", 0x47, 0x02)
AUT: Token = _register("AUT", 0x47, 0x03)
WIN: Token = _register("WIN", 0x47, 0x04)

SEASON_TOKENS: tuple[Token, ...] = (SPR, SUM, FAL, AUT, WIN)

# ---------------------------------------------------------------------------
# Commands (0x48)
# ---------------------------------------------------------------------------

CCD: Token = _register("CCD", 0x48, 0x00)
DRW: Token = _register("DRW", 0x48, 0x01)
FRM: Token = _register("FRM", 0x48, 0x02)
GOF: Token = _register("GOF", 0x48, 0x03)
HLO: Token = _register("HLO", 0x48, 0x04)
HST: Token = _register("HST", 0x48, 0x05)
HUH: Token = _register("HUH", 0x48, 0x06)
IAM: Token = _register("IAM", 0x48, 0x07)
LOD: Token = _register("LOD", 0x48, 0x08)
MAP: Token = _register("MAP", 0x48, 0x09)
MDF: Token = _register("MDF", 0x48, 0x0A)
MIS: Token = _register("MIS", 0x48, 0x0B)
NME: Token = _register("NME", 0x48, 0x0C)
NOT: Token = _register("NOT", 0x48, 0x0D)
NOW: Token = _register("NOW", 0x48, 0x0E)
OBS: Token = _register("OBS", 0x48, 0x0F)
OFF: Token = _register("OFF", 0x48, 0x10)
ORD: Token = _register("ORD", 0x48, 0x11)
OUT: Token = _register("OUT", 0x48, 0x12)
PRN: Token = _register("PRN", 0x48, 0x13)
REJ: Token = _register("REJ", 0x48, 0x14)
SCO: Token = _register("SCO", 0x48, 0x15)
SLO: Token = _register("SLO", 0x48, 0x16)
SND: Token = _register("SND", 0x48, 0x17)
SUB: Token = _register("SUB", 0x48, 0x18)
SVE: Token = _register("SVE", 0x48, 0x19)
THX: Token = _register("THX", 0x48, 0x1A)
TME: Token = _register("TME", 0x48, 0x1B)
YES: Token = _register("YES", 0x48, 0x1C)
ADM: Token = _register("ADM", 0x48, 0x1D)
SMR: Token = _register("SMR", 0x48, 0x1E)

COMMAND_TOKENS: tuple[Token, ...] = (
    CCD,
    DRW,
    FRM,
    GOF,
    HLO,
    HST,
    HUH,
    IAM,
    LOD,
    MAP,
    MDF,
    MIS,
    NME,
    NOT,
    NOW,
    OBS,
    OFF,
    ORD,
    OUT,
    PRN,
    REJ,
    SCO,
    SLO,
    SND,
    SUB,
    SVE,
    THX,
    TME,
    YES,
    ADM,
    SMR,
)

# ---------------------------------------------------------------------------
# HLO / negotiation parameters (0x49)
# ---------------------------------------------------------------------------

AOA: Token = _register("AOA", 0x49, 0x00)
BTL: Token = _register("BTL", 0x49, 0x01)
ERR: Token = _register("ERR", 0x49, 0x02)
LVL: Token = _register("LVL", 0x49, 0x03)
MRT: Token = _register("MRT", 0x49, 0x04)
MTL: Token = _register("MTL", 0x49, 0x05)
NPB: Token = _register("NPB", 0x49, 0x06)
NPR: Token = _register("NPR", 0x49, 0x07)
PDA: Token = _register("PDA", 0x49, 0x08)
PTL: Token = _register("PTL", 0x49, 0x09)
RTL: Token = _register("RTL", 0x49, 0x0A)
UNO: Token = _register("UNO", 0x49, 0x0B)
DSD: Token = _register("DSD", 0x49, 0x0D)

PARAMETER_TOKENS: tuple[Token, ...] = (
    AOA,
    BTL,
    ERR,
    LVL,
    MRT,
    MTL,
    NPB,
    NPR,
    PDA,
    PTL,
    RTL,
    UNO,
    DSD,
)

# ---------------------------------------------------------------------------
# Press (0x4A) -- syntax tokens for the PRP/ALY/... negotiation grammar. Track
# D scopes press support to opaque, syntax-checked forwarding (see
# docs/specs/done_fixes.md's Ground Rules), so these are registered for
# completeness but D1/D2 do not attempt to parse press semantics.
# ---------------------------------------------------------------------------

ALY: Token = _register("ALY", 0x4A, 0x00)
AND: Token = _register("AND", 0x4A, 0x01)
BWX: Token = _register("BWX", 0x4A, 0x02)
DMZ: Token = _register("DMZ", 0x4A, 0x03)
ELS: Token = _register("ELS", 0x4A, 0x04)
EXP: Token = _register("EXP", 0x4A, 0x05)
FCT: Token = _register("FCT", 0x4A, 0x06)
FOR: Token = _register("FOR", 0x4A, 0x07)
FWD: Token = _register("FWD", 0x4A, 0x08)
HOW: Token = _register("HOW", 0x4A, 0x09)
IDK: Token = _register("IDK", 0x4A, 0x0A)
IFF: Token = _register("IFF", 0x4A, 0x0B)
INS: Token = _register("INS", 0x4A, 0x0C)
OCC: Token = _register("OCC", 0x4A, 0x0E)
ORR: Token = _register("ORR", 0x4A, 0x0F)
PCE: Token = _register("PCE", 0x4A, 0x10)
POB: Token = _register("POB", 0x4A, 0x11)
PRP: Token = _register("PRP", 0x4A, 0x13)
QRY: Token = _register("QRY", 0x4A, 0x14)
SCD: Token = _register("SCD", 0x4A, 0x15)
SRY: Token = _register("SRY", 0x4A, 0x16)
SUG: Token = _register("SUG", 0x4A, 0x17)
THK: Token = _register("THK", 0x4A, 0x18)
THN: Token = _register("THN", 0x4A, 0x19)
TRY: Token = _register("TRY", 0x4A, 0x1A)
VSS: Token = _register("VSS", 0x4A, 0x1C)
WHT: Token = _register("WHT", 0x4A, 0x1D)
WHY: Token = _register("WHY", 0x4A, 0x1E)
XDO: Token = _register("XDO", 0x4A, 0x1F)
XOY: Token = _register("XOY", 0x4A, 0x20)
YDO: Token = _register("YDO", 0x4A, 0x21)
CHO: Token = _register("CHO", 0x4A, 0x22)
BCC: Token = _register("BCC", 0x4A, 0x23)
UNT: Token = _register("UNT", 0x4A, 0x24)
NAR: Token = _register("NAR", 0x4A, 0x25)
CCL: Token = _register("CCL", 0x4A, 0x26)

PRESS_TOKENS: tuple[Token, ...] = (
    ALY,
    AND,
    BWX,
    DMZ,
    ELS,
    EXP,
    FCT,
    FOR,
    FWD,
    HOW,
    IDK,
    IFF,
    INS,
    OCC,
    ORR,
    PCE,
    POB,
    PRP,
    QRY,
    SCD,
    SRY,
    SUG,
    THK,
    THN,
    TRY,
    VSS,
    WHT,
    WHY,
    XDO,
    XOY,
    YDO,
    CHO,
    BCC,
    UNT,
    NAR,
    CCL,
)

# ---------------------------------------------------------------------------
# Provinces -- categories 0x50-0x57, split by topology:
#   0x50 inland, non-supply-center   0x54 coastal, non-supply-center
#   0x51 inland, supply-center       0x55 coastal, supply-center
#   0x52 sea                         0x57 bicoastal, supply-center
# The *set* of provinces is derived from `engine.map_loader.load_standard_map()`
# and checked by `verify_standard_map_coverage()` -- see the module docstring.
# The specific byte pairs are the fixed DAIDE assignment for the standard map.
# ---------------------------------------------------------------------------

BOH: Token = _register("BOH", 0x50, 0x00)
BUR: Token = _register("BUR", 0x50, 0x01)
GAL: Token = _register("GAL", 0x50, 0x02)
RUH: Token = _register("RUH", 0x50, 0x03)
SIL: Token = _register("SIL", 0x50, 0x04)
TYR: Token = _register("TYR", 0x50, 0x05)
UKR: Token = _register("UKR", 0x50, 0x06)

BUD: Token = _register("BUD", 0x51, 0x07)
MOS: Token = _register("MOS", 0x51, 0x08)
MUN: Token = _register("MUN", 0x51, 0x09)
PAR: Token = _register("PAR", 0x51, 0x0A)
SER: Token = _register("SER", 0x51, 0x0B)
VIE: Token = _register("VIE", 0x51, 0x0C)
WAR: Token = _register("WAR", 0x51, 0x0D)

ADR: Token = _register("ADR", 0x52, 0x0E)
AEG: Token = _register("AEG", 0x52, 0x0F)
BAL: Token = _register("BAL", 0x52, 0x10)
BAR: Token = _register("BAR", 0x52, 0x11)
BLA: Token = _register("BLA", 0x52, 0x12)
EAS: Token = _register("EAS", 0x52, 0x13)
ECH: Token = _register("ECH", 0x52, 0x14)
GOB: Token = _register("GOB", 0x52, 0x15)
GOL: Token = _register("GOL", 0x52, 0x16)
HEL: Token = _register("HEL", 0x52, 0x17)
ION: Token = _register("ION", 0x52, 0x18)
IRI: Token = _register("IRI", 0x52, 0x19)
MAO: Token = _register("MAO", 0x52, 0x1A)
NAO: Token = _register("NAO", 0x52, 0x1B)
NTH: Token = _register("NTH", 0x52, 0x1C)
NWG: Token = _register("NWG", 0x52, 0x1D)
SKA: Token = _register("SKA", 0x52, 0x1E)
TYS: Token = _register("TYS", 0x52, 0x1F)
WES: Token = _register("WES", 0x52, 0x20)

ALB: Token = _register("ALB", 0x54, 0x21)
APU: Token = _register("APU", 0x54, 0x22)
ARM: Token = _register("ARM", 0x54, 0x23)
CLY: Token = _register("CLY", 0x54, 0x24)
FIN: Token = _register("FIN", 0x54, 0x25)
GAS: Token = _register("GAS", 0x54, 0x26)
LVN: Token = _register("LVN", 0x54, 0x27)
NAF: Token = _register("NAF", 0x54, 0x28)
PIC: Token = _register("PIC", 0x54, 0x29)
PIE: Token = _register("PIE", 0x54, 0x2A)
PRU: Token = _register("PRU", 0x54, 0x2B)
SYR: Token = _register("SYR", 0x54, 0x2C)
TUS: Token = _register("TUS", 0x54, 0x2D)
WAL: Token = _register("WAL", 0x54, 0x2E)
YOR: Token = _register("YOR", 0x54, 0x2F)

ANK: Token = _register("ANK", 0x55, 0x30)
BEL: Token = _register("BEL", 0x55, 0x31)
BER: Token = _register("BER", 0x55, 0x32)
BRE: Token = _register("BRE", 0x55, 0x33)
CON: Token = _register("CON", 0x55, 0x34)
DEN: Token = _register("DEN", 0x55, 0x35)
EDI: Token = _register("EDI", 0x55, 0x36)
GRE: Token = _register("GRE", 0x55, 0x37)
HOL: Token = _register("HOL", 0x55, 0x38)
KIE: Token = _register("KIE", 0x55, 0x39)
LON: Token = _register("LON", 0x55, 0x3A)
LVP: Token = _register("LVP", 0x55, 0x3B)
MAR: Token = _register("MAR", 0x55, 0x3C)
NAP: Token = _register("NAP", 0x55, 0x3D)
NWY: Token = _register("NWY", 0x55, 0x3E)
POR: Token = _register("POR", 0x55, 0x3F)
ROM: Token = _register("ROM", 0x55, 0x40)
RUM: Token = _register("RUM", 0x55, 0x41)
SEV: Token = _register("SEV", 0x55, 0x42)
SMY: Token = _register("SMY", 0x55, 0x43)
SWE: Token = _register("SWE", 0x55, 0x44)
TRI: Token = _register("TRI", 0x55, 0x45)
TUN: Token = _register("TUN", 0x55, 0x46)
VEN: Token = _register("VEN", 0x55, 0x47)

BUL: Token = _register("BUL", 0x57, 0x48)
SPA: Token = _register("SPA", 0x57, 0x49)
STP: Token = _register("STP", 0x57, 0x4A)

PROVINCE_TOKENS: tuple[Token, ...] = (
    BOH,
    BUR,
    GAL,
    RUH,
    SIL,
    TYR,
    UKR,
    BUD,
    MOS,
    MUN,
    PAR,
    SER,
    VIE,
    WAR,
    ADR,
    AEG,
    BAL,
    BAR,
    BLA,
    EAS,
    ECH,
    GOB,
    GOL,
    HEL,
    ION,
    IRI,
    MAO,
    NAO,
    NTH,
    NWG,
    SKA,
    TYS,
    WES,
    ALB,
    APU,
    ARM,
    CLY,
    FIN,
    GAS,
    LVN,
    NAF,
    PIC,
    PIE,
    PRU,
    SYR,
    TUS,
    WAL,
    YOR,
    ANK,
    BEL,
    BER,
    BRE,
    CON,
    DEN,
    EDI,
    GRE,
    HOL,
    KIE,
    LON,
    LVP,
    MAR,
    NAP,
    NWY,
    POR,
    ROM,
    RUM,
    SEV,
    SMY,
    SWE,
    TRI,
    TUN,
    VEN,
    BUL,
    SPA,
    STP,
)

# Engine province code (`engine.map_loader`) -> DAIDE token string, for the
# three names the spec spells differently than this engine does.
_ENGINE_TO_DAIDE_PROVINCE: dict[str, str] = {
    "ENG": "ECH",
    "BOT": "GOB",
    "LYO": "GOL",
}


def daide_province_token(engine_code: str) -> Token:
    """The `Token` for an `engine.map_loader` province code (e.g. ``"STP"``)."""
    code = engine_code.upper()
    text = _ENGINE_TO_DAIDE_PROVINCE.get(code, code)
    return Token.from_str(text)


# DAIDE token string -> engine province code (D2's reverse direction of
# `daide_province_token`), inverting the same 3-entry rename table.
_DAIDE_TO_ENGINE_PROVINCE: dict[str, str] = {v: k for k, v in _ENGINE_TO_DAIDE_PROVINCE.items()}

# Fast membership check for `engine_province_code` -- built from `PROVINCE_TOKENS`
# once at import time, same coverage `verify_standard_map_coverage()` checks.
_PROVINCE_TOKEN_TEXTS: frozenset[str] = frozenset(t.text for t in PROVINCE_TOKENS)


def engine_province_code(token: Token) -> str:
    """The `engine.map_loader` province code for a DAIDE province `Token`.

    Inverse of `daide_province_token`. Raises ``ValueError`` if ``token`` is
    not one of the registered `PROVINCE_TOKENS` (e.g. a unit-type or order
    token passed by mistake).
    """
    if token.text not in _PROVINCE_TOKEN_TEXTS:
        raise ValueError(f"{token.text!r} is not a DAIDE province token")
    return _DAIDE_TO_ENGINE_PROVINCE.get(token.text, token.text)


def verify_standard_map_coverage() -> None:
    """Assert this table's provinces exactly match `load_standard_map()`.

    Does file I/O (loads `maps/standard.map`), so it is not called at import
    time -- see the module docstring. The test suite calls this directly.
    """
    from engine.map_loader import load_standard_map

    live_provinces = load_standard_map().provinces
    expected = {_ENGINE_TO_DAIDE_PROVINCE.get(p, p) for p in live_provinces}
    registered = {token.text for token in PROVINCE_TOKENS}
    if expected != registered:
        missing = expected - registered
        extra = registered - expected
        raise AssertionError(
            "DAIDE province token table is out of sync with maps/standard.map: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )


ALL_TOKENS: tuple[Token, ...] = tuple(_STR_TO_TOKEN.values())
