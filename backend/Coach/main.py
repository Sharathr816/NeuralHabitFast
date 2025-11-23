import gradio as gr
import uuid
from src.ingestion import ingest_documents
from src.bot import RAGChatbot

# 1. Initialize System
print("Initializing Chatbot System...")
# Uncomment the line below if you want to auto-ingest on every restart
# ingest_documents() 
bot = RAGChatbot()


# def respond(message, history, session_id_state):
#     if not session_id_state:
#         session_id_state = str(uuid.uuid4())
    
#     response = bot.chat(session_id=session_id_state, user_input=message)
#     return response

def respond(message, history, session_id_state):
    if not session_id_state:
        session_id_state = str(uuid.uuid4())

    # print("\n🔥 SESSION ID:", session_id_state)
    reply = bot.chat(session_id=session_id_state, user_input=message)

    return reply


def trigger_ingestion():
    try:
        ingest_documents()
        return "Ingestion Complete! Vector Database Updated."
    except Exception as e:
        return f"Error: {str(e)}"

# 2. Build Gradio UI
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 🤖 Plug & Play RAG Chatbot (Groq + Chroma + Memory)")
    
    # Session State
    #session_id = gr.State(value=lambda: str(uuid.uuid4()))
    session_id = gr.State(value=lambda: str(uuid.uuid4()))  
    
    with gr.Row():
        with gr.Column(scale=4):
            chatbot = gr.ChatInterface(
                fn=respond, 
                additional_inputs=[session_id],
                title="Chat Interface",
                description="Session is persistent via SQLite."
            )
        
        with gr.Column(scale=1):
            gr.Markdown("### Admin Controls")
            ingest_btn = gr.Button("🔄 Re-ingest Data Files", variant="primary")
            status_box = gr.Textbox(label="System Status", interactive=False)
            
            ingest_btn.click(trigger_ingestion, inputs=[], outputs=[status_box])
            
            gr.Markdown("""
            **How to use:**
            1. Put PDF/TXT in `data/`
            2. Click 'Re-ingest Data Files'
            3. Chat!
            """)

if __name__ == "__main__":
    demo.launch(share=False)