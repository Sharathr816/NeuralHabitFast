import os
import shutil
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.config import DATA_DIR, VECTOR_DB_DIR, EMBEDDING_MODEL

def ingest_documents():
    """Reads files from /data, splits them, and updates the Vector DB."""
    
    # 1. Load Documents
    print(f"Loading documents from {DATA_DIR}...")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # Loaders for txt and pdf
    pdf_loader = DirectoryLoader(DATA_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader)
    #txt_loader = DirectoryLoader(DATA_DIR, glob="**/*.txt", loader_cls=TextLoader)
    
    docs = []
    docs.extend(pdf_loader.load())
    #docs.extend(txt_loader.load())

    if not docs:
        print("No documents found in /data folder.")
        return

    # 2. Split Text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    # 3. Initialize Embeddings
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # 4. Store in Chroma (Persistent)
    # Note: This creates a new DB or appends. To reset, delete the vector_store folder manually.
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=VECTOR_DB_DIR
    )
    print(f"Successfully ingested {len(splits)} chunks into ChromaDB.")

if __name__ == "__main__":
    ingest_documents()