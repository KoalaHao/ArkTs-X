"""Recovery guards: verify exact patches without mutating checkout/index state."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from bootstrap_deps import verify_patch


class PatchRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        self.run_git('init', '-q')
        self.run_git('config', 'user.name', 'Recovery test')
        self.run_git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'existing.cpp').write_text('original\n')
        self.run_git('add', 'existing.cpp')
        self.run_git('commit', '-qm', 'fixture')
        (self.repo / 'existing.cpp').write_text('macOS modification\n')
        (self.repo / 'added.h').write_text('new macOS source\n')
        self.run_git('add', 'added.h')
        self.patch = self.root / 'port.patch'
        self.patch.write_bytes(self.run_git('diff', 'HEAD', '--binary'))
        self.run_git('reset', '-q', 'HEAD')
        self.index = (self.repo / '.git/index').read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def run_git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.STDOUT)

    def test_exact_patch_is_idempotent_and_preserves_index(self):
        verify_patch(self.repo, self.patch)
        verify_patch(self.repo, self.patch)
        self.assertEqual(self.index, (self.repo / '.git/index').read_bytes())
        self.assertEqual('new macOS source\n', (self.repo / 'added.h').read_text())

    def test_rejects_extra_edit_in_patched_file(self):
        (self.repo / 'existing.cpp').write_text('macOS modification\nunexpected edit\n')
        with self.assertRaises(subprocess.CalledProcessError):
            verify_patch(self.repo, self.patch)
        self.assertEqual(self.index, (self.repo / '.git/index').read_bytes())

    def test_rejects_changed_added_source(self):
        (self.repo / 'added.h').write_text('unexpected replacement\n')
        with self.assertRaises(subprocess.CalledProcessError):
            verify_patch(self.repo, self.patch)

    def test_rejects_unexpected_untracked_source(self):
        (self.repo / 'unrelated.cpp').write_text('local work\n')
        with self.assertRaises(RuntimeError):
            verify_patch(self.repo, self.patch)
        self.assertEqual('local work\n', (self.repo / 'unrelated.cpp').read_text())

    def test_rejects_missing_added_source(self):
        (self.repo / 'added.h').unlink()
        with self.assertRaises(RuntimeError):
            verify_patch(self.repo, self.patch)


if __name__ == '__main__':
    unittest.main()
