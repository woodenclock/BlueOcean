from pathlib import Path
from typing import Any, Literal

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ROBOTS_FILE = DATA_DIR / "robots.json"
LIF_FILE = DATA_DIR / "layout.lif.json"


class Coords(BaseModel):
    x: float
    y: float
    z: float = 0.0


class RobotWaypoint(Coords):
    id: str | int
    label: str | None = None


class RobotConfig(BaseModel):
    id: str
    name: str | None = None
    position: Coords | None = None
    target: Coords | None = None
    path: list[RobotWaypoint] | None = None
    startWaypointIndex: int = 0
    loop: bool = False
    speed: float = 1.0
    enabled: bool = True
    rotationZ: float = 0.0
    scale: float | dict[str, float] = 1.0
    coordinateSystem: Literal["navigation", "world"] = "world"


class RobotsResponse(BaseModel):
    coordinateSystem: Literal["navigation", "world"] = "world"
    robots: list[RobotConfig] = Field(default_factory=list)


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in {path.name}: {exc}",
        ) from exc


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


@app.get("/")
def root():
    return {"message": "FastAPI backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scene")
def get_scene_config():
    return {
        "sceneUrl": "/RMF2_SIM/Test_3.glb",
        "robotModelUrl": "/robot.glb",
        "robotsConfigUrl": "/api/robots",
        "robotConfigRefreshMs": 1000,
    }


@app.get("/api/robots", response_model=RobotsResponse)
def get_robots():
    payload = read_json_file(
        ROBOTS_FILE,
        default={
            "coordinateSystem": "world",
            "robots": [],
        },
    )

    # Supports both:
    # 1. [{...robot}]
    # 2. {"coordinateSystem": "world", "robots": [{...robot}]}
    if isinstance(payload, list):
        return {
            "coordinateSystem": "world",
            "robots": payload,
        }

    return payload


@app.put("/api/robots", response_model=RobotsResponse)
def update_robots(payload: RobotsResponse):
    data = payload.model_dump(mode="json")
    write_json_file(ROBOTS_FILE, data)
    return data


@app.get("/api/lif")
def get_lif_layout():
    return read_json_file(
        LIF_FILE,
        default={
            "metaInformation": {
                "projectIdentification": "Dashboard Demo",
                "creator": "Dashboard API",
                "lifVersion": "1.0.0",
            },
            "layouts": [],
        },
    )