"""Output path guards for derive-bass2-flow — never touch curated evidence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from prometeo.bootstrap.safe_output import (
    UnsafeOutputPathError,
    atomic_write_text,
    processed_root,
    resolve_processed_json_output,
)


@pytest.fixture
def data_tree(tmp_path: Path) -> Path:
    """Isolated data/ layout: curated, sources, fixtures, processed, .env."""
    (tmp_path / "curated").mkdir()
    (tmp_path / "sources").mkdir()
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "processed").mkdir()
    (tmp_path / "curated" / "trials.json").write_text('{"protected": true}\n', encoding="utf-8")
    (tmp_path / "curated" / "document_chunks.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "sources" / "bass2-manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "fixtures" / "synthetic_trials.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=no\n", encoding="utf-8")
    return tmp_path


def test_default_path_is_under_processed(data_tree: Path) -> None:
    target = resolve_processed_json_output(None, data_dir=data_tree)
    assert target == processed_root(data_tree) / "bass2_flow_speeds.json"
    assert target.parent == processed_root(data_tree)


def test_alternate_name_inside_processed_is_allowed(data_tree: Path) -> None:
    requested = data_tree / "processed" / "review_sheet.json"
    target = resolve_processed_json_output(requested, data_dir=data_tree)
    assert target == requested.resolve()


def test_relative_path_inside_processed_is_allowed(
    data_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(data_tree)
    target = resolve_processed_json_output(Path("processed/alt.json"), data_dir=data_tree)
    assert target == (data_tree / "processed" / "alt.json").resolve()


@pytest.mark.parametrize(
    "relative",
    [
        "curated/trials.json",
        "curated/document_chunks.json",
        "sources/bass2-manifest.json",
        "fixtures/synthetic_trials.json",
        ".env",
        "processed/../curated/trials.json",
        "processed/../../.env",
    ],
)
def test_protected_and_traversal_paths_are_refused(
    data_tree: Path, relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(data_tree)
    before = (data_tree / "curated" / "trials.json").read_text(encoding="utf-8")
    with pytest.raises(UnsafeOutputPathError, match=r"must stay under|curated evidence"):
        resolve_processed_json_output(Path(relative), data_dir=data_tree)
    assert (data_tree / "curated" / "trials.json").read_text(encoding="utf-8") == before


def test_absolute_path_outside_processed_is_refused(data_tree: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "leak.json"
    outside.parent.mkdir()
    with pytest.raises(UnsafeOutputPathError, match="must stay under"):
        resolve_processed_json_output(outside, data_dir=data_tree)


def test_non_json_extension_is_refused(data_tree: Path) -> None:
    with pytest.raises(UnsafeOutputPathError, match=r"\.json"):
        resolve_processed_json_output(
            data_tree / "processed" / "sheet.csv",
            data_dir=data_tree,
        )


def test_existing_file_requires_overwrite(data_tree: Path) -> None:
    existing = data_tree / "processed" / "bass2_flow_speeds.json"
    existing.write_text("{}\n", encoding="utf-8")
    with pytest.raises(UnsafeOutputPathError, match="--overwrite"):
        resolve_processed_json_output(None, data_dir=data_tree)
    target = resolve_processed_json_output(None, data_dir=data_tree, overwrite=True)
    assert target == existing.resolve()


def test_symlink_to_curated_is_refused(data_tree: Path) -> None:
    link = data_tree / "processed" / "alias.json"
    target = data_tree / "curated" / "trials.json"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlink creation requires privileges on this Windows host")
    before = target.read_text(encoding="utf-8")
    with pytest.raises(UnsafeOutputPathError, match=r"must stay under|curated evidence"):
        resolve_processed_json_output(link, data_dir=data_tree, overwrite=True)
    assert target.read_text(encoding="utf-8") == before


def test_atomic_write_replaces_without_partial_file(data_tree: Path) -> None:
    path = data_tree / "processed" / "sheet.json"
    atomic_write_text(path, '{"ok": true}\n')
    assert path.read_text(encoding="utf-8") == '{"ok": true}\n'
    leftovers = list(path.parent.glob(".sheet.*.tmp"))
    assert leftovers == []


def test_protected_corpus_unchanged_after_refused_writes(data_tree: Path) -> None:
    """Hash-style integrity: refused destinations must not mutate curated files."""
    import hashlib

    protected = [
        data_tree / "curated" / "trials.json",
        data_tree / "curated" / "document_chunks.json",
        data_tree / "sources" / "bass2-manifest.json",
        data_tree / "fixtures" / "synthetic_trials.json",
        data_tree / ".env",
    ]
    digests = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    attacks = [
        data_tree / "curated" / "trials.json",
        data_tree / "processed" / ".." / "curated" / "document_chunks.json",
        data_tree / "fixtures" / "synthetic_trials.json",
    ]
    for attack in attacks:
        with pytest.raises(UnsafeOutputPathError):
            resolve_processed_json_output(attack, data_dir=data_tree, overwrite=True)
    for path, digest in digests.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
