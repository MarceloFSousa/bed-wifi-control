from __future__ import annotations

import asyncio
import logging
import os
import sys

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from enums.bed_direction import Direction
from enums.bed_part import BedPart
from errors.not_connected_error import NotConnectedError
from services.bed_control_base import BedControlBase

logger = logging.getLogger(__name__)

_BASE_UUID = "-338a-1024-8a49-009c0215f78a"
_UUID_CMD = "99fa0002" + _BASE_UUID

_UUID_POS_BACKREST = "99fa0028" + _BASE_UUID  # max 820 -> 68 graus
_UUID_POS_LEGS = "99fa0027" + _BASE_UUID  # max 548 -> 45 graus

# So o 1o byte varia; o 2o e sempre 0x00.
_CMD_STOP = 0xFE
_CMD_MOVE = {
    (BedPart.BACKREST, Direction.UP): 0x0B,
    (BedPart.BACKREST, Direction.DOWN): 0x0A,
    (BedPart.LEGS, Direction.UP): 0x09,
    (BedPart.LEGS, Direction.DOWN): 0x08,
}
_CMD_SAVE_MEMORY = {1: 0x38, 2: 0x39, 3: 0x05}
_CMD_RECALL_MEMORY = {1: 0x0E, 2: 0x0F, 3: 0x0C}

_REPEAT_INTERVAL_S = 0.1  # dead-man switch: motor so anda enquanto recebe o comando
_CONNECT_TIMEOUT_S = 20
_CONNECT_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_S = 1.0

_IS_LINUX = sys.platform == "linux"


def _bluez_device(address: str) -> BLEDevice:
    """Aponta direto para o objeto D-Bus que o BlueZ ja tem em cache.

    Sem isso o bleak escaneia antes de cada connect; no Pi 3B+ (Wi-Fi e BT na mesma
    antena) esse scan concorrente derruba a conexao com le-connection-abort-by-local.
    E o mesmo caminho que o `bluetoothctl connect` usa.
    """
    adapter = os.environ.get("BED_ADAPTER", "hci0")
    path = f"/org/bluez/{adapter}/dev_" + address.upper().replace(":", "_")
    return BLEDevice(address, None, {"path": path})


class BedControlLinak(BedControlBase):

    def __init__(self, address: str):
        self._address = address
        self._client: BleakClient | None = None
        self._backrest_position = 0
        self._legs_position = 0

    async def connect(self) -> None:
        last_error: Exception | None = None

        for attempt in range(1, _CONNECT_ATTEMPTS + 1):
            for target in self._connect_targets():
                logger.info("Conectando na cama %s (tentativa %d)", self._address, attempt)
                client = BleakClient(target, timeout=_CONNECT_TIMEOUT_S)
                try:
                    await client.connect()
                except BleakError as e:
                    logger.warning("Falha ao conectar: %s", e)
                    last_error = e
                    continue

                self._client = client
                await client.start_notify(_UUID_POS_BACKREST, self._on_backrest_notify)
                await client.start_notify(_UUID_POS_LEGS, self._on_legs_notify)
                logger.info("Conectado na cama %s", self._address)
                return

            await asyncio.sleep(_CONNECT_RETRY_DELAY_S)

        raise NotConnectedError(
            f"Falha ao conectar na cama apos {_CONNECT_ATTEMPTS} tentativas: {last_error}"
        )

    def _connect_targets(self) -> list[BLEDevice | str]:
        """Caminho D-Bus primeiro (sem scan); o endereco puro fica de reserva."""
        if _IS_LINUX:
            return [_bluez_device(self._address), self._address]
        return [self._address]

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def backrest_position(self) -> int:
        return self._backrest_position

    @property
    def legs_position(self) -> int:
        return self._legs_position

    async def move(self, part: BedPart, direction: Direction, seconds: float) -> None:
        self._ensure_connected()
        payload = self._payload(_CMD_MOVE[(part, direction)])
        loops = max(1, int(seconds / _REPEAT_INTERVAL_S))
        try:
            for _ in range(loops):
                await self._client.write_gatt_char(_UUID_CMD, payload, response=False)
                await asyncio.sleep(_REPEAT_INTERVAL_S)
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._ensure_connected()
        await self._client.write_gatt_char(_UUID_CMD, self._payload(_CMD_STOP), response=False)

    async def save_memory(self, memory_id: int) -> None:
        self._ensure_connected()
        payload = self._payload(_CMD_SAVE_MEMORY[memory_id])
        await self._client.write_gatt_char(_UUID_CMD, payload, response=False)

    async def recall_memory(self, memory_id: int) -> None:
        self._ensure_connected()
        payload = self._payload(_CMD_RECALL_MEMORY[memory_id])
        await self._client.write_gatt_char(_UUID_CMD, payload, response=False)

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise NotConnectedError("Cama nao conectada.")

    @staticmethod
    def _payload(cmd: int) -> bytes:
        return bytes([cmd, 0x00])

    def _on_backrest_notify(self, _sender, data: bytearray) -> None:
        self._backrest_position = int.from_bytes(data[0:2], "little")

    def _on_legs_notify(self, _sender, data: bytearray) -> None:
        self._legs_position = int.from_bytes(data[0:2], "little")
