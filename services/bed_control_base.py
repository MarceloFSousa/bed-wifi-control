from __future__ import annotations

from abc import ABC, abstractmethod

from enums.bed_direction import Direction
from enums.bed_part import BedPart


class BedControlBase(ABC):

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abstractmethod
    def backrest_position(self) -> int:
        ...

    @property
    @abstractmethod
    def legs_position(self) -> int:
        ...

    @abstractmethod
    async def move(self, part: BedPart, direction: Direction, seconds: float) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def save_memory(self, memory_id: int) -> None:
        ...

    @abstractmethod
    async def recall_memory(self, memory_id: int) -> None:
        ...

    async def raise_backrest(self, seconds: float) -> None:
        await self.move(BedPart.BACKREST, Direction.UP, seconds)

    async def lower_backrest(self, seconds: float) -> None:
        await self.move(BedPart.BACKREST, Direction.DOWN, seconds)

    async def raise_legs(self, seconds: float) -> None:
        await self.move(BedPart.LEGS, Direction.UP, seconds)

    async def lower_legs(self, seconds: float) -> None:
        await self.move(BedPart.LEGS, Direction.DOWN, seconds)

    async def __aenter__(self) -> "BedControlBase":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()
