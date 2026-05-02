from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "reef_factory_kh"

WS_URL: Final = "wss://api.reeffactory.com:443/controler"
WS_PROTOCOL: Final = "reeffactory"

CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_SERIAL: Final = "serial"

UPDATE_INTERVAL: Final = timedelta(minutes=30)
WS_TIMEOUT: Final = 45  # seconds for the full fetch cycle
WS_RECEIVE_TIMEOUT: Final = 15  # seconds per ws.receive() call
WS_MAX_MESSAGES: Final = 30  # max messages to read before giving up

SCALE: Final = 1 / 10000  # fixed-point divisor for KH values

INTERVAL_LABELS: Final[dict[int, str]] = {
    0: "1h",
    1: "2h",
    2: "4h",
    3: "6h",
    4: "8h",
    5: "12h",
    6: "off",
    7: "custom",
}
