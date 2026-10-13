import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cp, mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
import { loadModel, ModelNotFoundError } from '@arxo/canon-fide-chess';
const root=new URL('./',import.meta.resolve('@arxo/canon-fide-chess/package.json'));
const spec='fide.laws.chess@0.1.1';
const sha=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
test('unknown and versionless specs fail; fresh worlds are isolated',async()=>{
  const circular = {}; circular.self = circular;
  for(const s of ['fide.laws.chess','fide.laws.chess@9.0.0','../world',null,1n,circular])await assert.rejects(loadModel(s),e=>e instanceof ModelNotFoundError&&e.code==='MODEL_NOT_FOUND');
  const a=await loadModel(spec);a.package.ir.package.name='changed';assert.equal((await loadModel(spec)).package.ir.package.name,'fide.laws.chess');
});
test('metadata-only root import and integrity failures in isolated copies',async()=>{
  for(const mode of ['missing-world','bad-world','missing-catalog','mismatched-descriptor']){
    const dir=await mkdtemp(join(tmpdir(),'fide-loader-'));
    try{
      for(const file of ['src','data','models.json','source-pin.json','package.json'])await cp(new URL(file,root),join(dir,file),{recursive:true});
      const world=join(dir,'data/chess/world.lawir.json');
      if(mode==='missing-world')await rm(world);
      if(mode==='bad-world')await writeFile(world,'not JSON');
      if(mode==='missing-catalog'){
        const pin=JSON.parse(await readFile(join(dir,'source-pin.json')));const hash=pin.models[0].questionCatalogHash.slice(7);
        await rm(join(dir,`data/resources/${hash}.json`));
      }
      if(mode==='mismatched-descriptor'){
        const target='data/chess/descriptor.json';const descriptor=JSON.parse(await readFile(join(dir,target)));descriptor.worldHash='sha256:'+'0'.repeat(64);
        const bytes=Buffer.from(JSON.stringify(descriptor));await writeFile(join(dir,target),bytes);
        const pin=JSON.parse(await readFile(join(dir,'source-pin.json')));pin.files[target].sha256=sha(bytes);pin.files[target].bytes=bytes.length;await writeFile(join(dir,'source-pin.json'),JSON.stringify(pin));
      }
      const copy=await import(pathToFileURL(join(dir,'src/index.js')));
      assert.equal(copy.models.length,1,'root must not read model assets');
      await assert.rejects(copy.loadModel(spec),e=>e.code==='MODEL_INTEGRITY',mode);
    }finally{await rm(dir,{recursive:true,force:true});}
  }
});
