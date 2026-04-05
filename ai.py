from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse
from app.services.ai_service import detect_quick_action, get_ai_response

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    history = [item.model_dump() for item in payload.history]
    quick_action = detect_quick_action(payload.message)
    if quick_action:
        return ChatResponse(**quick_action)
    reply = get_ai_response(payload.message, chat_history=history, images=payload.images)
    return ChatResponse(reply=reply)
