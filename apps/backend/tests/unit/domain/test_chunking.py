import itertools

import pytest

from prometeo.domain.knowledge.chunking import chunk_text


def test_short_text_is_one_chunk_with_whitespace_collapsed() -> None:
    assert chunk_text("Flames  in\nmicrogravity   are weak.") == [
        "Flames in microgravity are weak."
    ]


def test_empty_text_gives_no_chunks() -> None:
    assert chunk_text("  \n\n  ") == []


def test_chunks_respect_the_limit_and_keep_whole_sentences() -> None:
    sentences = [f"Sentence number {i} is about flame spread." for i in range(40)]
    chunks = chunk_text(" ".join(sentences), max_chars=200, overlap_chars=0)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert all(c.endswith(".") for c in chunks)
    # No overlap requested: every sentence appears exactly once, in order.
    assert " ".join(chunks) == " ".join(sentences)


def test_consecutive_chunks_overlap_by_trailing_sentences() -> None:
    sentences = [f"Fact {i} holds." for i in range(30)]
    chunks = chunk_text(" ".join(sentences), max_chars=120, overlap_chars=40)
    assert all(len(c) <= 120 for c in chunks)
    for previous, current in itertools.pairwise(chunks):
        first_sentence = current.split(". ")[0] + "."
        assert first_sentence in previous


def test_every_word_survives_chunking() -> None:
    text = "PMMA rods burn. " * 50 + "\n\n" + "Oxygen was 21 %. " * 50
    chunks = chunk_text(text, max_chars=300, overlap_chars=60)
    joined = " ".join(chunks)
    assert "PMMA rods burn." in joined
    assert "Oxygen was 21 %." in joined
    assert all(len(c) <= 300 for c in chunks)


def test_a_sentence_longer_than_the_limit_is_split_on_spaces() -> None:
    chunks = chunk_text("word " * 100, max_chars=50, overlap_chars=0)
    assert all(len(c) <= 50 for c in chunks)
    assert sum(c.count("word") for c in chunks) == 100


@pytest.mark.parametrize(("max_chars", "overlap"), [(0, 0), (100, 100), (100, -1)])
def test_invalid_sizes_are_rejected(max_chars: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_text("text", max_chars=max_chars, overlap_chars=overlap)
