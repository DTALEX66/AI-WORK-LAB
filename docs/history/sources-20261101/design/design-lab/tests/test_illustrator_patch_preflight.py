# SPDX-License-Identifier: MIT
"""Run the real patch preflight; invalid requests cannot even open a document."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


class PatchPreflightTests(unittest.TestCase):
    def test_malformed_patch_rejected_before_checkpoint_open(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;let opens=0;
const c={File:p=>({fsName:path.resolve(p),exists:/checkpoint\.ai$/.test(p)}),Folder:p=>({fsName:path.resolve(p),exists:true}),
 app:{documents:[],textFonts:{getByName:n=>({name:n})},open:()=>{opens++;throw Error('OPEN_BOUNDARY');}}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
const base={schemaVersion:'design-lab/adobe-patch-job/v1',jobId:'patch',rirHash:'a'.repeat(64),runRoot:'D:/run',
 artboard:{width:100,height:100},assets:[],targets:{ai:'D:/run/new.ai',png:'D:/run/new.png',svg:'D:/run/new.svg'},
 authorization:{required:true,scope:'single-session'},checkpoint:'D:/run/checkpoint.ai',checkpointSha256:'b'.repeat(64),
 operations:['openAI','readback','patchObject','saveAI','reopen','readback','exportPNG','exportSVG'],
 layers:[{id:'layer',items:[{kind:'group',id:'objects',mask:null,items:[
 {kind:'text',id:'title',text:'Before',font:'ArialMT',size:12,color:[0,0,0],position:[5,90]}]}]}],
 patch:{kind:'text',id:'title',text:'After'}};
const cases=[['valid',j=>{}],['absent',j=>j.patch.id='absent'],['wrong-kind',j=>j.patch={kind:'path',id:'title',points:[]}],
 ['empty',j=>j.patch.text=''],['extra',j=>j.patch.command='anything'],['outside',j=>j.checkpoint='D:/outside/checkpoint.ai'],
 ['wrong-sequence',j=>j.operations.reverse()],['wrong-hash',j=>j.checkpointSha256='invalid']];
const results=[];
for(const [name,change] of cases){c.payload=JSON.stringify(base);const j=vm.runInContext('JSON.parse(payload)',c);change(j);
 const before=opens;let error=null;try{c.runApprovedPatchJob(j,'D:/run');}catch(e){error=String(e);}
 results.push({name,opens:opens-before,error});}
console.log(JSON.stringify(results));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx')],
            capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        results=json.loads(result.stdout)
        self.assertEqual(results[0]['opens'],1,results[0])
        self.assertIn('OPEN_BOUNDARY',results[0]['error'])
        for result in results[1:]:
            with self.subTest(case=result['name']):
                self.assertEqual(result['opens'],0,result);self.assertIsNotNone(result['error'])


if __name__=='__main__':unittest.main()
