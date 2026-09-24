"""Tests for the DCSP framing layer (Track D, D1).

Byte sequences below are computed by hand against the DAIDE specification's
DCSP header format (message type, padding, big-endian length, then body) --
not imported from `old_implementation`, per Track D's Ground Rules. Async
framing is exercised with `asyncio.StreamReader.feed_data`/`feed_eof` rather
than a real socket, matching `pytest.ini`'s `asyncio_mode = auto`.
"""

from __future__ import annotations

import asyncio

import pytest

from server.daide.wire import (
    MAGIC_NUMBER,
    PROTOCOL_VERSION,
    DaideWireError,
    DiplomacyMessage,
    ErrorCode,
    ErrorMessage,
    FinalMessage,
    InitialMessage,
    MessageType,
    RepresentationMessage,
    read_message,
    write_message,
)


def _reader_for(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


# ---------------------------------------------------------------------------
# Encoding: byte-exact framing for each message type
# ---------------------------------------------------------------------------


def test_initial_message_bytes():
    message = InitialMessage()
    assert bytes(message.to_bytes()) == bytes(
        (MessageType.INITIAL, 0, 0, 4, 0, PROTOCOL_VERSION, 0xDA, 0x10)
    )


def test_initial_message_magic_number_constant():
    assert MAGIC_NUMBER == 0xDA10


def test_representation_message_bytes():
    assert RepresentationMessage().to_bytes() == bytes((MessageType.REPRESENTATION, 0, 0, 0))


def test_final_message_bytes():
    assert FinalMessage().to_bytes() == bytes((MessageType.FINAL, 0, 0, 0))


def test_error_message_bytes():
    message = ErrorMessage(code=ErrorCode.IM_WRONG_MAGIC_NUMBER)
    assert message.to_bytes() == bytes((MessageType.ERROR, 0, 0, 2, 0, 0x04))


def test_diplomacy_message_bytes_empty_payload():
    assert DiplomacyMessage(b"").to_bytes() == bytes((MessageType.DIPLOMACY, 0, 0, 0))


def test_diplomacy_message_bytes_with_payload():
    payload = bytes((0x48, 0x04))  # HLO token
    message = DiplomacyMessage(payload)
    assert message.to_bytes() == bytes((MessageType.DIPLOMACY, 0, 0, 2)) + payload


def test_diplomacy_message_length_is_two_bytes_big_endian():
    payload = bytes(300)  # forces the length field's high byte to be nonzero
    message = DiplomacyMessage(payload)
    header = message.to_bytes()[:4]
    assert header[2] == 300 // 256
    assert header[3] == 300 % 256


def test_diplomacy_message_rejects_odd_length_payload():
    with pytest.raises(ValueError):
        DiplomacyMessage(b"\x01\x02\x03")


# ---------------------------------------------------------------------------
# Decoding via read_message, fed through a StreamReader
# ---------------------------------------------------------------------------


async def test_read_initial_message():
    data = bytes((MessageType.INITIAL, 0, 0, 4, 0, 1, 0xDA, 0x10))
    message = await read_message(_reader_for(data))
    assert isinstance(message, InitialMessage)
    assert message.version == 1


async def test_read_representation_message():
    data = bytes((MessageType.REPRESENTATION, 0, 0, 0))
    message = await read_message(_reader_for(data))
    assert isinstance(message, RepresentationMessage)


async def test_read_final_message():
    data = bytes((MessageType.FINAL, 0, 0, 0))
    message = await read_message(_reader_for(data))
    assert isinstance(message, FinalMessage)


async def test_read_error_message():
    data = bytes((MessageType.ERROR, 0, 0, 2, 0, 0x09))
    message = await read_message(_reader_for(data))
    assert isinstance(message, ErrorMessage)
    assert message.code is ErrorCode.MESSAGE_SHORTER_THAN_DECLARED


async def test_read_diplomacy_message_roundtrips_payload():
    payload = bytes((0x48, 0x18, 0x51, 0x0A))  # SUB PAR (arbitrary token pair)
    data = bytes((MessageType.DIPLOMACY, 0, 0, len(payload))) + payload
    message = await read_message(_reader_for(data))
    assert isinstance(message, DiplomacyMessage)
    assert message.payload == payload


async def test_read_message_rejects_wrong_version():
    data = bytes((MessageType.INITIAL, 0, 0, 4, 0, 99, 0xDA, 0x10))
    with pytest.raises(DaideWireError) as exc_info:
        await read_message(_reader_for(data))
    assert exc_info.value.code is ErrorCode.VERSION_INCOMPATIBLE


async def test_read_message_rejects_swapped_endian_magic_number():
    data = bytes((MessageType.INITIAL, 0, 0, 4, 0, 1, 0x10, 0xDA))
    with pytest.raises(DaideWireError) as exc_info:
        await read_message(_reader_for(data))
    assert exc_info.value.code is ErrorCode.IM_WRONG_ENDIAN


async def test_read_message_rejects_wrong_magic_number():
    data = bytes((MessageType.INITIAL, 0, 0, 4, 0, 1, 0x12, 0x34))
    with pytest.raises(DaideWireError) as exc_info:
        await read_message(_reader_for(data))
    assert exc_info.value.code is ErrorCode.IM_WRONG_MAGIC_NUMBER


async def test_read_message_rejects_short_initial_body():
    data = bytes((MessageType.INITIAL, 0, 0, 2, 0, 1))
    with pytest.raises(DaideWireError) as exc_info:
        await read_message(_reader_for(data))
    assert exc_info.value.code is ErrorCode.MESSAGE_SHORTER_THAN_DECLARED


async def test_read_message_rejects_odd_length_diplomacy_body():
    data = bytes((MessageType.DIPLOMACY, 0, 0, 3, 0x01, 0x02, 0x03))
    with pytest.raises(DaideWireError) as exc_info:
        await read_message(_reader_for(data))
    assert exc_info.value.code is ErrorCode.INVALID_TOKEN_IN_DM


async def test_read_message_rejects_unknown_message_type():
    data = bytes((99, 0, 0, 0))
    with pytest.raises(ValueError):
        await read_message(_reader_for(data))


async def test_read_message_raises_on_truncated_stream():
    data = bytes((MessageType.INITIAL, 0, 0, 4, 0, 1))  # header + 2 of 4 body bytes
    with pytest.raises(asyncio.IncompleteReadError):
        await read_message(_reader_for(data))


# ---------------------------------------------------------------------------
# write_message drives an actual StreamWriter-shaped object
# ---------------------------------------------------------------------------


class _RecordingWriter:
    """A minimal stand-in for `asyncio.StreamWriter`'s write/drain surface."""

    def __init__(self) -> None:
        self.written = b""
        self.drained = False

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        self.drained = True


async def test_write_message_writes_and_drains():
    writer = _RecordingWriter()
    await write_message(writer, FinalMessage())
    assert writer.written == bytes((MessageType.FINAL, 0, 0, 0))
    assert writer.drained


async def test_write_then_read_roundtrips_a_diplomacy_message():
    payload = bytes((0x48, 0x04, 0x41, 0x01))  # HLO ENG
    writer = _RecordingWriter()
    await write_message(writer, DiplomacyMessage(payload))
    message = await read_message(_reader_for(writer.written))
    assert isinstance(message, DiplomacyMessage)
    assert message.payload == payload
