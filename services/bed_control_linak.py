from __future__ import annotations

import asyncio

from bleak import BleakClient, BleakError, BleakScanner

from enums.bed_direction import Direction
from enums.bed_part import BedPart
from errors.not_connected_error import NotConnectedError
from services.bed_control_base import BedControlBase

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
_SCAN_TIMEOUT_S = 20
_CONNECT_TIMEOUT_S = 30
_CONNECT_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_S = 1.0


class BedControlLinak(BedControlBase):

    def __init__(self, address: str):
        self._address = address
        self._client: BleakClient | None = None
        self._backrest_position = 0
        self._legs_position = 0

    async def connect(self) -> None:
        last_error: Exception | None = None
        for _ in range(_CONNECT_ATTEMPTS):
            device = await BleakScanner.find_device_by_address(self._address, timeout=_SCAN_TIMEOUT_S)
            if device is None:
                last_error = NotConnectedError(f"Cama nao encontrada: {self._address}")
                await asyncio.sleep(_CONNECT_RETRY_DELAY_S)
                continue

            client = BleakClient(device, timeout=_CONNECT_TIMEOUT_S)
            try:
                await client.connect()
            except BleakError as e:
                last_error = e
                await asyncio.sleep(_CONNECT_RETRY_DELAY_S)
                continue

            self._client = client
            await self._client.start_notify(_UUID_POS_BACKREST, self._on_backrest_notify)
            await self._client.start_notify(_UUID_POS_LEGS, self._on_legs_notify)
            return

        raise NotConnectedError(f"Falha ao conectar na cama apos {_CONNECT_ATTEMPTS} tentativas: {last_error}")

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
