"""Run separately: uvicorn core.playground.main:app --host 127.0.0.1 --port 8001."""
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .engine import apply, geometry, simulate, schedule_launch
from .models import ApplyRequest, CreateRequest, Scene, SimulateRequest, Simulation, SceneSimulateRequest, SceneSimulation, ScheduleLaunchRequest
from .ensemble import simulate_scene
from .planning import PlannedSimulation, PlannedSimulationRequest, plan_simulation
from .generation import router as generation_router

app = FastAPI(title="Physica Playground API", version="0.1.0",
              description="Local prototype: SI units, XY motion, +y upward. Stateless scene commands; no executable code.")
app.include_router(generation_router)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc):
    # Do not echo invalid inputs: raw NaN/Infinity cannot be serialized as JSON.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "type": error["type"], "msg": error["msg"]}
        for error in exc.errors()
    ]})


@app.post("/v1/scenes", response_model=Scene)
def create_scene(request: CreateRequest):
    return Scene(gravity=request.gravity)


@app.post("/v1/scenes/apply", response_model=Scene)
def apply_commands(request: ApplyRequest):
    try:
        return apply(request)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/scenes/validate", response_model=Scene)
def validate_scene(scene: Scene):
    return scene


@app.post('/v1/scenes/schedule', response_model=Scene)
def set_launch_time(request: ScheduleLaunchRequest):
    try:
        return schedule_launch(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/simulations", response_model=Simulation)
def run_simulation(request: SimulateRequest):
    try:
        return simulate(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/geometry")
def render_geometry(scene: Scene):
    try:
        return {"scene_id": scene.id, "revision": scene.revision, "meshes": geometry(scene)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/v1/simulations/scene', response_model=SceneSimulation)
def run_scene_simulation(request: SceneSimulateRequest):
    try:
        return simulate_scene(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/simulations/planned", response_model=PlannedSimulation)
def run_planned_simulation(request: PlannedSimulationRequest):
    try:
        return plan_simulation(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
