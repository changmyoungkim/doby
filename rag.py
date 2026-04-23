#!/usr/bin/env python3
"""
stmemory RAG — Lightweight ChromaDB-based semantic search module.

Provides semantic search over project plans, code, and documentation
using persistent ChromaDB storage.
"""

import sys
import os
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("ERROR: chromadb not installed.")
    print("Install with: pip install chromadb")
    sys.exit(1)


class StmemoryRAG:
    """Semantic search over project plans and code using ChromaDB."""

    def __init__(self, project_root: str) -> None:
        """
        Initialize ChromaDB persistent client.

        Args:
            project_root: Project root directory path
        """
        self.project_root = Path(project_root)
        self.db_path = self.project_root / ".omc" / "state" / "stmemory-rag"
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with persistent storage
        settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(self.db_path),
            anonymized_telemetry=False,
        )
        self.client = chromadb.Client(settings)
        self.collection = self.client.get_or_create_collection(
            name="stmemory",
            metadata={"hnsw:space": "cosine"}
        )

    def index_plans(self, plans_dir: str) -> None:
        """
        Index all markdown files from plans directory.

        Reads .md files, splits into ~500 character chunks, and stores
        in ChromaDB with filename as metadata. Skips INDEX*.md files.

        Args:
            plans_dir: Path to plans directory
        """
        plans_path = Path(plans_dir)
        if not plans_path.exists():
            print(f"WARNING: Plans directory not found: {plans_dir}")
            return

        md_files = [f for f in plans_path.glob("*.md") if not f.name.startswith("INDEX")]

        if not md_files:
            print(f"No plan files found in {plans_dir}")
            return

        print(f"Indexing {len(md_files)} plan files...")

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                chunks = self._chunk_text(content, chunk_size=500)

                for i, chunk in enumerate(chunks):
                    doc_id = f"plan_{md_file.stem}_{i}"
                    self.collection.add(
                        ids=[doc_id],
                        documents=[chunk],
                        metadatas=[{
                            "source": "plan",
                            "filename": md_file.name,
                            "chunk": str(i),
                        }]
                    )

                print(f"  ✓ {md_file.name} ({len(chunks)} chunks)")
            except Exception as e:
                print(f"  ERROR: {md_file.name}: {e}")

    def index_code(self, codemap_path: str) -> None:
        """
        Index code files referenced in INDEX-codemap.md.

        Reads codemap file, extracts file paths, reads first 100 lines
        of each, and stores in ChromaDB.

        Args:
            codemap_path: Path to INDEX-codemap.md file
        """
        codemap_file = Path(codemap_path)
        if not codemap_file.exists():
            print(f"WARNING: Codemap file not found: {codemap_path}")
            return

        try:
            content = codemap_file.read_text(encoding="utf-8")
            # Simple extraction of file paths (lines that look like file paths)
            lines = content.split("\n")
            file_paths = []

            for line in lines:
                line = line.strip()
                # Look for lines that might be file paths
                if line.startswith("/") or line.startswith("./") or ".py" in line or ".ts" in line or ".tsx" in line:
                    # Extract potential file path
                    parts = line.split(maxsplit=1)
                    if parts:
                        potential_path = parts[0].strip("- []():`")
                        if Path(potential_path).suffix in [".py", ".ts", ".tsx", ".js", ".jsx"]:
                            file_paths.append(potential_path)

            if not file_paths:
                print(f"WARNING: No code file paths found in {codemap_path}")
                return

            print(f"Indexing {len(file_paths)} code files...")

            for file_path_str in file_paths:
                file_path = Path(file_path_str)
                if not file_path.is_absolute():
                    file_path = self.project_root / file_path

                if not file_path.exists():
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [f.readline() for _ in range(100)]
                        code_snippet = "".join(lines)

                    if code_snippet.strip():
                        doc_id = f"code_{file_path.name}"
                        self.collection.add(
                            ids=[doc_id],
                            documents=[code_snippet],
                            metadatas=[{
                                "source": "code",
                                "filepath": str(file_path),
                            }]
                        )
                        print(f"  ✓ {file_path.name}")
                except Exception as e:
                    print(f"  ERROR: {file_path}: {e}")

        except Exception as e:
            print(f"ERROR reading codemap: {e}")

    def query(self, question: str, n_results: int = 5) -> list[dict]:
        """
        Search ChromaDB for relevant documents.

        Args:
            question: Natural language query
            n_results: Number of results to return

        Returns:
            List of dicts with keys: doc_name, file_path, snippet, distance
        """
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

            output = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]

                    result_dict = {
                        "doc_name": metadata.get("filename", metadata.get("filepath", "unknown")),
                        "file_path": metadata.get("filepath", ""),
                        "snippet": doc[:200] + "..." if len(doc) > 200 else doc,
                        "distance": round(distance, 4),
                    }
                    output.append(result_dict)

            return output

        except Exception as e:
            print(f"ERROR querying: {e}")
            return []

    def rebuild(self) -> None:
        """Clear collection and re-index everything."""
        try:
            self.client.delete_collection(name="stmemory")
            self.collection = self.client.get_or_create_collection(
                name="stmemory",
                metadata={"hnsw:space": "cosine"}
            )
            print("Collection cleared. Ready to re-index.")
        except Exception as e:
            print(f"ERROR rebuilding collection: {e}")

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
        """
        Split text into chunks of approximately chunk_size characters.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters

        Returns:
            List of text chunks
        """
        chunks = []
        current_chunk = ""

        for paragraph in text.split("\n\n"):
            if len(current_chunk) + len(paragraph) < chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


def main() -> None:
    """CLI interface for stmemory RAG."""
    if len(sys.argv) < 2:
        print("Usage: python rag.py <command> [args]")
        print("")
        print("Commands:")
        print("  index              Index all plans and code files")
        print("  query <question>   Search for relevant documents")
        print("  rebuild            Clear and re-index everything")
        sys.exit(1)

    command = sys.argv[1]
    project_root = os.getcwd()

    rag = StmemoryRAG(project_root)

    if command == "index":
        plans_dir = Path(project_root) / ".omc" / "plans"
        codemap_path = plans_dir / "INDEX-codemap.md"

        rag.index_plans(str(plans_dir))
        rag.index_code(str(codemap_path))
        print("\nIndexing complete!")

    elif command == "query":
        if len(sys.argv) < 3:
            print("ERROR: query requires a question")
            print("Usage: python rag.py query \"your question\"")
            sys.exit(1)

        question = " ".join(sys.argv[2:])
        results = rag.query(question, n_results=5)

        if not results:
            print("No results found.")
            sys.exit(0)

        print(f"\nSearch results for: {question}\n")
        print("=" * 70)

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['doc_name']}")
            if result["file_path"]:
                print(f"   Path: {result['file_path']}")
            print(f"   Distance: {result['distance']}")
            print(f"   Snippet: {result['snippet']}")

        print("\n" + "=" * 70)

    elif command == "rebuild":
        rag.rebuild()
        print("Rebuild complete. Run 'index' to re-populate.")

    else:
        print(f"ERROR: unknown command '{command}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
