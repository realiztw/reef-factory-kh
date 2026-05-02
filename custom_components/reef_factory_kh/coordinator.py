"""Coordinator for Reef Factory KH Keeper Plus.

Connects to the Reef Factory Smart Reef WebSocket API, authenticates,
subscribes to a KH Keeper device, and parses the binary data frame.

Protocol summary (reverse-engineered from Smart Reef web app):
  - WebSocket: wss://api.reeffactory.com:443/controler, subprotocol "reeffactory"
  - Binary framing: null-separated ASCII fields then payload, then null terminator
    Frame layout: [serial]\x00[namespace]\x00[command]\x00[session]\x00[payload]\x00
  - Login: namespace="user", command="login"
    Payload: [email]\x00[password]\x00[keep_logged_byte]
  - Login response: namespace="status", payload starts with b'ok' on success
  - Subscribe: namespace="khConnect", command="join"
    Payload: [device_serial]\x00
  - Data push: namespace="khRefresh", command="settings"
    Payload: custom binary struct (see _parse_kh_settings)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SERIAL,
    DOMAIN,
    SCALE,
    UPDATE_INTERVAL,
    WS_MAX_MESSAGES,
    WS_PROTOCOL,
    WS_RECEIVE_TIMEOUT,
    WS_TIMEOUT,
    WS_URL,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wire encoding / decoding
# ---------------------------------------------------------------------------

def _encode_message(
    namespace: str,
    command: str,
    payload: bytes = b"",
    serial: str = "0000000000000000",
    session: str = "",
) -> bytes:
    out = bytearray()
    out += serial.encode("latin-1") + b"\x00"
    out += namespace.encode("latin-1") + b"\x00"
    out += command.encode("latin-1") + b"\x00"
    out += session.encode("latin-1") + b"\x00"
    out += payload
    out += b"\x00"
    return bytes(out)


def _decode_message(data: bytes) -> tuple[str, str, str, str, bytes]:
    buf = bytearray(data)
    parts: list[str] = []
    i = 0
    for _ in range(4):
        end = buf.index(0, i)
        parts.append(buf[i:end].decode("latin-1"))
        i = end + 1
    payload = bytes(buf[i:])
    if payload.endswith(b"\x00"):
        payload = payload[:-1]
    serial, namespace, command, session = parts
    return serial, namespace, command, session, payload


def _build_login_payload(email: str, password: str) -> bytes:
    out = email.encode("latin-1") + b"\x00"
    out += password.encode("latin-1") + b"\x00"
    out += b"\x00"  # keep_logged = False
    return out


# ---------------------------------------------------------------------------
# Binary struct parser for khRefresh/settings
# ---------------------------------------------------------------------------

def _parse_kh_settings(payload: bytes) -> dict[str, Any] | None:
    """Parse the binary payload from a khRefresh/settings WebSocket message.

    Struct layout (big-endian, all integers):
      alarm_kh_low   s32  * SCALE  -> dKH
      alarm_kh_high  s32  * SCALE  -> dKH
      status_byte1   u8
      status_byte2   u8
      interval       u8   (0=1h 1=2h 2=4h 3=6h 4=8h 5=12h 6=off 7=custom)
      kh_adjust      s32  * SCALE  -> dKH offset
      reagent_alert  u8   (0=ok, non-zero=low alert)
      num_readings   u8
      for each reading:
        kh           s32  * SCALE  -> dKH
        ph           s32  * SCALE  -> pH (0 if not measured)
        year         u16
        month        u8
        day          u8
        hour         u8
        minute       u8
        type         u8  (3=error/calibration)
        alert        u8  (4=low 5=high 7=error 8=critical)
      [after readings: reagent_pct u8, waste_pct u8, ... other fields]
    """
    pos = 0

    def u8() -> int:
        nonlocal pos
        if pos >= len(payload):
            raise IndexError(f"u8 read past end at pos={pos}")
        v = payload[pos]
        pos += 1
        return v

    def u16() -> int:
        nonlocal pos
        if pos + 1 >= len(payload):
            raise IndexError(f"u16 read past end at pos={pos}")
        v = (payload[pos] << 8) | payload[pos + 1]
        pos += 2
        return v

    def s32() -> float:
        nonlocal pos
        if pos + 3 >= len(payload):
            raise IndexError(f"s32 read past end at pos={pos}")
        v = int.from_bytes(payload[pos : pos + 4], "big", signed=True)
        pos += 4
        return v * SCALE

    try:
        alarm_kh_low = s32()
        alarm_kh_high = s32()
        _status1 = u8()
        _status2 = u8()
        interval = u8()
        reagent_ml = s32()   # reagent remaining volume in ml (s32 * SCALE)
        reagent_alert = u8()

        num_readings = u8()
        readings: list[dict[str, Any]] = []
        for _ in range(num_readings):
            kh_val = s32()
            ph_val = s32()
            year = u16()
            month = u8()
            day = u8()
            hour = u8()
            minute = u8()
            rtype = u8()
            alert = u8()
            readings.append(
                {
                    "kh": round(kh_val, 4),
                    "ph": round(ph_val, 4) if ph_val > 0 else None,
                    "year": year,
                    "month": month,
                    "day": day,
                    "hour": hour,
                    "minute": minute,
                    "type": rtype,
                    "alert": alert,
                }
            )

        remaining = payload[pos:]
        _LOGGER.debug(
            "khRefresh post-readings bytes (%d bytes): %s",
            len(remaining),
            remaining.hex(),
        )

        latest = readings[0] if readings else None
        last_measurement: str | None = None
        if latest:
            try:
                last_measurement = datetime(
                    latest["year"],
                    latest["month"],
                    latest["day"],
                    latest["hour"],
                    latest["minute"],
                ).isoformat()
            except (ValueError, OverflowError):
                pass

        return {
            "alarm_low": round(alarm_kh_low, 2),
            "alarm_high": round(alarm_kh_high, 2),
            "interval": interval,
            "reagent_ml": round(reagent_ml, 2),
            "reagent_alert": reagent_alert,
            "readings": readings,
            "latest_kh": round(latest["kh"], 2) if latest else None,
            "latest_ph": latest["ph"] if latest else None,
            "last_measurement": last_measurement,
        }

    except (IndexError, ValueError, OverflowError) as exc:
        _LOGGER.warning("Failed to parse khRefresh/settings: %s", exc)
        _LOGGER.debug("Full payload hex (%d bytes): %s", len(payload), payload.hex())
        return None


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class ReefFactoryKHCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches KH Keeper Plus data from the Reef Factory WebSocket API."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Reef Factory KH Keeper {entry_data[CONF_SERIAL]}",
            update_interval=UPDATE_INTERVAL,
        )
        self.email: str = entry_data[CONF_EMAIL]
        self.password: str = entry_data[CONF_PASSWORD]
        self.serial: str = entry_data[CONF_SERIAL]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._fetch_kh_data(), timeout=WS_TIMEOUT
            )
        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timed out communicating with Reef Factory API") from exc

    async def _fetch_kh_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)

        async with session.ws_connect(
            WS_URL,
            protocols=[WS_PROTOCOL],
            receive_timeout=WS_RECEIVE_TIMEOUT,
        ) as ws:
            # 1. Authenticate
            await ws.send_bytes(
                _encode_message(
                    "user", "login", _build_login_payload(self.email, self.password)
                )
            )
            await self._expect_login_ok(ws)

            # 2. Subscribe to the KH device
            join_token = f"join_{int(time.time() * 1000)}"
            await ws.send_bytes(
                _encode_message(
                    "khConnect",
                    "join",
                    self.serial.encode("latin-1") + b"\x00",
                    self.serial,
                    join_token,
                )
            )

            # 3. Read ALL pushed messages after subscribing and merge the data
            return await self._collect_kh_messages(ws)

    async def _expect_login_ok(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        for _ in range(WS_MAX_MESSAGES):
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.BINARY:
                try:
                    _, ns, cmd, _, payload = _decode_message(msg.data)
                    _LOGGER.debug("Login rx: ns=%s cmd=%s", ns, cmd)
                    if ns == "status":
                        if payload[:2] == b"ok":
                            return
                        raise UpdateFailed(
                            "Reef Factory login rejected — check email and password"
                        )
                except UpdateFailed:
                    raise
                except Exception as exc:
                    _LOGGER.debug("Ignoring unparseable message during login: %s", exc)
            elif msg.type in (
                aiohttp.WSMsgType.ERROR,
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
            ):
                raise UpdateFailed(f"WebSocket closed during login ({msg.type})")
        raise UpdateFailed("Login confirmation not received")

    async def _collect_kh_messages(
        self, ws: aiohttp.ClientWebSocketResponse
    ) -> dict[str, Any]:
        """Read all messages pushed after khConnect/join and merge the data.

        The server pushes several khRefresh/* messages in sequence. We read them
        all (up to WS_MAX_MESSAGES) and merge whatever we can parse. Unknown
        messages are logged at DEBUG so we can identify reagent/waste messages.
        """
        result: dict[str, Any] = {}

        for _ in range(WS_MAX_MESSAGES):
            try:
                msg = await ws.receive()
            except asyncio.TimeoutError:
                # No more messages within receive_timeout — done collecting
                break

            if msg.type == aiohttp.WSMsgType.BINARY:
                try:
                    _, ns, cmd, _, payload = _decode_message(msg.data)
                    _LOGGER.debug(
                        "Data rx: ns=%s cmd=%s payload_len=%d hex=%s",
                        ns, cmd, len(payload), payload.hex(),
                    )
                    if ns == "khRefresh" and cmd == "settings":
                        parsed = _parse_kh_settings(payload)
                        if parsed:
                            result.update(parsed)
                            _LOGGER.debug("Parsed settings: %s", parsed)
                    elif ns == "khRefresh":
                        # Log unknown khRefresh sub-commands so we can map them
                        _LOGGER.debug(
                            "UNKNOWN khRefresh/%s payload (%d bytes): %s",
                            cmd, len(payload), payload.hex(),
                        )
                        # Try to parse as reagent volume: s32 big-endian * SCALE
                        if len(payload) >= 4 and cmd in ("reagent", "status", "info", "config"):
                            v = int.from_bytes(payload[:4], "big", signed=True) * SCALE
                            _LOGGER.debug("  First s32*SCALE = %.4f", v)
                    # Ignore other namespaces (user account info, etc.)
                except Exception as exc:
                    _LOGGER.debug("Error parsing message: %s", exc)

            elif msg.type in (
                aiohttp.WSMsgType.ERROR,
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
            ):
                break

        if not result:
            raise UpdateFailed("No KH data received from device")

        _LOGGER.debug("Final merged KH data: %s", result)
        return result


async def async_validate_credentials(
    hass: HomeAssistant, email: str, password: str
) -> bool:
    """Try to authenticate with the Reef Factory API. Returns True on success."""
    session = async_get_clientsession(hass)
    try:
        async with session.ws_connect(
            WS_URL,
            protocols=[WS_PROTOCOL],
            receive_timeout=10,
        ) as ws:
            await ws.send_bytes(
                _encode_message(
                    "user", "login", _build_login_payload(email, password)
                )
            )
            for _ in range(10):
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    _, ns, _, _, payload = _decode_message(msg.data)
                    if ns == "status":
                        return payload[:2] == b"ok"
                elif msg.type in (
                    aiohttp.WSMsgType.ERROR,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                ):
                    return False
    except Exception as exc:
        _LOGGER.debug("Credential validation failed: %s", exc)
    return False
