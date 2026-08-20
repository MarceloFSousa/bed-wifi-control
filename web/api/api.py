from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from enums.bed_direction import Direction
from enums.bed_part import BedPart
from errors.bed_control_error import BedControlError
from services.bed_control_base import BedControlBase
from services.bed_control_linak import BedControlLinak

if getattr(sys, "frozen", False):
    _APP_DIR = Path(sys.executable).resolve().parent
    _FRONTEND_DIR = Path(sys._MEIPASS) / "frontend"  # type: ignore[attr-defined]
else:
    _APP_DIR = Path(__file__).resolve().parent.parent.parent
    _FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

load_dotenv(_APP_DIR / ".env")

_ADDR_ENV_VAR = "BED_ADDRESS"

_PARTS = {"backrest": BedPart.BACKREST, "legs": BedPart.LEGS}
_DIRECTIONS = {"up": Direction.UP, "down": Direction.DOWN}


class MoveRequest(BaseModel):
    part: str
    direction: str
    seconds: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    address = os.environ.get(_ADDR_ENV_VAR)
    if not address:
        raise RuntimeError(f"Defina o endereco BLE da cama na variavel de ambiente {_ADDR_ENV_VAR}.")

    bed = BedControlLinak(address)
    await bed.connect()
    app.state.bed = bed
    try:
        yield
    finally:
        await bed.disconnect()


app = FastAPI(lifespan=lifespan)


def get_bed(request: Request) -> BedControlBase:
    return request.app.state.bed


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.post("/api/move")
async def move(req: MoveRequest, bed: BedControlBase = Depends(get_bed)) -> dict:
    if req.part not in _PARTS or req.direction not in _DIRECTIONS:
        raise HTTPException(status_code=400, detail="part ou direction invalido")

    try:
        await bed.move(_PARTS[req.part], _DIRECTIONS[req.direction], req.seconds)
    except BedControlError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"backrest": bed.backrest_position, "legs": bed.legs_position}


@app.post("/api/stop")
async def stop(bed: BedControlBase = Depends(get_bed)) -> dict:
    try:
        await bed.stop()
    except BedControlError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"backrest": bed.backrest_position, "legs": bed.legs_position}


@app.post("/api/memory/save/{memory_id}")
async def save_memory(memory_id: int, bed: BedControlBase = Depends(get_bed)) -> dict:
    try:
        await bed.save_memory(memory_id)
    except BedControlError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"ok": True}


@app.post("/api/memory/recall/{memory_id}")
async def recall_memory(memory_id: int, bed: BedControlBase = Depends(get_bed)) -> dict:
    try:
        await bed.recall_memory(memory_id)
    except BedControlError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"ok": True}


app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8000)))
