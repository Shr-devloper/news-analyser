from app.ai.embeddings import cosine_similarity, embed_text, embed_texts


def test_embed_dimension_stable():
    vecs = embed_texts(["hello world", "completely different text about finance"])
    assert len(vecs) == 2
    assert len(vecs[0]) == len(vecs[1])


def test_cosine_similarity_self_is_high():
    v = embed_text("artificial intelligence breakthrough in language models")
    assert cosine_similarity(v, v) > 0.99


def test_cosine_similarity_related_vs_unrelated():
    a = embed_text("stock market rallies as inflation cools")
    b = embed_text("equities surge after inflation data eases")
    c = embed_text("local football team wins championship match")
    assert cosine_similarity(a, b) >= cosine_similarity(a, c)
