from fastapi import APIRouter, HTTPException
from database.schema import ChatResponse, ChatRequest
from Coach.bot import RAGChatbot

router = APIRouter(prefix="/coach", tags=["Coach"])
chatbot = RAGChatbot()

@router.post("/chat", response_model=ChatResponse)
async def coach_chat(req: ChatRequest):
    try:
        result = chatbot.chat(req.session_id, req.message)  # result can be dict or ChatResponse
        # if chatbot.chat returns dict already, ensure keys are answer & history
        if isinstance(result, dict):
            # normalize keys if needed (support older return)
            answer = result.get("answer") or result.get("reply") or ""
            history = result.get("history", [])
            return ChatResponse(answer=answer, history=history)
        # If it's already a ChatResponse instance, just return it
        return result
    except Exception as e:
        #logger.exception("Error in /coach/chat")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def coach_history(session_id: str):
    try:
        history = chatbot.get_session_history(session_id)  # your existing method
        # convert to simple dicts
        serialized = []
        for m in history.messages:
            role = getattr(m, "role", getattr(m, "author", "assistant"))
            text = getattr(m, "text", getattr(m, "content", ""))
            ts = getattr(m, "ts", None)
            serialized.append({"role": role, "text": text, "ts": ts})
        return {"history": [ chatbot._serialize_message(m) for m in history.messages ]}

    except Exception as e:
        # logger.exception("Error in /coach/history")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear_history")
async def clear_history(payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    try:
        history = chatbot.get_session_history(session_id)
        chatbot.last_seen_analysis = {}  # reset any analysis cache
        # If the history object has a method to clear messages:
        if hasattr(history, 'clear') and callable(history.clear):
            history.clear()
        elif hasattr(history, 'delete_all') and callable(history.delete_all):
            history.delete_all()
        else:
            # fallback to explicit SQL deletion (see Option B)
            raise RuntimeError("No clear method on history object")

        return {"status": "cleared"}
    except Exception as e:
        print("Error clearing history")
        raise HTTPException(status_code=500, detail=str(e))