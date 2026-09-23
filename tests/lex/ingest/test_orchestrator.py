from pydantic import BaseModel

from lex.ingest import orchestrator


class IngestDocument(BaseModel):
    id: str
    text: str

    def get_embedding_text(self) -> str:
        return self.text


class FakePointStruct:
    def __init__(self, id, vector, payload):
        self.id = id
        self.vector = vector
        self.payload = payload


def test_create_points_batch_skips_empty_embedding_text(monkeypatch, caplog):
    embedding_calls = []

    monkeypatch.setattr(
        orchestrator,
        "generate_dense_embeddings_batch",
        lambda texts: embedding_calls.append(texts) or [[0.1] for _ in texts],
    )
    monkeypatch.setattr(orchestrator, "bm25_document", lambda text: text)
    monkeypatch.setattr(orchestrator, "PointStruct", FakePointStruct)

    points = orchestrator._create_points_batch(
        [
            IngestDocument(id="empty", text=""),
            IngestDocument(id="whitespace", text="   "),
            IngestDocument(id="valid", text=" useful content "),
        ]
    )

    assert embedding_calls == [["useful content"]]
    assert len(points) == 1
    assert points[0].payload["id"] == "valid"
    assert points[0].vector == {"dense": [0.1], "sparse": "useful content"}
    assert "Skipping document empty" in caplog.text
    assert "Skipping document whitespace" in caplog.text


def test_create_points_batch_avoids_embedding_empty_batch(monkeypatch):
    embedding_calls = []

    monkeypatch.setattr(
        orchestrator,
        "generate_dense_embeddings_batch",
        lambda texts: embedding_calls.append(texts) or [],
    )

    points = orchestrator._create_points_batch(
        [
            IngestDocument(id="empty", text=""),
            IngestDocument(id="whitespace", text="   "),
        ]
    )

    assert points == []
    assert embedding_calls == []
