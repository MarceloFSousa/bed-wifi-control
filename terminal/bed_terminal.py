from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from enums.bed_direction import Direction
from enums.bed_part import BedPart
from errors.bed_control_error import BedControlError
from services.bed_control_base import BedControlBase
from services.bed_control_linak import BedControlLinak

load_dotenv()

_ADDR_ENV_VAR = "BED_ADDRESS"

_ACOES = [
    ("Encosto sobe", BedPart.BACKREST, Direction.UP),
    ("Encosto desce", BedPart.BACKREST, Direction.DOWN),
    ("Pernas sobe", BedPart.LEGS, Direction.UP),
    ("Pernas desce", BedPart.LEGS, Direction.DOWN),
]
_OPCAO_STOP = 4
_OPCOES_SALVAR_MEMORIA = {5: 1, 6: 2, 7: 3}
_OPCOES_RECALL_MEMORIA = {8: 1, 9: 2, 10: 3}


def _print_menu() -> None:
    for i, (nome, _, _) in enumerate(_ACOES):
        print(f"{i}: {nome}")
    print(f"{_OPCAO_STOP}: Parar")
    for opcao, memoria in _OPCOES_SALVAR_MEMORIA.items():
        print(f"{opcao}: Salvar memoria {memoria}")
    for opcao, memoria in _OPCOES_RECALL_MEMORIA.items():
        print(f"{opcao}: Recall memoria {memoria}")


def _print_positions(bed: BedControlBase) -> None:
    print(f"Posicoes -> encosto: {bed.backrest_position}  pernas: {bed.legs_position}")


async def _executar(bed: BedControlBase, opcao: int) -> None:
    if opcao == _OPCAO_STOP:
        await bed.stop()
    elif opcao in _OPCOES_SALVAR_MEMORIA:
        await bed.save_memory(_OPCOES_SALVAR_MEMORIA[opcao])
    elif opcao in _OPCOES_RECALL_MEMORIA:
        await bed.recall_memory(_OPCOES_RECALL_MEMORIA[opcao])
    elif 0 <= opcao < len(_ACOES):
        _, part, direction = _ACOES[opcao]
        seg = float(input("Tempo de execucao (exemplo: 2.5) segundos: "))
        await bed.move(part, direction, seg)
    else:
        print("Opcao invalida.")


async def main() -> None:
    address = os.environ.get(_ADDR_ENV_VAR)
    if not address:
        raise SystemExit(f"Defina o endereco BLE da cama na variavel de ambiente {_ADDR_ENV_VAR}.")

    bed: BedControlBase = BedControlLinak(address)
    async with bed:
        print("Conectado.")
        _print_positions(bed)
        _print_menu()
        opcao = int(input("Digite uma opcao (-1 cancela): "))
        while opcao != -1:
            try:
                await _executar(bed, opcao)
            except BedControlError as e:
                print(f"Erro: {e}")
            await asyncio.sleep(1)
            _print_positions(bed)
            _print_menu()
            opcao = int(input("Digite uma opcao (-1 cancela): "))


if __name__ == "__main__":
    asyncio.run(main())
