"""The DCSP (Diplomacy Communication Sub-Protocol) framing layer.

Every message on the wire, in both directions, starts with a fixed 4-byte
header:

```
byte 0: message type   (see MessageType)
byte 1: padding         (always 0x00)
bytes 2-3: length of what follows, big-endian, in bytes
```

Five message types make up the handshake and payload exchange:

- `InitialMessage` -- client -> server, first message on a fresh connection.
  Carries the client's protocol version and a fixed magic number so the
  server can detect endianness/version mismatches before trusting anything
  else on the stream.
- `RepresentationMessage` -- server -> client, acknowledges the handshake.
  Zero-length body (a future version may attach a custom token-representation
  table here; this codebase does not use that extension).
- `DiplomacyMessage` -- carries a token-stream payload (see `tokens.py`).
  This is what actual game messages (HLO, MAP, SUB, ORD, ...) ride inside;
  interpreting the payload is D2/D4's job, not this module's.
- `FinalMessage` -- either side signals it is closing the connection.
- `ErrorMessage` -- a framing-level protocol violation, carrying an
  `ErrorCode` the recipient can log or use to close the connection cleanly.

This module is written against `asyncio.StreamReader`/`StreamWriter` because
the DAIDE listener (Track D's D4) is asyncio-based -- see
`docs/specs/fix_plan.md`'s Track D Ground Rules for why Tornado (which
`old_implementation` uses) is not an option here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum

PROTOCOL_VERSION = 1
MAGIC_NUMBER = 0xDA10
_SWAPPED_MAGIC_NUMBER = 0x10DA  # what MAGIC_NUMBER looks like on a wrong-endian peer

_HEADER_LENGTH = 4


class MessageType(IntEnum):
    """The 1-byte discriminator in every DCSP frame header."""

    INITIAL = 0
    REPRESENTATION = 1
    DIPLOMACY = 2
    FINAL = 3
    ERROR = 4


class ErrorCode(IntEnum):
    """Framing-level error codes a peer's `ErrorMessage` can report.

    Values are fixed by the DAIDE specification's DCSP layer (cross-checked
    against `old_implementation/diplomacy/daide/messages.py`'s `ErrorCode`
    for wire compatibility; see Track D's Ground Rules for why that file is
    read-only reference, not something to import from).
    """

    IM_TIMER_EXPIRED = 0x01
    IM_NOT_FIRST_MESSAGE = 0x02
    IM_WRONG_ENDIAN = 0x03
    IM_WRONG_MAGIC_NUMBER = 0x04
    VERSION_INCOMPATIBLE = 0x05
    MULTIPLE_IM_SENT = 0x06
    IM_SENT_BY_SERVER = 0x07
    UNKNOWN_MESSAGE_TYPE = 0x08
    MESSAGE_SHORTER_THAN_DECLARED = 0x09
    DM_BEFORE_RM = 0x0A
    RM_NOT_FIRST_SERVER_MESSAGE = 0x0B
    MULTIPLE_RM_SENT = 0x0C
    RM_SENT_BY_CLIENT = 0x0D
    INVALID_TOKEN_IN_DM = 0x0E


class DaideWireError(Exception):
    """A framing-level protocol violation encountered while decoding a frame.

    Carries the `ErrorCode` a server should echo back to the offending peer
    inside an `ErrorMessage`, so callers only need to catch this one type
    and forward `.code` rather than re-deriving it from the failure.
    """

    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(detail or code.name)
        self.code = code


def _pack_header(message_type: MessageType, length: int) -> bytes:
    return bytes((message_type.value, 0, (length >> 8) & 0xFF, length & 0xFF))


@dataclass(frozen=True)
class InitialMessage:
    """Client -> server handshake: protocol version + magic number."""

    version: int = PROTOCOL_VERSION

    def to_bytes(self) -> bytes:
        return _pack_header(MessageType.INITIAL, 4) + bytes(
            ((self.version >> 8) & 0xFF, self.version & 0xFF, MAGIC_NUMBER >> 8, MAGIC_NUMBER & 0xFF)
        )


@dataclass(frozen=True)
class RepresentationMessage:
    """Server -> client handshake acknowledgement. Always zero-length."""

    def to_bytes(self) -> bytes:
        return _pack_header(MessageType.REPRESENTATION, 0)


@dataclass(frozen=True)
class DiplomacyMessage:
    """Carries one token-stream payload (an even number of bytes)."""

    payload: bytes = field(default=b"")

    def __post_init__(self) -> None:
        if len(self.payload) % 2 != 0:
            raise ValueError(f"a diplomacy message payload must have even length, got {len(self.payload)}")

    def to_bytes(self) -> bytes:
        return _pack_header(MessageType.DIPLOMACY, len(self.payload)) + self.payload


@dataclass(frozen=True)
class FinalMessage:
    """Either side signals the connection is closing. Always zero-length."""

    def to_bytes(self) -> bytes:
        return _pack_header(MessageType.FINAL, 0)


@dataclass(frozen=True)
class ErrorMessage:
    """Reports a `DaideWireError`'s code to the peer. Always 2-byte body."""

    code: ErrorCode

    def to_bytes(self) -> bytes:
        return _pack_header(MessageType.ERROR, 2) + bytes((0, self.code.value))


Message = InitialMessage | RepresentationMessage | DiplomacyMessage | FinalMessage | ErrorMessage


def _decode_initial(payload: bytes) -> InitialMessage:
    if len(payload) != 4:
        raise DaideWireError(
            ErrorCode.MESSAGE_SHORTER_THAN_DECLARED,
            f"initial message body must be 4 bytes, got {len(payload)}",
        )
    version = (payload[0] << 8) | payload[1]
    magic = (payload[2] << 8) | payload[3]
    if version != PROTOCOL_VERSION:
        raise DaideWireError(ErrorCode.VERSION_INCOMPATIBLE, f"client sent protocol version {version}")
    if magic == _SWAPPED_MAGIC_NUMBER:
        raise DaideWireError(ErrorCode.IM_WRONG_ENDIAN, "magic number arrived byte-swapped")
    if magic != MAGIC_NUMBER:
        raise DaideWireError(ErrorCode.IM_WRONG_MAGIC_NUMBER, f"got magic number 0x{magic:04X}")
    return InitialMessage(version=version)


def _decode_diplomacy(payload: bytes) -> DiplomacyMessage:
    if len(payload) % 2 != 0:
        raise DaideWireError(
            ErrorCode.INVALID_TOKEN_IN_DM,
            f"diplomacy message body has odd length {len(payload)}",
        )
    return DiplomacyMessage(payload=payload)


def _decode_error(payload: bytes) -> ErrorMessage:
    if len(payload) != 2:
        raise DaideWireError(
            ErrorCode.MESSAGE_SHORTER_THAN_DECLARED,
            f"error message body must be 2 bytes, got {len(payload)}",
        )
    return ErrorMessage(code=ErrorCode(payload[1]))


async def read_message(reader: asyncio.StreamReader) -> Message:
    """Read one complete DCSP frame off ``reader``.

    Raises `DaideWireError` for a recognised message type whose body fails a
    framing check (bad handshake, odd-length diplomacy payload, ...), and a
    plain `ValueError` for a message type byte outside 0-4 (nothing in the
    spec's error-code table covers a *type* the receiver has never heard of;
    `UNKNOWN_MESSAGE_TYPE` in `ErrorCode` is reserved for the session layer to
    raise once it decides a value it did understand was unexpected in
    context). Propagates `asyncio.IncompleteReadError` unchanged if the
    stream ends mid-frame.
    """
    header = await reader.readexactly(_HEADER_LENGTH)
    length = (header[2] << 8) | header[3]
    payload = await reader.readexactly(length) if length else b""

    message_type = header[0]
    if message_type == MessageType.INITIAL:
        return _decode_initial(payload)
    if message_type == MessageType.REPRESENTATION:
        return RepresentationMessage()
    if message_type == MessageType.DIPLOMACY:
        return _decode_diplomacy(payload)
    if message_type == MessageType.FINAL:
        return FinalMessage()
    if message_type == MessageType.ERROR:
        return _decode_error(payload)
    raise ValueError(f"unknown DAIDE message type byte {message_type}")


async def write_message(writer: asyncio.StreamWriter, message: Message) -> None:
    """Write one complete DCSP frame to ``writer`` and flush it."""
    writer.write(message.to_bytes())
    await writer.drain()
