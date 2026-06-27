from pydantic import BaseModel

from lex.core import document as document_module
from lex.core.document import upload_documents


class UploadDocument(BaseModel):
    id: str
    text: str


class FakeQdrantClient:
    def __init__(self) -> None:
        self.upsert_calls = []

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)


class FakePointStruct:
    def __init__(self, id, vector, payload):
        self.id = id
        self.vector = vector
        self.payload = payload


def test_upload_documents_skips_empty_batch_without_embedding(monkeypatch):
    embedding_calls = []
    qdrant_client = FakeQdrantClient()

    monkeypatch.setattr(
        "lex.core.embeddings.generate_dense_embeddings_batch",
        lambda texts, max_workers=25: embedding_calls.append(texts) or [[0.1] for _ in texts],
    )
    monkeypatch.setattr("lex.core.embeddings.bm25_document", lambda text: text)
    monkeypatch.setattr(document_module, "qdrant_client", qdrant_client)
    monkeypatch.setattr(document_module, "PointStruct", FakePointStruct)

    upload_documents(
        collection_name="test",
        documents=[UploadDocument(id="empty", text="")],
        batch_size=1,
    )

    assert embedding_calls == []
    assert qdrant_client.upsert_calls == []


def test_upload_documents_skips_empty_documents_and_uploads_valid_ones(monkeypatch):
    embedding_calls = []
    qdrant_client = FakeQdrantClient()

    monkeypatch.setattr(
        "lex.core.embeddings.generate_dense_embeddings_batch",
        lambda texts, max_workers=25: embedding_calls.append(texts) or [[0.1] for _ in texts],
    )
    monkeypatch.setattr("lex.core.embeddings.bm25_document", lambda text: text)
    monkeypatch.setattr(document_module, "qdrant_client", qdrant_client)
    monkeypatch.setattr(document_module, "PointStruct", FakePointStruct)

    upload_documents(
        collection_name="test",
        documents=[
            UploadDocument(id="empty", text=""),
            UploadDocument(id="whitespace", text="   "),
            UploadDocument(id="valid", text=" useful content "),
        ],
        batch_size=3,
    )

    assert embedding_calls == [["useful content"]]
    assert len(qdrant_client.upsert_calls) == 1
    assert len(qdrant_client.upsert_calls[0]["points"]) == 1
    assert qdrant_client.upsert_calls[0]["points"][0].payload["id"] == "valid"
