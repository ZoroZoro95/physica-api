"""Opt-in local question-to-scene generation. Not a public authenticated API."""
import json
import os
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from groq import Groq
from pydantic import Field, ValidationError, field_validator

from .agent import ModelOutputTruncated, run_agent
from .engine import apply, geometry, simulate
from .models import ApplyRequest, CreateRequest, Model, Scene, SimulateRequest, Simulation
from .planning import PlannedSimulationRequest, plan_simulation

router = APIRouter()
generation_lock = Lock()
REPORT_ROOT = Path(__file__).resolve().parents[2] / 'questions/debug_reports/playground-agent'


class GenerateRequest(Model):
    question: str = Field(min_length=1, max_length=12_000)

    @field_validator('question')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Enter a question')
        return value.strip()


class GenerateResponse(Model):
    status: Literal['review', 'needs_clarification', 'unsupported', 'failed']
    reason: str
    assumptions: list[str]
    report_id: str
    scene: Scene | None = None
    simulation: Simulation | None = None
    meshes: list[dict] = Field(default_factory=list)


class LocalPlaygroundAPI:
    """Same validated operations as HTTP, without calling our own server."""

    def post(self, path, *, json):
        request = httpx.Request('POST', 'http://playground.local'+path)
        try:
            if path == '/v1/scenes':
                result = Scene(gravity=CreateRequest.model_validate(json).gravity)
            elif path == '/v1/scenes/apply':
                result = apply(ApplyRequest.model_validate(json))
            elif path == '/v1/simulations':
                result = simulate(SimulateRequest.model_validate(json))
            elif path == '/v1/simulations/planned':
                result = plan_simulation(PlannedSimulationRequest.model_validate(json))
            else:
                return httpx.Response(404, json={'detail': 'Unknown playground operation'}, request=request)
            return httpx.Response(200, json=result.model_dump(mode='json'), request=request)
        except ValidationError as exc:
            detail = '; '.join(
                ('.'.join(map(str, error['loc'])) or 'scene') + ': ' + error['msg']
                for error in exc.errors(include_input=False, include_url=False, include_context=False)
            )
            return httpx.Response(422, json={'detail': detail[:2000]}, request=request)
        except ValueError as exc:
            return httpx.Response(422, json={'detail': str(exc)[:2000]}, request=request)


def model_completion(client, model):
    def complete(messages, tools):
        result = client.chat.completions.create(model=model, messages=messages,
            tools=tools, tool_choice='required', parallel_tool_calls=False,
            temperature=0, max_completion_tokens=2000)
        if result.choices[0].finish_reason == 'length':
            raise ModelOutputTruncated()
        message = result.choices[0].message
        return {'content': message.content,
            'tool_calls': [call.model_dump() for call in message.tool_calls or []]}
    return complete


@router.post('/v1/generate', response_model=GenerateResponse)
def generate(request: GenerateRequest):
    if os.getenv('PLAYGROUND_AI_ENABLED') != '1':
        raise HTTPException(503, 'AI generation is disabled on this server.')
    key, model = os.getenv('GROQ_API_KEY'), os.getenv('PLAYGROUND_MODEL')
    if not key or not model:
        raise HTTPException(503, 'Configure GROQ_API_KEY and PLAYGROUND_MODEL on the backend.')
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(429, 'A scene is already being generated. Wait for it to finish.')
    try:
        # No provider retries/sleeps in an interactive request. The atomic agent
        # itself permits at most three rounds, including one tool repair.
        with Groq(api_key=key, timeout=20, max_retries=0) as client:
            report = run_agent(request.question, model_completion(client, model),
                LocalPlaygroundAPI(), atomic=True, max_rounds=3, max_calls=3)
        report.update(model=model, orchestration='atomic_scene_recipe')
        report_id = str(uuid4())
        destination = REPORT_ROOT / report_id
        destination.mkdir(parents=True, mode=0o700)
        (destination / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        scene = Scene.model_validate(report['scene']) if report['scene'] else None
        if scene:
            (destination / 'scene.json').write_text(scene.model_dump_json(indent=2)+'\n')
        return GenerateResponse(status=report['status'], reason=report['reason'],
            assumptions=report['assumptions'], report_id=report_id, scene=scene,
            simulation=report['simulation'], meshes=geometry(scene) if scene else [])
    except OSError:
        raise HTTPException(503, 'Unable to save the generation report. The current scene has not been replaced.') from None
    finally:
        generation_lock.release()
