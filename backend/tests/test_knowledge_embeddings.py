from app.core.config import get_settings
from app.services import knowledge


class FakeEmbeddings:
    def embed_query(self, _text: str) -> list[float]:
        return [0.25] * get_settings().embedding_dimension


def test_embed_query_calls_provider_and_validates_dimension(monkeypatch):
    monkeypatch.setattr(knowledge, "_embeddings", lambda: FakeEmbeddings())
    vector = knowledge.embed_query("RAG 产品")
    assert vector is not None
    assert len(vector) == get_settings().embedding_dimension
