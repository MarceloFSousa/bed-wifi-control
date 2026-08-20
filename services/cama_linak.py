
import asyncio
from bleak import BleakScanner, BleakClient

BASE = "-338a-1024-8a49-009c0215f78a"
UUID_CMD = "99fa0002" + BASE

UUID_POS = {
    "pes":     "99fa0025" + BASE,
    "cabeca":  "99fa0026" + BASE,
    "pernas":  "99fa0027" + BASE,  # max 548 -> 45 graus
    "encosto": "99fa0028" + BASE,  # max 820 -> 68 graus
}

# Tabela oficial de comandos (byte -> significado). So o 1o byte varia; o 2o e sempre 0x00.
CMD = {
    "stop":         0xFE,  # o app DESTA cama usa 0xFE (spec sugere 0xFF como alternativa)
    "encosto_sobe": 0x0B, "encosto_desce": 0x0A,
    "pernas_sobe":  0x09, "pernas_desce":  0x08,
    "salvar_memoria_1":  0x38, "salvar_memoria_2":  0x39,
    "salvar_memoria_3":     0x05,
    "memoria_1":    0x0E, "memoria_2":     0x0F, "memoria_3": 0x0C,
    "luz_toggle":   0x94,
}

COMANDOS = list(CMD.items())

REPEAT_MS = 100  # igual ao app (disassembly: 100ms)

class LinakBed:
    def __init__(self, address: str):
        self.address = address
        self._client: BleakClient | None = None

    async def __aenter__(self):
        dev = await BleakScanner.find_device_by_address(self.address, timeout=20)
        if dev is None:
            raise RuntimeError("Cama nao encontrada. App fechado? BT do celular off? Cama acordada?")
        self._client = BleakClient(dev, timeout=30)
        await self._client.connect()
        return self

    async def __aexit__(self, *exc):
        if self._client and self._client.is_connected:
            await self._client.disconnect()

    def _payload(self, name: str) -> bytes:
        return bytes([CMD[name], 0x00])

    async def send(self, name: str):
        await self._client.write_gatt_char(UUID_CMD, self._payload(name), response=False)

    async def hold(self, name: str, duration_s: float):
        stop = self._payload("stop")
        payload = self._payload(name)
        loops = max(1, int(duration_s * 1000 / REPEAT_MS))
        try:
            for _ in range(loops):
                await self._client.write_gatt_char(UUID_CMD, payload, response=False)
                await asyncio.sleep(REPEAT_MS / 1000)
        finally:
            await self._client.write_gatt_char(UUID_CMD, stop, response=False)

    async def read_positions(self) -> dict:
        out = {}
        for nome, uuid in UUID_POS.items():
            try:
                raw = await self._client.read_gatt_char(uuid)
                out[nome] = int.from_bytes(raw[0:2], "little")
            except Exception as e:
                out[nome] = f"erro: {e}"
        return out

    async def watch_positions(self, seconds: float = 10):
        def cb(nome):
            def _inner(_sender, data: bytearray):
                pos = int.from_bytes(data[0:2], "little")
                print(f"[{nome}] pos={pos}  raw={data.hex()}")
            return _inner
        for nome, uuid in UUID_POS.items():
            await self._client.start_notify(uuid, cb(nome))
        await asyncio.sleep(seconds)

ADDR = ""

async def demo():
    async with LinakBed(ADDR) as bed:
        print("Conectado. Posicoes atuais:", await bed.read_positions())
        for i, (nome, byte) in enumerate(COMANDOS):
            print(f"{i}: {nome} (0x{byte:02X})")
        inp = int(input(f"Digite um numero de 0 a {len(COMANDOS)-1} (-1 cancela): "))
        while inp != -1:
            print("Posicoes atual:", await bed.read_positions())
            nome, byte = COMANDOS[inp]
            print(f"Comando selecionado: {nome} -> 0x{byte:02X}")
            input

            await bed.hold(nome, float(input("tempo de execução (exemplo: (2.5) segundos): ")))

            await asyncio.sleep(1)
            print("Posicoes depois:", await bed.read_positions())
            for i, (nome, byte) in enumerate(COMANDOS):
                print(f"{i}: {nome} (0x{byte:02X})")
            inp = int(input(f"Digite um numero de 0 a {len(CMD)-1} (-1 cancela): "))

if __name__ == "__main__":
    asyncio.run(demo())