"""Tests for the subprocess-git VCS layer that replaced dulwich."""
import subprocess
import tkinter as tk

import pytest

from poetit.app import (
    Editor,
    _DEMO_POEM,
    _DEMO_POEM_NAME,
    _git,
    _is_git_repo,
    _seed_demo_poem,
)
from poetit.linguistics import Linguistics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _init_repo(path):
    """Initialise a bare git repo at path and return it."""
    subprocess.run(['git', 'init', str(path)], capture_output=True, check=True)
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
# _git()
# ---------------------------------------------------------------------------

class TestGitHelper:
    def test_successful_command_returns_zero_rc(self, tmp_path):
        rc, _ = _git('-C', str(tmp_path), 'init')
        assert rc == 0

    def test_failing_command_returns_nonzero_rc(self, tmp_path):
        # rev-parse on a non-repo directory fails
        rc, _ = _git('-C', str(tmp_path), 'rev-parse', '--git-dir')
        assert rc != 0

    def test_stdout_is_decoded_string(self, repo):
        rc, out = _git('-C', str(repo), 'rev-parse', '--git-dir')
        assert rc == 0
        assert isinstance(out, str)

    def test_cwd_kwarg_sets_working_directory(self, repo):
        rc, _ = _git('rev-parse', '--git-dir', cwd=str(repo))
        assert rc == 0

    def test_output_matches_git_output(self, repo):
        _commit_file(repo, 'a.txt', 'hello')
        rc, out = _git('-C', str(repo), 'log', '--format=%s')
        assert rc == 0
        assert 'add a.txt' in out


# ---------------------------------------------------------------------------
# _is_git_repo()
# ---------------------------------------------------------------------------

class TestIsGitRepo:
    def test_true_for_initialised_repo(self, repo):
        assert _is_git_repo(str(repo)) is True

    def test_false_for_plain_directory(self, tmp_path):
        assert _is_git_repo(str(tmp_path)) is False

    def test_false_for_nonexistent_path(self, tmp_path):
        assert _is_git_repo(str(tmp_path / 'no_such_dir')) is False


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


# ---------------------------------------------------------------------------
# git ls-tree used by _show_repo_browser
# ---------------------------------------------------------------------------

class TestLsTree:
    """Verify the git ls-tree invocation that replaced dulwich's tree walk."""

    def test_txt_files_listed(self, repo):
        _commit_file(repo, 'sonnet.txt', 'content')
        rc, out = _git('-C', str(repo), 'ls-tree', '-r', 'HEAD', '--name-only')
        names = [n for n in out.splitlines() if n.endswith('.txt') and not n.endswith('.meta')]
        assert rc == 0
        assert 'sonnet.txt' in names

    def test_meta_files_excluded_by_filter(self, repo):
        _commit_file(repo, 'poem.txt', 'content')
        _commit_file(repo, 'poem.txt.meta', '{}')
        _, out = _git('-C', str(repo), 'ls-tree', '-r', 'HEAD', '--name-only')
        names = [n for n in out.splitlines() if n.endswith('.txt') and not n.endswith('.meta')]
        assert 'poem.txt' in names
        assert 'poem.txt.meta' not in names

    def test_returns_nonzero_on_empty_repo(self, repo):
        # HEAD doesn't exist before first commit
        rc, _ = _git('-C', str(repo), 'ls-tree', '-r', 'HEAD', '--name-only')
        assert rc != 0

    def test_multiple_poems_all_listed(self, repo):
        _commit_file(repo, 'one.txt', 'a')
        _commit_file(repo, 'two.txt', 'b')
        _, out = _git('-C', str(repo), 'ls-tree', '-r', 'HEAD', '--name-only')
        names = [n for n in out.splitlines() if n.endswith('.txt') and not n.endswith('.meta')]
        assert 'one.txt' in names
        assert 'two.txt' in names
