# SPDX-License-Identifier: MIT
"""Execute actual legacy JSX validation in Node, not a Photoshop live claim."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
JSX=ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx'


class PhotoshopLegacyNativeTests(unittest.TestCase):
    def test_dirty_open_input_is_rejected_without_closing_user_document(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;let closes=0;
const c={File:p=>({fsName:path.resolve(p)}),app:{documents:[
 {saved:false,fullName:{fsName:'D:/run/input.png'},close:()=>{closes++}}
]}};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
let rejection=null;try{c.psRejectOpenInputs({assets:[{path:'D:/run/input.png'}]})}catch(e){rejection=e.message}
console.log(JSON.stringify({rejection,closes}));
'''
        result=subprocess.run([node,'-e',script,str(JSX)],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'rejection':'input already open','closes':0})

    def test_selection_coordinates_are_explicit_pixels_not_user_ruler_units(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
const c={UnitValue:(value,unit)=>({value,unit})};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
console.log(JSON.stringify(c.psRect([10,20,30,40])));
'''
        result=subprocess.run([node,'-e',script,str(JSX)],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[
            [{'value':10,'unit':'px'},{'value':20,'unit':'px'}],
            [{'value':40,'unit':'px'},{'value':20,'unit':'px'}],
            [{'value':40,'unit':'px'},{'value':60,'unit':'px'}],
            [{'value':10,'unit':'px'},{'value':60,'unit':'px'}]])

    def test_closed_jobs_reject_before_document_creation(self):
        self.assertTrue(JSX.is_file(),'native Photoshop bridge is missing')
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;let creates=0;
const c={File:p=>({fsName:path.resolve(p),exists:/input.png$|existing.psd$/.test(p)}),Folder:p=>({fsName:path.resolve(p),exists:true}),
 app:{fonts:{getByName:n=>{if(n!=='ArialMT')throw Error('font missing');return {postScriptName:n};}},documents:{add:()=>{creates++;throw Error('unexpected dispatch');}}}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
const base={schemaVersion:'design-lab/photoshop-native-job/v1',jobId:'ps-test',runRoot:'D:/run',width:800,height:600,
 outputName:'output.psd',previewName:'output.png',assets:[{id:'input',path:'D:/run/input.png'}],layers:[
 {id:'title',kind:'text',text:'LIVE',font:'ArialMT',size:32,position:[40,60],color:[20,40,60]},
 {id:'group',kind:'group',mask:[100,100,200,200],children:[{id:'image',kind:'raster',assetId:'input',position:[100,100],width:256,height:256}]}
]};
const clone=()=>{c.payload=JSON.stringify(base);return vm.runInContext('JSON.parse(payload)',c)};
let valid=null;try{c.psValidate(clone(),'D:/run')}catch(e){valid=String(e)}
const cases=[j=>j.command='execute',j=>j.width=0,j=>j.width=NaN,j=>j.runRoot='D:/other',j=>j.outputName='../escape.psd',
 j=>j.outputName='existing.psd',j=>j.assets[0].path='D:/else/input.png',j=>j.layers[0].font='missing',
 j=>j.layers[1].children[0].id='title',j=>j.layers[1].mask=[1,2,-3,4],j=>j.layers[0].kind='script',
 j=>j.layers[0].color=[-1,0,0],j=>j.layers[0].text='',j=>j.layers[1].children=[],j=>j.layers[1].children[0].assetId='nope'];
const rejected=cases.map(change=>{const j=clone();change(j);try{c.psRunJob(j,'D:/run');return false}catch(e){return true}});
console.log(JSON.stringify({valid,rejected,creates}));
'''
        result=subprocess.run([node,'-e',script,str(JSX)],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertIsNone(report['valid'],report['valid'])
        self.assertEqual(report['rejected'],[True]*15)
        self.assertEqual(report['creates'],0)


if __name__ == '__main__':
    unittest.main()
