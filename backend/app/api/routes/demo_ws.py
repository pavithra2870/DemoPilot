"""WebSocket transport for the demo conversation.

The AI's reply is a validated JSON object, so it cannot be streamed token by
token without breaking the structured contract. What the socket gives us instead
is a live *status* channel — "thinking", "searching the knowledge base",
"preparing the demo" — which is what actually makes a 3-second turn feel
responsive. The final payload is identical to the REST route's.

Protocol
  client → {"type": "message", "message": "...", "active_section": "analytics"}
         → {"type": "end"}
         → {"type": "ping"}
  server → {"type": "status",  "stage": "retrieving", "detail": "..."}
         → {"type": "turn",    "data": AgentTurnOut}
         → {"type": "ended",   "data": {...}}
         → {"type": "error",   "message": "...", "code": "..."}
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.errors import AppError
from app.core.logging_config import get_logger
from app.core.rate_limit import TokenBucket
from app.core.security import sanitize_text
from app.services import demo_service

log = get_logger("api.ws")
router = APIRouter()

# Per-socket budget: generous enough for a real conversation, tight enough that a
# single connection cannot be used to drain the Groq quota.
_socket_bucket = TokenBucket(rate_per_minute=20, burst=8)

MAX_MESSAGE_CHARS = 4000


async def _send(socket: WebSocket, payload: dict) -> None:
    try:
        await socket.send_json(payload)
    except (RuntimeError, WebSocketDisconnect):
        pass


@router.websocket("/ws/demo/{session_id}")
async def demo_socket(socket: WebSocket, session_id: str) -> None:
    await socket.accept()

    try:
        demo_service.get_session(session_id)
    except AppError as exc:
        await _send(socket, {"type": "error", "code": exc.code, "message": exc.message})
        await socket.close(code=4404)
        return

    log.info("Demo socket opened for session %s", session_id)

    try:
        while True:
            payload = await socket.receive_json()
            kind = payload.get("type")

            if kind == "ping":
                await _send(socket, {"type": "pong"})
                continue

            if kind == "end":
                result = await demo_service.end_session(session_id)
                await _send(socket, {"type": "ended", "data": result})
                break

            if kind != "message":
                await _send(
                    socket,
                    {"type": "error", "code": "bad_request",
                     "message": f"Unsupported message type '{kind}'."},
                )
                continue

            message = sanitize_text(payload.get("message"), max_length=MAX_MESSAGE_CHARS)
            if not message:
                await _send(
                    socket,
                    {"type": "error", "code": "empty_message",
                     "message": "Message cannot be empty."},
                )
                continue

            if not _socket_bucket.consume(session_id):
                await _send(
                    socket,
                    {"type": "error", "code": "rate_limited",
                     "message": "You're sending messages very quickly — give it a second."},
                )
                continue

            active_section = sanitize_text(payload.get("active_section"), max_length=64) or None
            await _run_turn(socket, session_id, message, active_section)

    except WebSocketDisconnect:
        log.info("Demo socket closed for session %s", session_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Demo socket error for session %s", session_id)
        await _send(
            socket,
            {"type": "error", "code": "internal_error", "message": "Something went wrong."},
        )
    finally:
        try:
            await socket.close()
        except RuntimeError:
            pass


async def _run_turn(
    socket: WebSocket, session_id: str, message: str, active_section: str | None
) -> None:
    """Emit progress while the turn is generated, then the validated result."""
    await _send(socket, {"type": "status", "stage": "thinking", "detail": "Reading your message"})

    task = asyncio.create_task(
        demo_service.handle_message(session_id, message, active_section)
    )

    # Progress narration is time-based rather than instrumented: the phases are
    # genuinely sequential inside handle_message, and this keeps the service free
    # of transport concerns.
    progress = [
        (0.5, "retrieving", "Searching the knowledge base"),
        (1.6, "generating", "Preparing your walkthrough"),
    ]
    for delay, stage, detail in progress:
        done, _ = await asyncio.wait({task}, timeout=delay)
        if done:
            break
        await _send(socket, {"type": "status", "stage": stage, "detail": detail})

    try:
        turn = await task
    except AppError as exc:
        await _send(socket, {"type": "error", "code": exc.code, "message": exc.message})
        return
    except Exception:  # noqa: BLE001
        log.exception("Turn generation failed for session %s", session_id)
        await _send(
            socket,
            {"type": "error", "code": "internal_error",
             "message": "I couldn't generate a reply. Please try again."},
        )
        return

    await _send(socket, {"type": "turn", "data": turn.model_dump(mode="json")})
