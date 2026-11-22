
from pathlib import Path
import hashlib
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

HANDBOOK_PATH = (
    BASE_DIR / "data" / "ap_handbook" / "AP_Policy_Handbook.md"
)

CHROMA_PATH = BASE_DIR / "data" / "chroma_db"

COLLECTION_NAME = "ap_policy_handbook"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def split_text(text: str):
    """Split long text into overlapping chunks."""

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        if end < len(text):
            boundary = text.rfind(" ", start, end)

            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def extract_sections(markdown_text: str):
    """Separate the handbook using Markdown headings."""

    sections = []
    current_heading = "General Information"
    current_lines = []

    for line in markdown_text.splitlines():

        if line.startswith("#"):
            if current_lines:
                sections.append(
                    (current_heading, "\n".join(current_lines))
                )

            current_heading = line.lstrip("#").strip()
            current_lines = []

        else:
            current_lines.append(line)

    if current_lines:
        sections.append(
            (current_heading, "\n".join(current_lines))
        )

    return sections


def create_chunks():
    """Read handbook and create metadata-rich chunks."""

    if not HANDBOOK_PATH.exists():
        raise FileNotFoundError(
            f"AP Handbook not found: {HANDBOOK_PATH}"
        )

    markdown_text = HANDBOOK_PATH.read_text(
        encoding="utf-8"
    )

    sections = extract_sections(markdown_text)

    all_chunks = []

    for heading, section_text in sections:

        for chunk in split_text(section_text):

            all_chunks.append({
                "heading": heading,
                "content": chunk
            })

    if not all_chunks:
        raise ValueError("No policy content found in handbook.")

    return all_chunks


def get_collection():
    """Connect to the persistent ChromaDB collection."""

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    embedding_function = DefaultEmbeddingFunction()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )

    return collection


def index_handbook():
    """Index handbook chunks in ChromaDB."""

    chunks = create_chunks()
    collection = get_collection()

    ids = []
    documents = []
    metadatas = []

    for index, item in enumerate(chunks):

        content = item["content"]
        heading = item["heading"]

        chunk_id = hashlib.sha256(
            f"{heading}:{index}:{content}".encode("utf-8")
        ).hexdigest()

        ids.append(chunk_id)

        documents.append(
            f"Policy Section: {heading}\n\n{content}"
        )

        metadatas.append({
            "source": HANDBOOK_PATH.name,
            "section": heading,
            "chunk_index": index
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print("\nAP HANDBOOK INDEXING SUCCESSFUL")
    print("--------------------------------")
    print(f"Source: {HANDBOOK_PATH.name}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Stored records: {collection.count()}")
    print(f"ChromaDB location: {CHROMA_PATH}")


def retrieve_policy(query: str, top_k: int = 3):
    """Retrieve relevant policy sections using semantic search."""

    collection = get_collection()

    if collection.count() == 0:
        raise ValueError(
            "Policy knowledge base is empty. Index the handbook first."
        )

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count())
    )

    retrieved = []

    for index, document in enumerate(results["documents"][0]):

        retrieved.append({
            "content": document,
            "metadata": results["metadatas"][0][index],
            "distance": results["distances"][0][index]
        })

    return retrieved


if __name__ == "__main__":

    index_handbook()

    print("\nPOLICY RETRIEVAL TEST")
    print("--------------------------------")

    test_query = (
        "What approval is required for an invoice "
        "of 75000 rupees?"
    )

    results = retrieve_policy(test_query)

    for index, result in enumerate(results, start=1):

        print(f"\nResult {index}")
        print(f"Section: {result['metadata']['section']}")
        print(f"Distance: {result['distance']:.4f}")
        print(result["content"])
