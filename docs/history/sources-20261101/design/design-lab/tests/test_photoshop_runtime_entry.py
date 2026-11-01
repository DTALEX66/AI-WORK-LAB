# SPDX-License-Identifier: MIT
"""Execute the UXP adapter with explicit host/storage doubles; not host-live."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PhotoshopRuntimeEntryTests(unittest.TestCase):
    def test_native_roundtrip_and_prewrite_rejections(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required')
        js = r'''
const vm=require('vm'),fs=require('fs');
let calls=[],snapshot,ctx={isCancelled:false},corrupt=false,failSave=false,cancelOnText=false;
const doc={id:100,width:800,height:600,layers:[],
 async createTextLayer(o){calls.push('text');this.layers.push({name:o.name,textItem:{contents:o.contents}});if(cancelOnText)ctx.isCancelled=true;},
 saveAs:{async psd(f,o,copy){calls.push('save');if(failSave)throw Error('disk failure');snapshot={id:101,width:800,height:600,path:f.nativePath,
  layers:JSON.parse(JSON.stringify(doc.layers))};if(corrupt)snapshot.layers[0].textItem.contents='WRONG';}},
 async closeWithoutSaving(){calls.push('close');}};
const app={version:'26.7.0',documents:[],async createDocument(o){calls.push('create');
 if(o.width!==800||o.height!==600||o.fill!=='transparent')throw Error('bad create options');doc.layers=[];return doc;},
 async open(f){calls.push('open');return snapshot;}};
const core={async executeAsModal(fn){calls.push('modal');return fn(ctx);}};
const box={module:{exports:{}},require:n=>{if(n==='photoshop')return {app,core};throw Error(n);}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),box);
const api=box.module.exports;
const base={runRoot:'D:/run',outputName:'out.psd',width:800,height:600,
 layers:[{id:'title',kind:'text',contents:'EDITABLE',fontSize:32}]};
const folder={isFolder:true,nativePath:'D:\\run',async getEntries(){return [];},
 async createFile(name,opts){if(opts.overwrite!==false)throw Error('unsafe overwrite');calls.push('file');
 return {isFile:true,nativePath:'D:\\run\\'+name};}};
(async()=>{
let validError=null,result;try{result=await api.executeJob(base,folder);}catch(e){validError=String(e);}
const validCalls=calls.slice();const cases=[];
for(const [name,change] of [
 ['unknown-root',j=>j.command='x'],['outside-name',j=>j.outputName='../out.psd'],
 ['extension',j=>j.outputName='out.png'],['unsupported-raster',j=>j.layers[0].kind='raster'],
 ['empty-text',j=>j.layers[0].contents=''],['invalid-size',j=>j.layers[0].fontSize=0],
 ['duplicate-id',j=>j.layers.push({...j.layers[0]})],['bad-width',j=>j.width=0],
 ['wrong-root',j=>j.runRoot='D:/outside'],['dot-root',j=>j.runRoot='D:/run/../run']]){
 const j=JSON.parse(JSON.stringify(base));change(j);calls=[];let rejected=false;
 try{await api.executeJob(j,folder);}catch(e){rejected=true;}
 cases.push({name,rejected,writes:calls.filter(x=>['create','file','text','save'].includes(x)).length});
}
for(const name of ['existing-output','cancelled','missing-folder','old-host']){
 app.version=name==='old-host'?'24.1.0':'26.7.0';
 calls=[];ctx.isCancelled=name==='cancelled';let rejected=false;
 const f=name==='missing-folder'?null:name==='existing-output'?{...folder,getEntries:async()=>[{name:'OUT.PSD'}]}:folder;
 try{await api.executeJob(base,f);}catch(e){rejected=true;}
 cases.push({name,rejected,writes:calls.filter(x=>['create','file','text','save'].includes(x)).length});
}
app.version='26.7.0';ctx.isCancelled=false;corrupt=true;let corruptRejected=false;
try{await api.executeJob(base,folder);}catch(e){corruptRejected=true;}
corrupt=false;const failures=[];
for(const mode of ['save-failure','cancel-after-text']){
 calls=[];ctx.isCancelled=false;failSave=mode==='save-failure';cancelOnText=mode==='cancel-after-text';
 let error=null;try{await api.executeJob(base,folder);}catch(e){error={id:e.taskDocumentId,path:e.taskOutputPath};}
 failures.push({mode,error,closed:calls.includes('close'),opened:calls.includes('open')});
}
console.log(JSON.stringify({validError,result,validCalls,cases,corruptRejected,failures}));
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        proc = subprocess.run([node, '-e', js, str(ROOT / 'integrations/hosts/adobe/photoshop-reconstruction/index.js')],
                              capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertIsNone(result['validError'])
        self.assertEqual(result['result']['status'], 'NATIVE_READBACK')
        self.assertEqual(result['result']['documentId'], 101)
        self.assertEqual(result['result']['textCount'], 1)
        self.assertEqual(result['validCalls'], ['modal', 'file', 'create', 'text', 'save', 'close', 'open'])
        for case in result['cases']:
            with self.subTest(case=case['name']):
                self.assertTrue(case['rejected'], case)
                self.assertEqual(case['writes'], 0, case)
        self.assertTrue(result['corruptRejected'])
        for failure in result['failures']:
            self.assertEqual(failure['error'], {'id': 100, 'path': r'D:\run\out.psd'})
            self.assertFalse(failure['closed'])
            self.assertFalse(failure['opened'])


if __name__ == '__main__':
    unittest.main()
