from fastapi import APIRouter, BackgroundTasks, HTTPException
# from sqlalchemy.orm import Session

from database.schema import JournalResponse, JournalIn
from config_main import emotion_labels, entity_labels, emotion_model, entity_model, bert_tokenizer

from database.db import SessionLocal
from database.models import User, Journal

import torch
import datetime

from services.background_service import process_journal_pipeline


router = APIRouter(tags=["Journal"])


@router.post("/journal-analyse", response_model=JournalResponse)
def analyse_journal(payload: JournalIn, background_tasks: BackgroundTasks):
    text = payload.text
    # run you NLP prediction logic (your snippet)
    inputs = bert_tokenizer(text, return_tensors="pt") 
    with torch.no_grad():
        bert_outputs = emotion_model(**inputs)
        ner_outputs = entity_model.predict_entities(text, entity_labels)
        probs = torch.sigmoid(bert_outputs.logits).squeeze(0)

    top5_indices = torch.argsort(probs, descending=True)[:5]
    top5_labels = [emotion_labels[i] for i in top5_indices]
    top5_probs = [probs[i].item() for i in top5_indices]

    emotions = {label: prob for label, prob in zip(top5_labels, top5_probs)}

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        j = Journal(
            user_id=payload.user_id,
            text=payload.text,
            screen_minutes=payload.screen_minutes,
            unlock_count=payload.unlock_count,
            sleep_hours=payload.sleep_hours,
            steps=payload.steps,
            dominant_emotion=top5_labels[0] if top5_labels else None,
            dominant_emotion_score=top5_probs[0] if top5_probs else None,
        )
        db.add(j)
        db.commit()
        db.refresh(j)
        journal_id = j.journal_id
    finally:
        db.close()

    # schedule background processing without blocking
    background_tasks.add_task(
        process_journal_pipeline,
        payload.user_id,
        journal_id,
        payload,
        ner_outputs,
        top5_labels,
        top5_probs
    )

    return JournalResponse(message="Journal received and processing started, say hi to coach to see your recommended habits!", journal_id=journal_id)