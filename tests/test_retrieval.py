from app.retrieval import Chunk, HybridIndex
from app.text import chunk_document, content_terms


def make_index() -> HybridIndex:
    idx = HybridIndex()
    idx.add(Chunk("a-0", "a", "vllm.md", "Continuous batching",
                  "Continuous batching lets new requests join the running batch "
                  "at every decoding step, raising GPU utilisation."))
    idx.add(Chunk("b-0", "b", "postgresql.md", "VACUUM",
                  "VACUUM reclaims space from dead tuples left behind by "
                  "updates and deletes under MVCC."))
    return idx


def test_chunking_splits_on_headings():
    text = "# One\nAlpha body text here.\n\n## Two\nBeta body text here."
    chunks = chunk_document(text)
    headings = [c["heading"] for c in chunks]
    assert headings == ["One", "Two"]


def test_chunking_windows_long_sections():
    text = "# Big\n" + " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_document(text, chunk_tokens=512, overlap=64)
    assert len(chunks) >= 3


def test_search_ranks_relevant_chunk_first():
    idx = make_index()
    results = idx.search("how does continuous batching use the GPU?")
    assert results and results[0]["source"] == "vllm.md"


def test_confidence_high_for_in_corpus_low_for_gibberish():
    idx = make_index()
    good = idx.search("what does vacuum do with dead tuples?")
    assert idx.confidence(good) >= 0.7
    bad = idx.search("what is the best pizza topping in naples?")
    assert idx.confidence(bad) < 0.7


def test_content_terms_drop_stopwords():
    assert "the" not in content_terms("what is the batching?")
    # light stemming: 'batching' -> 'batch'
    assert "batch" in content_terms("what is the batching?")
