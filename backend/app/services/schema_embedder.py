"""
Schema Embedding Service — embeds schema chunks into ChromaDB for retrieval.

Per PRD §4.3 step 3 and §5.4:
- Chunks per table: columns with types, sample values, FKs, comments
- Stored in a per-workspace ChromaDB collection
- Cosine similarity for retrieval (top-5, threshold 0.75)
"""
from app.core.chroma import get_or_create_collection, get_chroma_client
from app.models.schema import SchemaMap, TableInfo


def embed_schema(schema_map: SchemaMap) -> int:
    """
    Embed all tables from a SchemaMap into ChromaDB.
    Returns the number of chunks embedded.
    """
    collection = get_or_create_collection(schema_map.workspace_id)

    # Clear existing embeddings for this workspace (full re-embed)
    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    ids = []
    documents = []
    metadatas = []

    for table in schema_map.tables:
        doc, meta = _build_table_document(table)
        ids.append(f"{schema_map.workspace_id}_{table.name}")
        documents.append(doc)
        metadatas.append(meta)

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return len(ids)


def retrieve_relevant_tables(
    workspace_id: str, question: str, top_k: int = 8, threshold: float = 0.10
) -> list[dict]:
    """
    Retrieve the top-k most relevant schema chunks for a question.
    Returns list of {table_name, document, distance, similarity}.

    Threshold is intentionally low (0.10) because ChromaDB's cosine distance
    on schema text typically yields similarities in the 0.15–0.45 range.
    The LLM itself will determine if it can answer from the provided tables.
    """
    collection = get_or_create_collection(workspace_id)

    # Don't request more than what's in the index
    count = collection.count()
    n_results = min(top_k, count) if count > 0 else 1

    results = collection.query(
        query_texts=[question],
        n_results=n_results,
    )

    retrieved = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0
            # ChromaDB returns distance (lower = more similar for cosine)
            # Convert to similarity: similarity = 1 - distance
            similarity = 1 - distance
            if similarity >= threshold:
                retrieved.append({
                    "table_name": results["metadatas"][0][i].get("table_name", ""),
                    "document": results["documents"][0][i],
                    "similarity": similarity,
                    "metadata": results["metadatas"][0][i],
                })

    return retrieved


def delete_workspace_embeddings(workspace_id: str) -> None:
    """Delete all embeddings for a workspace (e.g. on connection removal)."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(f"schema_{workspace_id}")
        client.delete_collection(f"schema_{workspace_id}")
    except Exception:
        pass


def _build_table_document(table: TableInfo) -> tuple[str, dict]:
    """
    Build a text document and metadata dict for a single table.
    This is what gets embedded and retrieved via similarity search.
    """
    lines = [f"Table: {table.name}"]
    if table.row_count is not None:
        lines.append(f"Approximate rows: {table.row_count:,}")

    # Columns
    col_lines = []
    for col in table.columns:
        parts = [f"  {col.name} {col.data_type}"]
        if col.is_primary_key:
            parts.append("PRIMARY KEY")
        if not col.is_nullable:
            parts.append("NOT NULL")
        if col.is_foreign_key:
            parts.append(f"FK -> {col.references_table}.{col.references_column}")
        if col.column_comment:
            parts.append(f"-- {col.column_comment}")
        if col.sample_values:
            parts.append(f"values: {', '.join(col.sample_values)}")
        col_lines.append(" ".join(parts))

    lines.append("Columns:")
    lines.extend(col_lines)

    # Foreign keys summary
    if table.foreign_keys:
        fk_lines = [f"  {fk['column']} -> {fk['references_table']}.{fk['references_column']}"
                     for fk in table.foreign_keys]
        lines.append("Relationships:")
        lines.extend(fk_lines)

    document = "\n".join(lines)

    # Metadata for filtering
    metadata = {
        "table_name": table.name,
        "column_count": len(table.columns),
        "row_count": table.row_count or 0,
        "has_pk": any(c.is_primary_key for c in table.columns),
        "has_fk": any(c.is_foreign_key for c in table.columns),
    }

    return document, metadata
