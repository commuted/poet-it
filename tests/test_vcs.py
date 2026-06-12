"""Tests for the dulwich-based VCS layer.

The app writes history with dulwich (pure Python — no git binary needed at
runtime). These tests verify that behaviour, using the real git CLI as an
independent reader: every assertion made through `git log` / `git show` also
proves the dulwich-written repository is plain git underneath. The git CLI
is a test-only dependency; the module is skipped where it is unavailable.
"""
import shutil
import subprocess
import tkinter as tk

import pytest

from poetit.app import (
    Editor,
    _DEMO_POEM,
    _DEMO_POEM_NAME,
    _seed_demo_poem,
)
from poetit.linguistics import Linguistics

dulwich = pytest.importorskip("dulwich")
from dulwich.repo import Repo  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git CLI needed to independently verify dulwich-written history",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _git(*args, cwd=None):
    """Test-only helper: run git, return (returncode, decoded stdout)."""
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", errors="replace")


def _init_repo(path):
    """Initialise a repo at path with dulwich (as the app does) and return it."""
    Repo.init(str(path)).close()
    return path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


@pytest.fixture(scope="module")
def nlp():
    return Linguistics()


@pytest.fixture(scope="module")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture(scope="module")
def ed(root, nlp):
    return Editor(root, nlp)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _commit_file(repo_path, filename, content):
    """Write a file, stage it, commit, and return the HEAD sha."""
    path = repo_path / filename
    path.write_text(content, encoding='utf-8')
    _git('-C', str(repo_path), 'add', '--', filename)
    _git('-C', str(repo_path),
         '-c', 'user.name=Test', '-c', 'user.email=test@test',
         'commit', '-m', f'add {filename}')
    _, sha = _git('-C', str(repo_path), 'rev-parse', 'HEAD')
    return sha.strip()


def _set_editor_line(ed, row, text):
    te = ed.lines[row][0]
    te.delete(0, tk.END)
    te.insert(0, text)


# ---------------------------------------------------------------------------
# dulwich ↔ git interoperability
# ---------------------------------------------------------------------------

class TestGitInterop:
    def test_dulwich_init_recognised_by_git(self, repo):
        rc, _ = _git('-C', str(repo), 'rev-parse', '--git-dir')
        assert rc == 0

    def test_git_init_recognised_by_dulwich(self, tmp_path):
        subprocess.run(['git', 'init', str(tmp_path)],
                       capture_output=True, check=True)
        Repo(str(tmp_path)).close()  # raises NotGitRepository on failure

    def test_plain_directory_is_not_a_repo(self, tmp_path):
        from dulwich.errors import NotGitRepository
        with pytest.raises(NotGitRepository):
            Repo(str(tmp_path))


# ---------------------------------------------------------------------------
# _seed_demo_poem()
# ---------------------------------------------------------------------------

class TestSeedDemoPoem:
    def test_browning_txt_is_created(self, repo):
        _seed_demo_poem(str(repo))
        assert (repo / _DEMO_POEM_NAME).exists()

    def test_file_content_matches_demo_poem_constant(self, repo):
        _seed_demo_poem(str(repo))
        assert (repo / _DEMO_POEM_NAME).read_text(encoding='utf-8') == _DEMO_POEM

    def test_exactly_one_commit_created(self, repo):
        _seed_demo_poem(str(repo))
        _, out = _git('-C', str(repo), 'log', '--oneline')
        assert len(out.strip().splitlines()) == 1

    def test_commit_message_references_browning(self, repo):
        _seed_demo_poem(str(repo))
        _, out = _git('-C', str(repo), 'log', '--format=%s')
        assert 'Browning' in out

    def test_file_tracked_in_commit(self, repo):
        _seed_demo_poem(str(repo))
        _, out = _git('-C', str(repo), 'ls-tree', '-r', 'HEAD', '--name-only')
        assert _DEMO_POEM_NAME in out.splitlines()

    def test_idempotent_when_file_already_exists(self, repo):
        _seed_demo_poem(str(repo))
        _seed_demo_poem(str(repo))  # second call should be a no-op
        _, out = _git('-C', str(repo), 'log', '--oneline')
        assert len(out.strip().splitlines()) == 1


# ---------------------------------------------------------------------------
# Editor._do_commit_and_stage()
# ---------------------------------------------------------------------------

class TestDoCommitAndStage:
    def test_returns_false_when_repo_path_is_none(self, ed):
        saved = ed._repo_path
        ed._repo_path = None
        result = ed._do_commit_and_stage('msg')
        ed._repo_path = saved
        assert result is False

    def test_returns_false_when_current_path_is_none(self, ed, tmp_path):
        _init_repo(tmp_path)
        saved_repo, saved_path = ed._repo_path, ed._current_path
        ed._repo_path = str(tmp_path)
        ed._current_path = None
        result = ed._do_commit_and_stage('msg')
        ed._repo_path, ed._current_path = saved_repo, saved_path
        assert result is False

    def test_returns_true_on_successful_commit(self, ed, tmp_path):
        _init_repo(tmp_path)
        saved_repo, saved_path = ed._repo_path, ed._current_path
        ed._repo_path = str(tmp_path)
        ed._current_path = str(tmp_path / 'poem.txt')
        _set_editor_line(ed, 0, 'Shall I compare thee')
        result = ed._do_commit_and_stage('first version')
        ed._repo_path, ed._current_path = saved_repo, saved_path
        assert result is True

    def test_commit_message_appears_in_log(self, ed, tmp_path):
        _init_repo(tmp_path)
        saved_repo, saved_path = ed._repo_path, ed._current_path
        ed._repo_path = str(tmp_path)
        ed._current_path = str(tmp_path / 'poem.txt')
        _set_editor_line(ed, 0, 'To be or not to be')
        ed._do_commit_and_stage('my special message')
        _, out = _git('-C', str(tmp_path), 'log', '--format=%s')
        ed._repo_path, ed._current_path = saved_repo, saved_path
        assert 'my special message' in out

    def test_returns_false_when_nothing_changed(self, ed, tmp_path):
        _init_repo(tmp_path)
        saved_repo, saved_path = ed._repo_path, ed._current_path
        ed._repo_path = str(tmp_path)
        ed._current_path = str(tmp_path / 'poem.txt')
        _set_editor_line(ed, 0, 'unchanged line')
        ed._do_commit_and_stage('first')
        # Second commit with identical content — nothing to stage
        result = ed._do_commit_and_stage('second')
        ed._repo_path, ed._current_path = saved_repo, saved_path
        assert result is False

    def test_file_content_reaches_repo(self, ed, tmp_path):
        _init_repo(tmp_path)
        saved_repo, saved_path = ed._repo_path, ed._current_path
        ed._repo_path = str(tmp_path)
        ed._current_path = str(tmp_path / 'poem.txt')
        _set_editor_line(ed, 0, 'committed text')
        ed._do_commit_and_stage('add')
        rc = subprocess.run(
            ['git', '-C', str(tmp_path), 'show', 'HEAD:poem.txt'],
            capture_output=True,
        )
        ed._repo_path, ed._current_path = saved_repo, saved_path
        assert b'committed text' in rc.stdout


# ---------------------------------------------------------------------------
# Editor._load_blob_at_path()
# ---------------------------------------------------------------------------

class TestLoadBlobAtPath:
    def test_returns_bytes_for_existing_file(self, ed, repo):
        sha = _commit_file(repo, 'poem.txt', 'hello world\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path(sha, 'poem.txt')
        ed._repo_path = saved
        assert isinstance(data, bytes)
        assert data == b'hello world\n'

    def test_accepts_bytes_sha(self, ed, repo):
        sha = _commit_file(repo, 'poem.txt', 'bytes sha\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path(sha.encode(), 'poem.txt')
        ed._repo_path = saved
        assert data == b'bytes sha\n'

    def test_returns_none_for_missing_file(self, ed, repo):
        sha = _commit_file(repo, 'poem.txt', 'content\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path(sha, 'nosuchfile.txt')
        ed._repo_path = saved
        assert data is None

    def test_returns_none_for_invalid_sha(self, ed, repo):
        _commit_file(repo, 'poem.txt', 'content\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path('0' * 40, 'poem.txt')
        ed._repo_path = saved
        assert data is None

    def test_retrieves_historical_version(self, ed, repo):
        sha1 = _commit_file(repo, 'poem.txt', 'version one\n')
        _commit_file(repo, 'poem.txt', 'version two\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path(sha1, 'poem.txt')
        ed._repo_path = saved
        assert data == b'version one\n'

    def test_unicode_content_preserved(self, ed, repo):
        sha = _commit_file(repo, 'poem.txt', 'café naïve résumé\n')
        saved = ed._repo_path
        ed._repo_path = str(repo)
        data = ed._load_blob_at_path(sha, 'poem.txt')
        ed._repo_path = saved
        assert data == 'café naïve résumé\n'.encode('utf-8')
