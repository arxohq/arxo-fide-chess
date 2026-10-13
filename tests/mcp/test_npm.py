import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[2]/'tools';sys.path.insert(0,str(TOOLS))
import mcp_npm


class InstalledIdentity(unittest.TestCase):
    def test_installed_launcher_bytes_must_match_tarball(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';package.mkdir();(package/'launcher.js').write_text('accepted')
            archive=root/'a.tgz'
            with tarfile.open(archive,'w:gz') as t:t.add(package,arcname='package')
            mcp_npm.verify_installed(package,archive)
            (package/'launcher.js').write_text('different')
            with self.assertRaisesRegex(ValueError,'differs'):mcp_npm.verify_installed(package,archive)
    def test_extra_installed_file_and_symlink_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';package.mkdir();(package/'p').write_text('p');archive=root/'a.tgz'
            with tarfile.open(archive,'w:gz') as t:t.add(package,arcname='package')
            (package/'extra').write_text('private')
            with self.assertRaisesRegex(ValueError,'differs'):mcp_npm.verify_installed(package,archive)
            (package/'extra').unlink();(package/'extra').symlink_to('/etc/hosts')
            with self.assertRaisesRegex(ValueError,'symlink'):mcp_npm.verify_installed(package,archive)
    def test_changed_acceptance_source_fails_before_npm_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j={'profile':'fide-chess','consumer':{'repository':'arxohq/arxo-fide-chess','files':{p:'sha256:'+'0'*64 for p in mcp_npm.source_files(mcp_npm.ROOT)}}}
            (root/'npm-release.json').write_text(json.dumps(j))
            with self.assertRaisesRegex(ValueError,'acceptance source differs'):mcp_npm.smoke(root,False,root/'receipt')
    def test_wrong_runtime_archive_hash_fails_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'a.tgz';archive.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'archive differs'):mcp_npm.archive_runtime(archive,root,'sha256:'+'0'*64)

if __name__=='__main__':unittest.main()
