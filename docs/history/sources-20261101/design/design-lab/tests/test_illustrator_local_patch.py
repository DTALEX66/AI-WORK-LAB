# SPDX-License-Identifier: MIT
"""Actual JSX patch dispatch with host DOM doubles, not native evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class IllustratorLocalPatchTests(unittest.TestCase):
    def test_owned_patch_saves_new_version_and_rejects_before_mutation(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required')
        script = r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;
let files=new Set(),saves=[],closed=0,opens=[],snapshots={};
function File(p){const name=path.resolve(p);return {fsName:name,parent:{exists:true},
 get exists(){return /baseline\.ai$|existing\.ai$/.test(name)||files.has(name);},
 get length(){return this.exists?120:0;}};}
const context={File,Folder:p=>({fsName:path.resolve(p),exists:true}),
 IllustratorSaveOptions:function(){},SaveOptions:{DONOTSAVECHANGES:2},
 app:{open:f=>{opens.push(f.fsName);return {...snapshots[f.fsName],fullName:f,marker:'reopened'};}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),context);
function doc(){return {saved:true,fullName:File('D:/run/baseline.ai'),
 textFrames:[{name:'title',contents:'BEFORE'},{name:'untouched',contents:'SENTINEL'}],
 pathItems:[{name:'curve',pathPoints:[{anchor:[1,2],leftDirection:[1,2],rightDirection:[2,3]},
  {anchor:[4,5],leftDirection:[3,4],rightDirection:[4,5]}]}],
 saveAs(f,o){saves.push(f.fsName);files.add(f.fsName);this.fullName=f;
  snapshots[f.fsName]=JSON.parse(JSON.stringify({textFrames:this.textFrames,pathItems:this.pathItems}));},
 close(){closed++;}};}
function run(d,p,target='D:/run/edited.ai',expected='D:/run/baseline.ai'){
 context.payload=JSON.stringify(p);return context.applyApprovedPatch(d,expected,
 vm.runInContext('JSON.parse(payload)',context),target,'D:/run');}
const report={validError:null,cases:[]};
try {
 const d=doc(),r=run(d,{kind:'text',id:'title',text:'AFTER'});
 report.text=d.textFrames.map(t=>t.contents);report.returned=r.marker;
 report.target=r.fullName.fsName;
 const d2=doc();run(d2,{kind:'path',id:'curve',points:[
  {anchor:[10,20],left:[9,20],right:[11,21]},
  {anchor:[40,50],left:[39,49],right:[40,50]}]},'D:/run/geometry.ai');
 report.points=d2.pathItems[0].pathPoints;report.pathText=d2.textFrames[0].contents;
 report.saves=saves.slice();report.closed=closed;report.opens=opens.slice();
} catch(e){report.validError=String(e);}
const mutations=[
 ['unknown-kind',(d,p)=>p.kind='menu'],
 ['unknown-field',(d,p)=>p.command='anything'],
 ['absent-id',(d,p)=>p.id='absent'],
 ['duplicate-id',(d,p)=>d.textFrames.push({name:'title',contents:'other'})],
 ['empty-text',(d,p)=>p.text=''],
 ['unsaved-document',(d,p)=>d.saved=false],
 ['wrong-document',(d,p)=>d.fullName=File('D:/run/unrelated.ai')]
];
for(const [name,change] of mutations){
 const d=doc(),p={kind:'text',id:'title',text:'AFTER'};change(d,p);
 const before=saves.length;let rejected=false;
 try{run(d,p,'D:/run/negative.ai');}catch(e){rejected=true;}
 report.cases.push({name,rejected,unmodified:d.textFrames[0].contents==='BEFORE',saves:saves.length-before});
}
for(const target of ['D:/run/existing.ai','D:/outside/next.ai','D:/run/output.svg']){
 const d=doc(),before=saves.length;let rejected=false;
 try{run(d,{kind:'text',id:'title',text:'AFTER'},target);}catch(e){rejected=true;}
 report.cases.push({name:target,rejected,unmodified:d.textFrames[0].contents==='BEFORE',saves:saves.length-before});
}
for(const [name,points] of [
 ['invalid-late-point',[{anchor:[10,20],left:[9,20],right:[11,21]},
                       {anchor:[40,50],left:[39,49],right:[null,50]}]],
 ['changed-topology',[{anchor:[10,20],left:[9,20],right:[11,21]}]]
]){
 const d=doc(),before=saves.length,original=JSON.stringify(d.pathItems);let rejected=false;
 try{run(d,{kind:'path',id:'curve',points},'D:/run/negative.ai');}catch(e){rejected=true;}
 report.cases.push({name,rejected,unmodified:JSON.stringify(d.pathItems)===original,saves:saves.length-before});
}
console.log(JSON.stringify(report));
'''
        result = subprocess.run([node, '-e', script, str(ROOT / 'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx')],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIsNone(report['validError'])
        self.assertEqual(report['text'], ['AFTER', 'SENTINEL'])
        self.assertEqual(report['returned'], 'reopened')
        self.assertEqual(report['target'], r'D:\run\edited.ai')
        self.assertEqual(report['points'][0]['anchor'], [10, 20])
        self.assertEqual(report['points'][1]['leftDirection'], [39, 49])
        self.assertEqual(report['pathText'], 'BEFORE')
        self.assertEqual(report['saves'], [r'D:\run\edited.ai', r'D:\run\geometry.ai'])
        self.assertEqual(report['closed'], 2)
        self.assertEqual(report['opens'], report['saves'])
        for case in report['cases']:
            with self.subTest(case=case['name']):
                self.assertTrue(case['rejected'], case)
                self.assertTrue(case['unmodified'], case)
                self.assertEqual(case['saves'], 0, case)


if __name__ == '__main__':
    unittest.main()
