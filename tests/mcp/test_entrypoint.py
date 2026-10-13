from pathlib import Path
import os
import subprocess
import tempfile
import unittest


class EntrypointTests(unittest.TestCase):
    def test_allowlist_and_fixed_root_against_hostile_inherited_env(self):
        source=(Path(__file__).parents[2]/'tools/mcp_entrypoint.sh').read_text()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fake=root/'host'
            fake.write_text('#!/bin/sh\n/usr/bin/env\nprintf "ARG=%s\\n" "$@"\n')
            fake.chmod(0o755)
            entry=root/'entry.sh'
            entry.write_text(source.replace('/opt/arxo/runtime/bin/law-mcp-server','/bin/sh '+str(fake)))
            entry.chmod(0o755)
            env={**os.environ,'FIDE_CHESS_MCP_TOKEN':'test-token','LAW_ANSWERS_URL':'https://publish.invalid','LAW_NEURAL_URL':'https://neural.invalid','LAW_MCP_OTLP_URL':'https://otlp.invalid','LAW_MCP_ROOT':'/foreign','LAW_MCP_PROFILE':'all'}
            output=subprocess.check_output(['/bin/sh',str(entry),'http'],env=env,text=True)
            for denied in ('LAW_ANSWERS_URL','LAW_NEURAL_URL','LAW_MCP_OTLP_URL','/foreign','ARG=all'):
                self.assertNotIn(denied,output)
            self.assertIn('ARG=/opt/arxo/runtime',output)
            self.assertIn('ARG=fide-chess',output)
            self.assertIn('LAW_MCP_ARTIFACT_DIR=/state/artifacts',output)
            self.assertIn('LAW_MCP_TOKEN=test-token',output)

    def test_http_without_token_refuses_before_host_launch(self):
        entry=Path(__file__).parents[2]/'tools/mcp_entrypoint.sh'
        env={'PATH':'/usr/bin:/bin'}
        result=subprocess.run(['/bin/sh',str(entry),'http'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,64)
        self.assertIn('FIDE_CHESS_MCP_TOKEN',result.stderr)

    def test_unsafe_argument_and_unbounded_timeout_refuse(self):
        entry=Path(__file__).parents[2]/'tools/mcp_entrypoint.sh'
        for args,env in [(['--root','/foreign'],{}),(['http'],{'FIDE_CHESS_MCP_TOKEN':'x','FIDE_CHESS_MCP_CALL_TIMEOUT':'0'})]:
            result=subprocess.run(['/bin/sh',str(entry),*args],env={'PATH':'/usr/bin:/bin',**env},capture_output=True)
            self.assertEqual(result.returncode,64)


if __name__=='__main__':unittest.main()
