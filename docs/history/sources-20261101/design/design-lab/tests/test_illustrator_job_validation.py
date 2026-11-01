# SPDX-License-Identifier: MIT
"""Real JSX preflight decisions; host filesystem/font boundaries are doubles.

Rejecting a job must happen before any document is created. This is not a
native Illustrator qualification and does not establish filesystem race safety.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
JSX = ROOT / 'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx'


class IllustratorJobValidationTests(unittest.TestCase):
    def test_invalid_jobs_never_reach_document_creation(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required for executing JSX validation')
        script = r'''
const fs = require('fs'), vm = require('vm'), path = require('path').win32;
let creates = 0;
const context = {
 File: p => ({fsName:path.resolve(p),exists:/input\.png$|existing\.ai$/.test(p)}),
 Folder: p => ({fsName:path.resolve(p),exists:true}),
 app: {textFonts:{getByName:n=>{if(n!=='ArialMT')throw Error('missing font');return {name:n};}},
       documents:{add:()=>{creates++;return {artboards:[{}]};}}},
 DocumentColorSpace:{RGB:'RGB'}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),context);
const base = {
 schemaVersion:'design-lab/adobe-host-job/v1',jobId:'fixture-01',rirHash:'a'.repeat(64),
 runRoot:'D:/run',artboard:{width:800,height:600},
 authorization:{required:true,scope:'single-session'},
 operations:['createDocument','createLayer','placePath','placeText','placeRaster','applyMask',
             'saveAI','exportSVG','reopen','readback','exportPNG'],
 targets:{ai:'D:/run/output.ai',svg:'D:/run/output.svg',png:'D:/run/output.png'},
 assets:[{id:'image',path:'D:/run/input.png'}],
 layers:[{id:'foreground',items:[
  {id:'title',kind:'text',text:'Editable',position:[20,500],font:'ArialMT',size:32,color:[20,30,40]},
  {id:'shape',kind:'path',points:[{anchor:[10,10],left:[10,10],right:[20,10]},
    {anchor:[60,60],left:[50,60],right:[60,60]}],closed:false,color:[255,0,20]},
  {id:'picture',kind:'raster',assetId:'image',position:[100,400],width:120,height:90}
 ]}]
};
const cases = [
 ['unknown-root-field',j=>j.command='anything'],
 ['missing-targets',j=>delete j.targets],
 ['empty-targets',j=>j.targets={}],
 ['target-outside',j=>j.targets.ai='D:/elsewhere/output.ai'],
 ['existing-output',j=>j.targets.ai='D:/run/existing.ai'],
 ['wrong-extension',j=>j.targets.ai='D:/run/output.txt'],
 ['zero-board',j=>j.artboard.width=0],
 ['nonfinite-board',j=>j.artboard.width=Infinity],
 ['unknown-operation',j=>j.operations.push('arbitrary')],
 ['missing-operation',j=>j.operations.pop()],
 ['zero-rir-hash',j=>j.rirHash='0'.repeat(64)],
 ['duplicate-id',j=>j.layers[0].items[1].id='title'],
 ['missing-font',j=>j.layers[0].items[0].font='NotInstalled'],
 ['unknown-object-kind',j=>j.layers[0].items[0].kind='script'],
 ['unknown-object-field',j=>j.layers[0].items[0].command='anything'],
 ['missing-raster',j=>j.assets[0].path='D:/run/absent.png'],
 ['outside-raster',j=>j.assets[0].path='D:/elsewhere/input.png'],
 ['missing-asset-ref',j=>j.layers[0].items[2].assetId='unknown'],
 ['bad-color',j=>j.layers[0].items[0].color=[-1,0,0]],
 ['bad-bezier',j=>j.layers[0].items[1].points[0].left=[1]],
 ['wrong-authorized-root',j=>j.runRoot='D:/other'],
 ['empty-layers',j=>j.layers=[]]
];
// JSON must be parsed inside the VM to model a host-parsed payload, not
// cross-realm Array identity. Infinity is introduced after parsing.
const result=cases.map(([name,change])=>{
 context.payload=JSON.stringify(base);
 const job=vm.runInContext('JSON.parse(payload)',context);change(job);
 const before=creates;let rejected=false,error='';
 try{context.runApprovedJob(job,'D:/run');}catch(e){rejected=true;error=String(e);}
 return {name,rejected,creates:creates-before,error};
});
context.payload=JSON.stringify(base);
const grouped=vm.runInContext('JSON.parse(payload)',context);
const mask=vm.runInContext('JSON.parse(payload)',context).layers[0].items[1];
mask.id='clip';mask.closed=true;
const picture=grouped.layers[0].items.pop();
grouped.layers[0].items.push({id:'media-group',kind:'group',items:[picture],mask});
// Build in the VM realm, as the real native job parser does.
context.payload=JSON.stringify(grouped);
let groupError=null;
try{context.validateJob(vm.runInContext('JSON.parse(payload)',context),'D:/run');}
catch(e){groupError=String(e);}
const groupCases=[
 ['mask-open',j=>j.layers[0].items[2].mask.closed=false],
 ['mask-not-path',j=>j.layers[0].items[2].mask.kind='text'],
 ['group-empty',j=>j.layers[0].items[2].items=[]],
 ['nested-id-conflict',j=>j.layers[0].items[2].items[0].id='title'],
 ['mask-id-conflict',j=>j.layers[0].items[2].mask.id='title'],
 ['nested-unknown-field',j=>j.layers[0].items[2].items[0].command='anything']
];
for(const [name,change] of groupCases){
 context.payload=JSON.stringify(grouped);const job=vm.runInContext('JSON.parse(payload)',context);change(job);
 const before=creates;let rejected=false;
 try{context.runApprovedJob(job,'D:/run');}catch(e){rejected=true;}
 result.push({name,rejected,creates:creates-before});
}
context.payload=JSON.stringify(base);
let validError=null;
try{context.validateJob(vm.runInContext('JSON.parse(payload)',context),'D:/run');}
catch(e){validError=String(e);}
console.log(JSON.stringify({result,validError,groupError}));
'''
        result = subprocess.run([node, '-e', script, str(JSX)], capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIsNone(report['validError'], report['validError'])
        self.assertIsNone(report['groupError'], report['groupError'])
        for case in report['result']:
            with self.subTest(case=case['name']):
                self.assertTrue(case['rejected'], case)
                self.assertEqual(case['creates'], 0, case)


if __name__ == '__main__':
    unittest.main()
