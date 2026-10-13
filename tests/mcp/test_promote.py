"""Actual promotion admission with Docker boundaries mocked, never publishing."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from standalone_mcp import config, promote
except ImportError:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
    from standalone_mcp import config, promote


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.directory=Path(self.temp.name)/'candidate'
        self.root.mkdir();self.directory.mkdir();self.commit='b'*40;self.host_source='c'*40
        self.host_sha='1'*64;self.tree_sha='sha256:'+'2'*64;self.image='sha256:'+'3'*64
        def put(root,rel,value):
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':')).encode())
        self.put=put
        delivery={'format':config.FORMAT,'profileId':'example','producerRepository':'arxohq/example',
                  'packageName':'@arxo/mcp-example','refs':config.DEFAULT_REFS,
                  'selectedPublications':[{'name':'example.rules','version':'1.0.0','runtimeKey':'example','packagePath':'corpus/laws/example','role':'root'}]}
        put(self.root,'mcp/delivery.json',delivery)
        put(self.root,'mcp/cases/acceptance.json',{});put(self.root,'mcp/source-policy.json',{})
        expected={'platform':'linux-amd64','binarySha256':'sha256:'+self.host_sha,'sourceCommit':self.host_source}
        lock={'host':{'sourceCommit':self.host_source,'platforms':{'linux-amd64':{'binarySha256':'sha256:'+self.host_sha}}}}
        tree={'treeSha256':self.tree_sha}
        for name,obj in [('runtime.lock.json',lock),('tree.pin.json',tree)]:
            put(self.root,'mcp/'+name,obj);put(self.directory,name,obj)
        put(self.directory,'image.tar',b'exact accepted OCI archive');put(self.directory,'runtime.tar.gz',b'exact accepted runtime archive')
        put(self.directory,'container-policy.json',{});put(self.directory,'materialization.json',{})
        put(self.directory,'runtime-contract.json',{'status':'accepted','acceptance':{'finalHostPin':expected}})
        put(self.directory,'host-compatibility.json',{'status':'compatible','platforms':{'linux-amd64':{'status':'compatible','binarySha256':expected['binarySha256'],'sourceCommit':self.host_source,'checks':[{'status':'passed'}]}}})
        smoke={'status':'passed','hostSha256':self.host_sha,'checks':[{'id':'initialize','status':'passed'}],
               'networkIsolation':'Docker network none','casesSha256':promote.sha(self.root/'mcp/cases/acceptance.json'),
               'sourcePolicySha256':promote.sha(self.root/'mcp/source-policy.json')}
        put(self.directory,'offline-smoke.json',smoke);put(self.directory,'image-smoke.json',smoke)
        self.receipt={'format':'arxo.mcp-candidate/0.1','profile':'example','producer':'arxohq/example','sourceCommit':self.commit,
                     'status':'accepted','fullCorpus':'not_checked','releaseVerified':False,'imageId':self.image,'runtimeTreeDigest':self.tree_sha,
                     'hostBinarySha256':self.host_sha,'acceptedHost':expected,'files':{p.name:promote.sha(p) for p in self.directory.iterdir()},
                     'acceptance':{k:smoke[k] for k in ('casesSha256','sourcePolicySha256')}|{'httpCheckIds':['initialize']}}
        self.receipt_sha=self.save_receipt()

    def save_receipt(self):
        self.put(self.directory,'candidate.json',self.receipt);return promote.sha(self.directory/'candidate.json')

    def verify(self):
        with patch.object(promote,'archive_image_id') as archive,patch.object(promote,'validate_container_policy') as policy:
            value=promote.verify(self.directory,self.receipt_sha,self.commit,self.root)
            archive.assert_called_once_with(self.directory/'image.tar',self.image)
            policy.assert_called_once()
            return value

    def test_exact_identity_and_preview_scope(self):
        self.assertEqual(self.verify()['producer'],'arxohq/example')

    def test_cross_profile_and_cross_producer_receipts_are_refused(self):
        for key,value in [('profile','cnaf'),('producer','arxohq/arxo-cnaf')]:
            original=self.receipt[key];self.receipt[key]=value;self.receipt_sha=self.save_receipt()
            with self.assertRaisesRegex(ValueError,'another profile/producer'):self.verify()
            self.receipt[key]=original

    def test_changed_artifact_and_committed_cases_are_refused(self):
        (self.directory/'runtime.tar.gz').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.verify()
        (self.directory/'runtime.tar.gz').write_bytes(b'exact accepted runtime archive')
        (self.root/'mcp/cases/acceptance.json').write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(ValueError,'committed producer inputs'):self.verify()

    def test_receipt_wrong_commit_and_scope_are_refused(self):
        self.receipt['sourceCommit']='d'*40;self.receipt_sha=self.save_receipt()
        with self.assertRaisesRegex(ValueError,'selected immutable commit'):self.verify()
        self.receipt['sourceCommit']=self.commit;self.receipt['releaseVerified']=True;self.receipt_sha=self.save_receipt()
        with self.assertRaisesRegex(ValueError,'scope changed'):self.verify()

    def test_destination_mismatch_fails_before_docker_or_publish(self):
        argv=['promote_mcp.py','--root',str(self.root),'--directory',str(self.directory),'--receipt-sha256',self.receipt_sha,
              '--source-commit',self.commit,'--image','ghcr.io/arxohq/arxo-cnaf-mcp:preview-'+self.commit]
        with patch.object(sys,'argv',argv),patch.object(promote,'verify',return_value=self.receipt),patch.object(promote.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'repository/tag differs'):promote.main()
            run.assert_not_called()


if __name__=='__main__':unittest.main()
