from prometeo.domain.knowledge.similarity import is_near_duplicate

PARAGRAPH = (
    "Microgravity studies of flames allow for a range of simplifications and provide various "
    "advantages over normal-gravity studies. For example, the natural flicker of flames, "
    "which is a buoyancy-driven instability, is eliminated yielding quasi-steady flames."
)


def test_identical_text_is_a_duplicate_whatever_the_case_or_spacing() -> None:
    assert is_near_duplicate(PARAGRAPH, PARAGRAPH.upper().replace(" ", "  "))


def test_same_paragraph_with_a_few_edited_words_is_a_duplicate() -> None:
    edited = PARAGRAPH.replace("a range of", "a wide range of") + " Length scales increase."
    assert is_near_duplicate(PARAGRAPH, edited)


def test_a_paragraph_contained_in_a_longer_chunk_is_a_duplicate() -> None:
    longer = "Section 2.1 Background. " + PARAGRAPH + " The burner ejects fuel into air."
    assert is_near_duplicate(PARAGRAPH, longer)
    assert is_near_duplicate(longer, PARAGRAPH)


def test_chunks_that_only_share_an_overlap_sentence_are_distinct() -> None:
    shared = "As the flow velocity is reduced, the sooting decreases and then disappears."
    first = (
        "The rods were ignited at the downstream end and the flame was allowed to spread "
        "across the rod for a period of time at each velocity. " + shared
    )
    second = shared + (
        " The flame tail opens up as it continues to spread along the rod, and the rod "
        "extends past the end of the flame as the spreading continues."
    )
    assert not is_near_duplicate(first, second)


def test_different_topics_are_distinct() -> None:
    other = "The quenching speeds were found to be between two bounds in concurrent spread."
    assert not is_near_duplicate(PARAGRAPH, other)


def test_very_short_and_empty_texts() -> None:
    assert is_near_duplicate("PMMA rod", "pmma  ROD")
    assert not is_near_duplicate("PMMA rod", "cotton sheet")
    assert is_near_duplicate("", "")
    assert not is_near_duplicate("", "PMMA rod")
