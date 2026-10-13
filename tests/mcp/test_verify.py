from pathlib import Path
import sys
import tempfile
import unittest
import json
import hashlib
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from test_materialize import fixture
from standalone_mcp import materialize as m
from standalone_mcp import verify as v
from standalone_mcp import bundle as b


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.base = Path(self.temp.name)
        self.source = fixture(self.base / 'source'); self.tree = self.base / 'runtime'; self.pin = self.base / 'pin.json'
        m.materialize(self.source, self.tree, tree_pin=self.pin)

    def tearDown(self):
        self.temp.cleanup()

    def test_verified(self):
        self.assertEqual(v.verify(self.tree, self.pin)['result'], 'pass')

    def test_altered(self):
        (self.tree / 'NOTICE').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'altered'):
            v.verify(self.tree, self.pin)

    def test_missing(self):
        (self.tree / 'NOTICE').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            v.verify(self.tree, self.pin)

    def test_extra(self):
        (self.tree / 'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'extra'):
            v.verify(self.tree, self.pin)

    def test_wrong_mode(self):
        (self.tree / 'NOTICE').chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'mode'):
            v.verify(self.tree, self.pin)

    def test_symlink(self):
        (self.tree / 'NOTICE').unlink(); (self.tree / 'NOTICE').symlink_to(self.source / 'NOTICE')
        with self.assertRaisesRegex(ValueError, 'file type'):
            v.verify(self.tree, self.pin)

    def test_pin_inside_tree(self):
        with self.assertRaisesRegex(ValueError, 'external'):
            v.verify(self.tree, self.tree / 'pin.json')

    def test_pin_tamper(self):
        pin = json.loads(self.pin.read_text()); pin['entries'][0]['path'] = '../secret'; self.pin.write_text(json.dumps(pin))
        with self.assertRaisesRegex(ValueError, 'invalid pinned path'):
            v.verify(self.tree, self.pin)

    def test_inventory_uses_posix_string_order(self):
        root = self.base / 'ordered'; root.mkdir()
        (root / 'a').mkdir(); (root / 'a' / 'z').write_text('z'); (root / 'a-z').mkdir()
        for path in root.rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        rows = m.inventory(root)
        self.assertEqual([row['path'] for row in rows], ['a', 'a-z', 'a/z'])

    def test_two_independent_outputs_and_archives(self):
        other, other_pin = self.base / 'second', self.base / 'second-pin.json'
        m.materialize(self.source, other, tree_pin=other_pin)
        self.assertEqual(self.pin.read_bytes(), other_pin.read_bytes())
        one, two = self.base / 'one.tar.gz', self.base / 'two.tar.gz'
        a = b.bundle(self.tree, one, self.pin); z = b.bundle(other, two, other_pin)
        self.assertEqual(a['archiveSha256'], z['archiveSha256'])
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with tarfile.open(one) as archive:
            for member in archive.getmembers():
                self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 0))
                self.assertEqual(member.mode, 0o755 if member.isdir() else 0o644)
        self.assertTrue(Path(str(one) + '.sha256').is_file())


if __name__ == '__main__':
    unittest.main()
