import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import List, Dict, Any
from collections import defaultdict
import chromadb
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.ingestion.cleaner import clean_html_document
from backend.ingestion.chunker import chunk_document

COLLECTION_NAME = "finsight_documents"

def run_ingestion(rebuild: bool = True) -> Dict[str, Any]:
    """
    Executes the ingestion pipeline:
    1. Scans data/documents for HTML SEC filings
    2. Cleans HTML, preserving Markdown tables & stripping XBRL/boilerplate
    3. Chunks section-aware based on 10-K, 10-Q, 8-K
    4. Computes SentenceTransformer embeddings
    5. Stores into persistent ChromaDB with structured metadata
    6. Logs audit summary
    """
    docs_dir = settings.DOCUMENTS_DIR
    if not docs_dir.exists():
        raise FileNotFoundError(f"Documents directory not found at {docs_dir}")

    html_files = sorted([f for f in docs_dir.iterdir() if f.is_file() and f.suffix.lower() == ".html"])
    if not html_files:
        raise ValueError(f"No HTML documents found in {docs_dir}")

    print(f"Found {len(html_files)} documents to ingest in {docs_dir}:")
    for f in html_files:
        print(f" - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    # 1. Clean and chunk documents
    all_chunks: List[Dict[str, Any]] = []
    audit_stats = defaultdict(lambda: defaultdict(int))

    for file_path in html_files:
        print(f"\nProcessing {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_html = f.read()
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            continue

        cleaned_text = clean_html_document(raw_html)
        chunks = chunk_document(cleaned_text, file_path.name)
        print(f"Generated {len(chunks)} chunks for {file_path.name}")

        for ch in chunks:
            all_chunks.append(ch)
            meta = ch["metadata"]
            audit_stats[meta["company"]][meta["doc_type"]] += 1

    print(f"\nTotal chunks prepared across all files: {len(all_chunks)}")

    # 2. Initialize ChromaDB client and collection
    persist_dir = str(Path(settings.CHROMA_PERSIST_DIR).resolve())
    client = chromadb.PersistentClient(path=persist_dir)

    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection '{COLLECTION_NAME}' for clean rebuild.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "FinSight financial SEC filings and earnings releases"}
    )

    # 3. Embed and store using Sentence Transformers
    print(f"\nLoading SentenceTransformer model: {settings.EMBEDDING_MODEL}...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    batch_size = 64
    total_chunks = len(all_chunks)
    print(f"Embedding and storing {total_chunks} chunks in batches of {batch_size}...")

    for i in range(0, total_chunks, batch_size):
        batch = all_chunks[i:i + batch_size]
        batch_texts = [b["text"] for b in batch]
        batch_ids = [b["chunk_id"] for b in batch]
        batch_metas = [b["metadata"] for b in batch]

        # Compute embeddings
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()

        # Insert into ChromaDB
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_texts,
            metadatas=batch_metas
        )
        print(f"Stored chunks {min(i + batch_size, total_chunks)}/{total_chunks}...")

    # 4. Audit summary
    print("\n" + "=" * 55)
    print("=== FIN SIGHT INGESTION AUDIT SUMMARY ===")
    print("=" * 55)
    summary_dict = {}
    for company, doc_types in audit_stats.items():
        summary_dict[company] = dict(doc_types)
        print(f"Company: {company}")
        for dt, count in doc_types.items():
            print(f"   {dt:<10}: {count} chunks")
        total_co = sum(doc_types.values())
        print(f"   Total     : {total_co} chunks")
        print("-" * 55)

    print(f"Persistent vectorstore location: {persist_dir}")
    print(f"Total documents indexed in ChromaDB: {collection.count()}")
    print("=" * 55)

    return {
        "status": "success",
        "total_chunks": collection.count(),
        "audit_summary": summary_dict
    }

if __name__ == "__main__":
    run_ingestion(rebuild=True)
