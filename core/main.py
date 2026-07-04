import os
import base64
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from dotenv import load_dotenv

from .auth import (
    AuthUser,
    create_session_token,
    optional_auth_user,
    public_user_payload,
    require_auth_user,
    revoke_session_token,
    verify_google_id_token,
)
from .feedback_loop import (
    create_or_update_ticket,
    list_notifications,
    list_tickets,
    mark_notifications_read,
    mark_retry_attempt,
    resolve_ticket,
)
from .db import initialize_app_schema
from .schema import (
    AuthGoogleRequest,
    AuthUserResponse,
    FeedbackRetryResponse,
    FeedbackTicketRequest,
    Session,
    GenerateResponse,
    TeachRequest,
    TeachResponse,
    ExtractQuestionResponse,
    SolveQuestionRequest,
    SolveQuestionResponse,
)
from .prompt_engine import PromptEngine
from .projectile_engine import build_solution_walkthrough, solve_ad_hoc_question
from .projectile_engine.animation_scene import build_animation_scene_spec
from .projectile_engine.classifier import projectile_classifier_mode
from .projectile_engine.templates import PROJECTILE_TEMPLATES
from .question_debug import (
    create_image_report,
    record_extraction,
    record_solve,
    report_path,
)
from .walkthrough_sync_audit import audit_walkthrough_sync

load_dotenv()

app = FastAPI(title="Physics Visualiser API")


def _cors_origins() -> list[str]:
    raw = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or ""
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    local_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if os.getenv("ENVIRONMENT", "").lower() in {"prod", "production"}:
        return origins
    return list(dict.fromkeys([*origins, *local_origins]))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Init ──────────────────────────────────────

api_key = os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
engine = PromptEngine(api_key=api_key) if api_key else None
sessions: dict[str, Session] = {}

try:
    from rag.context_retriever import ContextRetriever
    retriever = ContextRetriever()
    print("RAG loaded.")
except Exception as e:
    retriever = None
    print(f"RAG skipped: {e}")


def require_prompt_engine() -> PromptEngine:
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="LLM provider is not configured. Set GROQ_API_KEY, GOOGLE_API_KEY, or GEMINI_API_KEY.",
        )
    return engine


# ── Routes ────────────────────────────────────

@app.post("/auth/google", response_model=AuthUserResponse)
async def auth_google(req: AuthGoogleRequest):
    user = verify_google_id_token(req.id_token)
    return AuthUserResponse(token=create_session_token(user), user=public_user_payload(user))


@app.get("/auth/me")
async def auth_me(user: AuthUser = Depends(require_auth_user)):
    return {"user": public_user_payload(user)}


@app.post("/auth/logout")
async def auth_logout(authorization: str | None = Header(default=None)):
    if not authorization:
        return {"revoked": 0}
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Use Bearer auth token")
    return {"revoked": revoke_session_token(token)}


@app.post("/extract-question", response_model=ExtractQuestionResponse)
async def extract_question(
    image: UploadFile = File(...),
    hint: str = Form(""),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail="Image file is required")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image file is empty")

    image_mime = image.content_type or "image/jpeg"
    if not image_mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    debug_report_id = create_image_report(
        image_bytes=image_bytes,
        image_mime_type=image_mime,
        image_filename=image.filename,
        hint=hint,
    )

    try:
        prompt_engine = require_prompt_engine()
        extracted = prompt_engine.extract_question_from_image(
            image_bytes=image_bytes,
            image_mime_type=image_mime,
            hint=hint,
        )
        extracted.debug_report_id = debug_report_id
        extracted.debug_report_path = report_path(debug_report_id)
        record_extraction(debug_report_id, extracted)
        return extracted
    except Exception as e:
        record_extraction(debug_report_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Question extraction failed: {e}. Debug report: {report_path(debug_report_id)}",
        )


@app.post("/solve-question", response_model=SolveQuestionResponse)
async def solve_question(req: SolveQuestionRequest, user: AuthUser | None = Depends(optional_auth_user)):
    result = solve_ad_hoc_question(
        question_text=req.question_text_solver,
        engine_case=req.suggested_engine_case,
        options=req.options,
        givens=req.givens,
        requested_quantity=req.requested_quantity,
        diagram=req.diagram,
        require_diagram_validation=req.diagram is not None,
    )
    response = SolveQuestionResponse(
        debug_report_id=req.debug_report_id,
        debug_report_path=report_path(req.debug_report_id),
        status=result.status,
        engine_case=result.engine_case,
        template_id=result.template_id,
        template_confidence=result.template_confidence,
        template_reason=result.template_reason,
        template_warnings=result.template_warnings,
        diagram_valid=result.diagram_valid,
        diagram_warnings=result.diagram_warnings,
        equation_plan=result.equation_plan or None,
        answer=result.computed_text,
        matched_option=result.predicted_option_letter,
        computed_value=result.computed_value,
        trace=result.trace,
        walkthrough=build_solution_walkthrough(result) if result.status == "passed" else None,
        animation_scene_spec=build_animation_scene_spec(
            result=result,
            question_text=req.question_text_solver,
            givens=req.givens,
        ) if result.status == "passed" else None,
        reason=result.reason,
    )
    if result.status != "passed" and user is not None:
        ticket = create_or_update_ticket(
            user=user,
            question_text=req.question_text_solver,
            request=req,
            response=response,
            debug_report_id=req.debug_report_id,
        )
        response.feedback_ticket_id = ticket["ticket_id"]
        response.feedback_status = ticket["status"]
    record_solve(report_id=req.debug_report_id, request=req, response=response)
    return response


@app.post("/audit/walkthrough-sync")
async def audit_walkthrough_sync_endpoint(req: SolveQuestionRequest):
    result = solve_ad_hoc_question(
        question_text=req.question_text_solver,
        engine_case=req.suggested_engine_case,
        options=req.options,
        givens=req.givens,
        requested_quantity=req.requested_quantity,
        diagram=req.diagram,
        require_diagram_validation=req.diagram is not None,
    )
    walkthrough = build_solution_walkthrough(result) if result.status == "passed" else None
    animation_scene_spec = build_animation_scene_spec(
        result=result,
        question_text=req.question_text_solver,
        givens=req.givens,
    ) if result.status == "passed" else None
    audit = audit_walkthrough_sync(walkthrough=walkthrough, animation_scene=animation_scene_spec)
    return {
        "request": {
            "question_text_solver": req.question_text_solver,
            "options": req.options,
            "givens": req.givens,
            "requested_quantity": req.requested_quantity,
            "suggested_engine_case": req.suggested_engine_case,
        },
        "solver": {
            "status": result.status,
            "reason": result.reason,
            "engine_case": result.engine_case,
            "answer": result.computed_text,
            "matched_option": result.predicted_option_letter,
        },
        "walkthrough": walkthrough,
        "animation_scene_spec": animation_scene_spec,
        "audit": audit,
    }


@app.post("/feedback/questions")
async def create_feedback_ticket(req: FeedbackTicketRequest, user: AuthUser = Depends(require_auth_user)):
    ticket = create_or_update_ticket(
        user=user,
        question_text=req.question_text_solver,
        request=req.solve_request,
        response=req.solve_response,
        debug_report_id=req.debug_report_id,
    )
    return {
        "ticket_id": ticket["ticket_id"],
        "status": ticket["status"],
        "created_at": ticket["created_at"],
        "updated_at": ticket["updated_at"],
    }


@app.get("/feedback/questions")
async def get_feedback_tickets(user: AuthUser = Depends(require_auth_user)):
    return {"tickets": list_tickets(user=user)}


@app.get("/feedback/notifications")
async def get_feedback_notifications(user: AuthUser = Depends(require_auth_user)):
    return {"notifications": list_notifications(user=user)}


@app.post("/feedback/notifications/read")
async def read_feedback_notifications(user: AuthUser = Depends(require_auth_user)):
    return {"read": mark_notifications_read(user=user)}


@app.post("/feedback/retry", response_model=FeedbackRetryResponse)
async def retry_feedback_questions(
    user: AuthUser | None = Depends(optional_auth_user),
    retry_token: str | None = Header(default=None, alias="X-Feedback-Retry-Token"),
):
    retry_secret = os.getenv("FEEDBACK_RETRY_TOKEN") or os.getenv("FEEDBACK_SECRET")
    can_retry_all = bool(retry_secret and retry_token and retry_token == retry_secret)
    if not can_retry_all and user is None:
        raise HTTPException(status_code=401, detail="Sign in or provide X-Feedback-Retry-Token")

    tickets = list_tickets(user=None if can_retry_all else user, include_resolved=False)
    resolved_ids: list[str] = []
    still_open = 0
    for ticket in tickets:
        request_payload = ticket.get("latest_request") or {}
        try:
            req = SolveQuestionRequest.model_validate(request_payload)
        except Exception:
            still_open += 1
            continue
        result = solve_ad_hoc_question(
            question_text=req.question_text_solver,
            engine_case=req.suggested_engine_case,
            options=req.options,
            givens=req.givens,
            requested_quantity=req.requested_quantity,
            diagram=req.diagram,
            require_diagram_validation=req.diagram is not None,
        )
        response = SolveQuestionResponse(
            debug_report_id=req.debug_report_id,
            debug_report_path=report_path(req.debug_report_id),
            status=result.status,
            engine_case=result.engine_case,
            template_id=result.template_id,
            template_confidence=result.template_confidence,
            template_reason=result.template_reason,
            template_warnings=result.template_warnings,
            diagram_valid=result.diagram_valid,
            diagram_warnings=result.diagram_warnings,
            equation_plan=result.equation_plan or None,
            answer=result.computed_text,
            matched_option=result.predicted_option_letter,
            computed_value=result.computed_value,
            trace=result.trace,
            walkthrough=build_solution_walkthrough(result) if result.status == "passed" else None,
            animation_scene_spec=build_animation_scene_spec(
                result=result,
                question_text=req.question_text_solver,
                givens=req.givens,
            ) if result.status == "passed" else None,
            reason=result.reason,
        )
        if result.status == "passed":
            resolved = resolve_ticket(ticket, response=response)
            resolved_ids.append(str(resolved["ticket_id"]))
        else:
            mark_retry_attempt(ticket, response=response)
            still_open += 1
    return FeedbackRetryResponse(
        checked=len(tickets),
        resolved=len(resolved_ids),
        still_open=still_open,
        resolved_ticket_ids=resolved_ids,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    prompt: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    rag_context = ""
    if retriever:
        try:
            rag_context = retriever.get_context(prompt)
        except Exception:
            pass

    image_bytes = None
    image_mime = "image/jpeg"
    if image and image.filename:
        image_bytes = await image.read()
        image_mime = image.content_type or "image/jpeg"

    try:
        prompt_engine = require_prompt_engine()
        scene = prompt_engine.generate_scene(
            prompt=prompt,
            rag_context=rag_context,
            image_bytes=image_bytes,
            image_mime_type=image_mime,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scene generation failed: {e}")

    session = Session(scene=scene)
    sessions[session.session_id] = session
    first_chapter = session.current_chapter()
    opening = "Your visual explanation is ready. Choose Tutor Explanation or Text Explanation to begin."

    return GenerateResponse(
        session_id=session.session_id,
        scene=scene,
        current_chapter=first_chapter,
        message=opening,
    )


@app.post("/teach", response_model=TeachResponse)
async def teach(req: TeachRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.completed:
        return TeachResponse(
            session_id=req.session_id,
            narration="Great work! You've completed the full problem. Want to try another?",
            advance_chapter=False,
            completed=True,
            step_number=session.current_chapter_index,
        )

    if req.current_chapter_index is not None:
        last_index = len(session.scene.chapters) - 1
        session.current_chapter_index = max(0, min(req.current_chapter_index, last_index))

    frame_bytes = None
    if req.frame_base64:
        try:
            frame_bytes = base64.b64decode(req.frame_base64)
        except Exception:
            pass

    session.history.append({"role": "user", "content": req.student_message})

    # Use interactive teaching if enabled
    if req.interactive_mode:
        try:
            prompt_engine = require_prompt_engine()
            narration, options, step_type, highlight_id, chapter_index = prompt_engine.generate_interactive_step(
                session=session,
                student_message=req.student_message,
                frame_bytes=frame_bytes,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Interactive teaching failed: {e}")

        session.history.append({"role": "assistant", "content": narration})

        # Sync chapter progression
        prev_index = session.current_chapter_index
        next_chapter = None
        should_advance = False

        # Clamp chapter_index to valid range
        last_index = len(session.scene.chapters) - 1
        chapter_index = max(0, min(chapter_index, last_index))

        if chapter_index != prev_index:
            session.current_chapter_index = chapter_index
            next_chapter = session.scene.chapters[chapter_index]
            should_advance = True

        return TeachResponse(
            session_id=req.session_id,
            narration=narration,
            advance_chapter=should_advance,
            next_chapter=next_chapter,
            interactive_options=options,
            step_type=step_type,
            highlight_id=highlight_id,
            completed=session.completed,
            step_number=session.current_chapter_index,
        )
    else:
        # Phase 2: unpack 3-tuple
        try:
            prompt_engine = require_prompt_engine()
            narration, should_advance, highlight_id = prompt_engine.generate_narration(
                session=session,
                student_message=req.student_message,
                frame_bytes=frame_bytes,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Teaching failed: {e}")

        session.history.append({"role": "assistant", "content": narration})

        # Step number = chapter index at time of this response (before any advance)
        step_number = session.current_chapter_index

        # Honour the advance signal — chapter progression IS controlled here
        next_chapter = None
        if should_advance:
            advanced = session.advance()
            if advanced:
                next_chapter = session.current_chapter()

        return TeachResponse(
            session_id=req.session_id,
            narration=narration,
            advance_chapter=should_advance,
            next_chapter=next_chapter,
            completed=session.completed,
            highlight_id=highlight_id,
            step_number=step_number,
        )


# ── Debug endpoints ───────────────────────────

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    return session.model_dump()


@app.get("/session/{session_id}/chapter/{index}")
async def get_chapter(session_id: str, index: int):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    chapters = session.scene.chapters
    if index >= len(chapters):
        raise HTTPException(status_code=404, detail=f"Chapter {index} not found")
    ch = chapters[index]
    return {
        "chapter_id": ch.id,
        "title": ch.title,
        "object_count": len(ch.objects),
        "objects": [
            {
                "id": o.id,
                "type": o.type,
                "position": o.position,
                "has_path": o.path is not None,
                "path_length": len(o.path) if o.path else 0,
                "path_start": o.path[0] if o.path else None,
                "path_end": o.path[-1] if o.path else None,
                "label": o.label,
            }
            for o in ch.objects
        ],
    }


@app.get("/health")
async def health():
    try:
        initialize_app_schema()
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
    provider = engine.provider if engine is not None else "missing"
    status = "ok" if db_status == "ok" and provider != "missing" else "degraded"
    return {
        "status": status,
        "provider": provider,
        "database": db_status,
        "projectile_classifier": projectile_classifier_mode(),
    }


@app.get("/templates/projectile")
async def projectile_templates():
    return {
        "count": len(PROJECTILE_TEMPLATES),
        "templates": [
            {
                "id": template.id,
                "title": template.title,
                "family": template.family,
                "engine_cases": sorted(template.engine_cases),
                "accepted_quantities": sorted(template.accepted_quantities),
                "diagram_kind": template.diagram_kind,
            }
            for template in PROJECTILE_TEMPLATES
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
