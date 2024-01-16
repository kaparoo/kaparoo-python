import platform
from pathlib import Path

import pytest

from kaparoo.filesystem.utils import prepend_path, prepend_paths, stringify_path, stringify_paths


def _stringify(path: Path) -> str:
    path = str(path)
    if platform.system() == "Windows":
        path = path.replace("\\", "/")
    return path


@pytest.mark.order(1)
def test_stringify_path(
    cwd_path: Path, dummy_path: Path, tmp_paths: tuple[Path, Path, Path]
):
    assert stringify_path(cwd_path) == _stringify(cwd_path)
    assert stringify_path(dummy_path) == _stringify(dummy_path)

    for path in tmp_paths:
        assert stringify_path(path) == _stringify(path)

    # dummy_path: path/to/file
    assert stringify_path(dummy_path, after="path") == "to/file"
    assert stringify_path(dummy_path, after="path/to") == "file"

    # tmp_dir: tmp_path / dir
    # tmp_file: tmp_path / file.txt
    tmp_path, tmp_dir, tmp_file = tmp_paths
    assert stringify_path(tmp_dir, after=tmp_path) == "dir"
    assert stringify_path(tmp_file, after=tmp_path) == "file.txt"

    with pytest.raises(ValueError):
        stringify_path(tmp_dir, after=tmp_file)


@pytest.mark.order(2)
def test_stringify_paths(
    tmp_paths: tuple[Path, Path, Path],
    tmp_dirs: list[Path],
    tmp_files: list[Path],
):
    tmp_path, _, tmp_file = tmp_paths
    assert stringify_paths(tmp_paths) == [_stringify(p) for p in tmp_paths]
    assert stringify_paths(tmp_paths, after=tmp_path) == [".", "dir", "file.txt"]

    assert stringify_paths(tmp_files) == [_stringify(p) for p in tmp_files]
    assert stringify_paths(tmp_files, after=tmp_path) == [p.name for p in tmp_files]

    assert stringify_paths(tmp_dirs) == [_stringify(p) for p in tmp_dirs]
    assert stringify_paths(tmp_dirs, after=tmp_path) == [p.name for p in tmp_dirs]

    with pytest.raises(ValueError):
        stringify_paths(tmp_paths, after=tmp_file)
        

@pytest.mark.order(3)
def test_prepend_path(tmp_path: Path, cwd_path: Path):
    expected = tmp_path / "dir"
    expected_str = _stringify(expected)
    assert prepend_path("dir", base=tmp_path) == expected
    assert prepend_path("dir", base=tmp_path, stringify=True) == expected_str

    expected = tmp_path / "file.txt"
    expected_str = _stringify(expected)
    assert prepend_path("file.txt", base=tmp_path) == expected
    assert prepend_path("file.txt", base=tmp_path, stringify=True) == expected_str

    with pytest.raises(ValueError):
        prepend_path(cwd_path, tmp_path)


@pytest.mark.order(4)
def test_prepend_paths(
    cwd_path: Path,
    tmp_path: Path,
    tmp_dirs: list[Path],
    tmp_files: list[Path],
    tmp_dirnames: list[str],
    tmp_filenames: list[str],
):
    expected = tmp_dirs
    expected_str = [_stringify(dir) for dir in tmp_dirs]
    assert prepend_paths(tmp_dirnames, tmp_path) == expected
    assert prepend_paths(tmp_dirnames, tmp_path, stringify=True) == expected_str

    expected = tmp_files
    expected_str = [_stringify(path) for path in expected]
    assert prepend_paths(tmp_filenames, tmp_path) == expected
    assert prepend_paths(tmp_filenames, tmp_path, stringify=True) == expected_str

    with pytest.raises(ValueError):
        prepend_paths([cwd_path], tmp_path)