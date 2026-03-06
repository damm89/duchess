import subprocess
from pathlib import Path
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'nnue')))

from rl_loop import detect_resume_iter, run_step


def _make_iter(nnue_dir: Path, n: int, *, bin: bool = True, pt: bool = True):
    if bin:
        (nnue_dir / f"duchess_iter_{n}.bin").touch()
    if pt:
        (nnue_dir / f"duchess_iter_{n}.pt").touch()


def test_fresh_start_returns_iter_1(tmp_path):
    start, nnue = detect_resume_iter(tmp_path)
    assert start == 1
    assert nnue is None


def test_single_complete_iter(tmp_path):
    _make_iter(tmp_path, 3)
    start, nnue = detect_resume_iter(tmp_path)
    assert start == 4
    assert nnue == str(tmp_path / "duchess_iter_3.bin")


def test_picks_highest_complete_iter(tmp_path):
    _make_iter(tmp_path, 1)
    _make_iter(tmp_path, 2)
    _make_iter(tmp_path, 5)
    start, nnue = detect_resume_iter(tmp_path)
    assert start == 6
    assert "duchess_iter_5.bin" in nnue


def test_incomplete_iter_ignored(tmp_path):
    """An iteration with only .bin and no .pt should not count."""
    _make_iter(tmp_path, 4, pt=False)
    _make_iter(tmp_path, 3)
    start, nnue = detect_resume_iter(tmp_path)
    assert start == 4


def test_only_pt_no_bin_ignored(tmp_path):
    _make_iter(tmp_path, 7, bin=False)
    start, nnue = detect_resume_iter(tmp_path)
    assert start == 1
    assert nnue is None


def test_max_check_respected(tmp_path):
    """Iterations beyond max_check are not found."""
    _make_iter(tmp_path, 50)
    start, nnue = detect_resume_iter(tmp_path, max_check=30)
    assert start == 1
    assert nnue is None


# --- run_step ---

def test_run_step_success():
    with patch("rl_loop.subprocess.run"):
        assert run_step("Test", ["echo", "hi"]) is True


def test_run_step_failure():
    with patch("rl_loop.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        assert run_step("Test", ["false"]) is False


def test_run_step_keyboard_interrupt():
    with patch("rl_loop.subprocess.run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt
        assert run_step("Test", ["sleep", "10"]) is False
