import os
import io
import contextlib
import datetime
from pathlib import Path
import frontmatter
from dotenv import load_dotenv
from google import genai
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

load_dotenv()

# Detect Hugging Face persistent storage at /data or custom VECTOR_DB_DIR
data_mount = Path("/data/vector_db") if (Path("/data").exists() and os.access(Path("/data"), os.W_OK)) else Path("./vector_db")
CHROMA_DIR = Path(os.environ.get("VECTOR_DB_DIR", str(data_mount)))
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Generates ultra-fast text embeddings via Gemini Text-Embedding API without downloading heavy local weights."""
    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    res = client.models.embed_content(
                        model="gemini-embedding-001",
                        contents=text
                    )
                embeddings.append(res.embedding.values)
            except Exception as e:
                # Fallback zero vector if network hiccup
                embeddings.append([0.0] * 768)
        return embeddings

gemini_ef = GeminiEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = chroma_client.get_or_create_collection(
    name="academic_lectures",
    embedding_function=gemini_ef,
    metadata={"description": "Semester-wide graduate STEM lecture and theorem embeddings"}
)

def chunk_lecture_note(file_path: Path) -> list[dict]:
    """Splits a structured lecture note into semantic chunks with metadata."""
    if file_path.name.endswith("_MOC.md"):
        return []

    try:
        post = frontmatter.load(file_path)
        course = str(post.get("course", "General")).replace("[[", "").replace("]]", "").strip()
        topic = str(post.get("topic", file_path.stem)).replace("[[", "").replace("]]", "").strip()
        date_str = str(post.get("date", ""))
        
        sections = post.content.split("\n## ")
        chunks = []

        for i, sec in enumerate(sections):
            if not sec.strip():
                continue
            header = sec.split("\n")[0].strip("# ").strip()
            chunk_text = f"Course: {course}\nTopic: {topic}\nDate: {date_str}\nSection: {header}\n\n" + sec
            
            chunk_id = f"{file_path.stem}_sec_{i}"
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    "course": course,
                    "topic": topic,
                    "date": date_str,
                    "section": header,
                    "file_name": file_path.name
                }
            })
        return chunks
    except Exception as e:
        print(f"[!] Error chunking {file_path.name}: {e}")
        return []

def index_file_in_vector_db(file_path: Path):
    """Indexes or updates a lecture note in the persistent ChromaDB collection."""
    chunks = chunk_lecture_note(file_path)
    if not chunks:
        return

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    print(f"[+] Vector DB: Indexed {len(chunks)} chunks for {file_path.name}")

def index_all_lectures_vector_db(lectures_dir: Path, max_workers: int = 4):
    """Multi-threaded concurrent vector indexing for fast vault hydration on boot."""
    from concurrent.futures import ThreadPoolExecutor
    markdown_files = [f for f in lectures_dir.glob("*.md") if not f.name.endswith("_MOC.md")]
    if not markdown_files:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(index_file_in_vector_db, markdown_files))

def semantic_search_notes(query_text: str, n_results: int = 4, course_filter: str = None) -> list[dict]:
    """Performs semantic similarity vector search across all indexed semester lectures."""
    where_filter = None
    if course_filter:
        clean_c = course_filter.replace("[[", "").replace("]]", "").strip()
        where_filter = {"course": clean_c}

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_filter
    )

    formatted_results = []
    if results and "documents" in results and results["documents"]:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
        
        for doc, meta in zip(docs, metas):
            formatted_results.append({
                "content": doc,
                "course": meta.get("course", "Unknown"),
                "topic": meta.get("topic", "Unknown"),
                "date": meta.get("date", "Unknown"),
                "section": meta.get("section", ""),
                "file_name": meta.get("file_name", "")
            })
            
    return formatted_results

if __name__ == "__main__":
    index_all_lectures_vector_db(Path("./lectures"))
    res = semantic_search_notes("Explain Karush Kuhn Tucker conditions and Slater condition", n_results=2)
    print(f"[+] Vector Search Test Results: {len(res)} matches found.")
    for r in res:
        print(f" • Match from: {r['course']} - {r['topic']} ({r['date']})")
