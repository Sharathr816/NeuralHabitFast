import re
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from typing import Optional

# import engine from db.py
import sys


# 1. Get the absolute path of the current file (config.py)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Go up 2 levels: src -> Coach -> backend (where db.py lives)
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

# 3. Add this path to sys.path so Python can "see" the files in backend/
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 4. Now you can import directly
try:
    from db import engine
    print("✅ Successfully imported engine from db.py")
except ImportError as e:
    print(f"❌ Error importing engine: {e}")

from .config import (
    GROQ_MODEL_NAME, EMBEDDING_MODEL, VECTOR_DB_DIR, 
    SQL_DB_PATH, SYSTEM_PROMPT
)

load_dotenv()
POSTGRES_DSN = os.getenv("DATABASE_URL")

class RAGChatbot:
    def __init__(self):
        # LLM
        self.llm = ChatGroq(
            model=GROQ_MODEL_NAME,
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )

        # Embedding + Chroma
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.vectorstore = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=self.embeddings
        )
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})

        # Prompts
        self.rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Rewrite the user's last message into a standalone question. "
             "Do NOT answer. Only rewrite."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}")
        ])

        self.qa_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("system", "CONTEXT:\n{context}"),
            ("human", "{input}")
        ])

        self.last_seen_analysis = {}
        self.parser = StrOutputParser()
        self.engine = engine

    # ---------------- HISTORY HANDLING -----------------
    def get_session_history(self, session_id):
        os.makedirs(os.path.dirname(SQL_DB_PATH), exist_ok=True)
        return SQLChatMessageHistory(
            session_id=session_id,
            connection="sqlite:///" + SQL_DB_PATH
        )

    def clear_session_history(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].messages.clear()

    def _get_latest_analysis_id(self, user_id: int):
        q = text("""
            SELECT analysis_id
            FROM habit_analysis
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(q, {"uid": user_id}).fetchone()
            return row[0] if row else None

    # helper to get habits for analysis
    def _get_habits_for_analysis(self, analysis_id: int, limit: int = 5):
        q = text("""
            SELECT hi.habit_id, hc.name, hc.description
            FROM habit_interaction hi
            LEFT JOIN habits_catalog hc ON hi.habit_id = hc.habit_id
            WHERE hi.analysis_id = :aid
            ORDER BY hi.interaction_id DESC
            LIMIT :lim
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(q, {"aid": analysis_id, "lim": limit}).fetchall()

        habits = []
        for r in rows:
            habit_id, name, desc = r
            habits.append({
                "habit_id": habit_id,
                "name": name,
                "description": (desc or "")[:200]
            })
        return habits



    # ---------------- User context retrieval ----------------
    def _get_recent_user_context(
        self,
        user_id: int = 1,
        max_journals: int = 3,
        max_analyses: int = 3,
        max_recs: int = 5,
    ) -> str:
            """Fetch recent journal, analysis and recommendation rows for user and format as text.
            Returns empty string if user_id is falsy.
            """
            if not user_id:
                return ""

            

            blocks = []

            with self.engine.connect() as conn:
            # 1) Recent Journals (table: journals)
                q_j = text("""
                    SELECT journal_id, created_at, text, screen_minutes, unlock_count,
                        sleep_hours, steps, dominant_emotion, dominant_emotion_score
                    FROM journals
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT :lim
                """)
                journals = conn.execute(q_j, {"uid": user_id, "lim": max_journals}).fetchall()

                if journals:
                    blocks.append("RECENT JOURNALS:")
                    for r in journals:
                        (jid, created_at, journal_txt, screen_mins, unlocks,
                        sleep_h, steps, dom_emo, emo_score) = r

                        txt = (journal_txt or "").replace("\n", " ").strip()
                        preview = txt[:300] + ("..." if len(txt) > 300 else "")
                        blocks.append(
                            f"- journal_id={jid} at {created_at}\n"
                            f"  screen={screen_mins} unlocks={unlocks} sleep={sleep_h} steps={steps}\n"
                            f"  emotion={dom_emo} score={emo_score}\n"
                            f"  {preview}"
                        )


                # 2) Recent Analysis (table: habit_analysis)
                q_a = text("""
                    SELECT analysis_id, created_at, risk_score, prediction_label, top_features
                    FROM habit_analysis
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT :lim
                """)
                analyses = conn.execute(q_a, {"uid": user_id, "lim": max_analyses}).fetchall()

                if analyses:
                    blocks.append("\nRECENT ANALYSIS:")
                    for r in analyses:
                        (aid, created_at, risk_score, pred_label, top_features) = r
                        blocks.append(
                            f"- analysis_id={aid} at {created_at}\n"
                            f"  risk_score={risk_score} prediction={pred_label}\n"
                            f"  top_features={top_features}"
                        )


                # 3) Fetch habits ONLY for the latest analysis_id
                latest_analysis_id = self._get_latest_analysis_id(user_id)

                if latest_analysis_id:
                    habits = self._get_habits_for_analysis(latest_analysis_id, limit=max_recs)

                    if habits:
                        blocks.append("\nRECENT RECOMMENDED HABITS:")
                        for h in habits:
                            blocks.append(
                                f"- habit_id={h['habit_id']} name={h['name']}\n"
                                f"  desc: {h['description']}"
                            )


            return "\n".join(blocks)


    # ----------------- UTILITIES ------------------------
    def _rewrite_query(self, history, user_input):
        """Uses the LLM to rewrite dependent questions into standalone queries."""
        if len(history.messages) == 0:
            return user_input  # no need to rewrite

        prompt = self.rewrite_prompt.format(
            chat_history=history.messages,
            input=user_input
        )

        rewritten = self.llm.invoke(prompt)
        return rewritten.content

    def _retrieve_context(self, standalone_query):
        # Direct Chroma search (bypassing LCEL’s VectorStoreRetriever)
        docs = self.vectorstore.similarity_search(
            standalone_query,
            k=3
        )
        return "\n\n".join(doc.page_content for doc in docs)
    
    def _serialize_message(self, m):
            # LangChain ChatMessageHistory uses types like "human", "ai"
            raw_role = getattr(m, "type", None) or getattr(m, "role", None) or ""
            raw_role = str(raw_role).lower()

            # Normalize to ONLY these two:
            #   - "user" for anything human
            #   - "assistant" for anything ai/bot
            if raw_role in ("human", "user", "client", "me"):
                role = "user"
            else:
                role = "assistant"   # ai, system, tool, assistant → all bot side

            text = getattr(m, "text", None) or getattr(m, "content", None) or ""
            ts = getattr(m, "ts", None)
            if hasattr(ts, "isoformat"):
                ts = ts.isoformat()

            return {"role": role, "text": text, "ts": ts}



    def _sanitize_md_to_text(self, text: str) -> str:
            """
            Clean markdown-ish text but keep readable line breaks and list structure.
            """
            if not text:
                return ""

            # remove fenced code blocks
            text = re.sub(r'```[\s\S]*?```', '', text)

            # remove inline backticks
            text = text.replace('`', '')

            # convert common markdown list items to explicit line items
            # e.g. "\n- item" or "\n* item" -> "\n- item"
            text = re.sub(r'\n\s*[-\*]\s+', '\n- ', text)

            # convert numbered lists "1. item" to "1. item" on their own lines
            text = re.sub(r'\n\s*\d+\.\s+', '\n', text)            # remove leading numeric bullets (we'll keep lines)
            # If you want to keep numbers, use:
            # text = re.sub(r'\n\s*(\d+)\.\s+', r'\n\1. ', text)

            # convert markdown links [text](url) -> text
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

            # remove bold/italic markers but keep the words
            text = re.sub(r'(\*\*|\*|__|~~)(.*?)\1', r'\2', text)

            # replace table pipes with ' | ' but preserve line breaks so columns stay visually separated
            # also remove leading/trailing pipes on each line
            lines = []
            for ln in text.splitlines():
                # strip surrounding pipes
                ln2 = ln.strip()
                if ln2.startswith('|'): ln2 = ln2[1:]
                if ln2.endswith('|'): ln2 = ln2[:-1]
                # replace leftover pipes with spaced pipe to keep column separation
                ln2 = re.sub(r'\s*\|\s*', ' | ', ln2)
                lines.append(ln2.strip())

            text = '\n'.join(lines)

            # collapse multiple blank lines to single blank line
            text = re.sub(r'\n{3,}', '\n\n', text)

            # collapse long runs of spaces down to single spaces, but don't remove newlines
            text = re.sub(r'[ \t]{2,}', ' ', text)

            # trim spaces on each line and remove trailing/leading whitespace overall
            text = '\n'.join([l.rstrip() for l in text.splitlines()]).strip()

            return text



        # ----------------- MAIN CHAT ------------------------
    def chat(self, session_id, user_input):
        print("\n📌 BOT CHAT CALLED WITH SESSION:", session_id)
        history = self.get_session_history(session_id)
        print("📚 Loaded messages in history:", len(history.messages))

            # 1. rewrite (if needed)
        standalone_query = self._rewrite_query(history, user_input)

            # 2. retrieve docs
        #kb_context = self._retrieve_context(standalone_query)

        # 3. fetch recent DB context for this user
        user_id = 1 # in real app, map session_id -> user_id
        latest_analysis_id = self._get_latest_analysis_id(user_id)

        db_context = ""

        # Only fetch context if new analysis arrived
        if latest_analysis_id and self.last_seen_analysis.get(user_id) != latest_analysis_id:
            db_context = self._get_recent_user_context(user_id)
            self.last_seen_analysis[user_id] = latest_analysis_id

         # 4. combine contexts (KB first, then user DB)
        combined_context = ""
        if db_context:
            combined_context = (combined_context + "\n\nUSER_RECENT_DATA:\n" + db_context) if combined_context else db_context

        # 5. Build QA prompt
        qa_prompt = self.qa_prompt.format(
                chat_history=history.messages,
                input=user_input,
                context=combined_context
            )

        # 6. LLM generates final answer
        response = self.llm.invoke(qa_prompt)
        answer = response.content

        clean_answer = self._sanitize_md_to_text(answer)

        # 7. Save user + assistant messages
        history.add_user_message(user_input)
        history.add_ai_message(clean_answer)
        serialized = [self._serialize_message(m) for m in history.messages]

        return {"answer": answer, "history": serialized}