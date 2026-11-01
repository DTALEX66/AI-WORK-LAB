# SPDX-License-Identifier: MIT
"""Bound native DOM traversal while retaining layer identity/content checks."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


class PhotoshopReadbackScalingTests(unittest.TestCase):
    def test_patch_entry_reads_baseline_then_expected_without_rebuilding(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),events=[];
const doc={close(){events.push('close')}};
const c={File:p=>({fsName:p,exists:true}),app:{documents:[],open:f=>{events.push('open:'+f.fsName);return doc}},SaveOptions:{DONOTSAVECHANGES:1}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
c.psValidate=()=>{};c.psRejectOpenInputs=()=>{};c.psInside=p=>c.File(p);c.psPath=p=>p.toLowerCase();
c.psReadback=(d,j)=>events.push('read:'+j.outputName+':'+j.layers[0].text);
c.psPatch=(d,checkpoint,patch,output)=>{events.push('patch:'+patch.text);return doc};
c.psExportPNG=()=>events.push('png');
vm.runInContext(`var baseline={outputName:'master.psd',previewName:'master.png',layers:[{text:'Before'}]};
var expected={outputName:'master.psd',previewName:'master.png',layers:[{text:'After'}]};
psRunPatchJob({checkpoint:'D:/run/checkpoint.psd',patch:{kind:'text',id:'title',text:'After'}},baseline,expected,'D:/run');`,c);
console.log(JSON.stringify(events));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx')],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),['open:D:/run/checkpoint.psd','read:checkpoint.psd:Before','patch:After',
            'read:master.psd:After','png','close','open:D:/run/master.psd','read:master.psd:After'])

    def test_job_observer_reports_stages_in_execution_order(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
const events=[],doc={activeLayer:{remove(){}},close(){}};
const c={File:p=>({fsName:p}),UnitValue:function(v){return v},
app:{documents:{add:()=>doc},open:()=>doc},NewDocumentMode:{RGB:1},DocumentFill:{TRANSPARENT:1},SaveOptions:{DONOTSAVECHANGES:1}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
c.psValidate=()=>{};c.psRejectOpenInputs=()=>{};c.psSaveNew=()=>doc;c.psReadback=()=>{};c.psExportPNG=()=>{};
c.psRunJob({width:8,height:6,jobId:'fixture',assets:[],layers:[],outputName:'x.psd',previewName:'x.png'},'D:/run',stage=>events.push(stage));
console.log(JSON.stringify(events));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx')],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),['validated','build-start','build-end','save-reopen-start','save-reopen-end','readback-end','export-start','export-end','final-reopen-start','final-readback-end'])

    def test_nested_parent_membership_and_mask_are_still_required(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;
const c={File:p=>({fsName:path.resolve(p)}),LayerKind:{TEXT:'text',NORMAL:'normal'}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
c.psHasMask=l=>l.mask;
const leaf=id=>({name:id,typename:'ArtLayer',kind:'normal'});
const group=(id,child)=>({name:id,typename:'LayerSet',mask:false,layers:[leaf(child)]});
const doc={width:{as:()=>800},height:{as:()=>600},fullName:{fsName:'D:/run/master.psd'},layers:[group('g1','a'),group('g2','b')]};
const spec=(id,child)=>({id,kind:'group',mask:null,children:[{id:child,kind:'raster'}]});
const job={width:800,height:600,runRoot:'D:/run',outputName:'master.psd',layers:[spec('g1','a'),spec('g2','b')]};
const rejects=()=>{try{c.psReadback(doc,job);return false}catch(e){return true}};
const results=[rejects()];
[doc.layers[0].layers,doc.layers[1].layers]=[doc.layers[1].layers,doc.layers[0].layers];results.push(rejects());
[doc.layers[0].layers,doc.layers[1].layers]=[doc.layers[1].layers,doc.layers[0].layers];
doc.layers[0].mask=true;results.push(rejects());doc.layers[0].mask=false;
doc.layers[1].layers[0].name='a';results.push(rejects());
console.log(JSON.stringify(results));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx')],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[False,True,True,True])

    def test_flat_readback_is_linear_and_rejects_wrong_content_and_duplicate_ids(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),path=require('path').win32;
const c={File:p=>({fsName:path.resolve(p)}),LayerKind:{TEXT:'text',NORMAL:'normal'}};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
let reads=0;
const layers=Array.from({length:100},(_,i)=>({
 get name(){reads++;return this.identity},identity:'t'+i,typename:'ArtLayer',kind:'text',
 textItem:{contents:'Text '+i,font:'ArialMT',size:{as:()=>20}}}));
const doc={width:{as:()=>800},height:{as:()=>600},fullName:{fsName:'D:/run/master.psd'},layers};
const job={width:800,height:600,runRoot:'D:/run',outputName:'master.psd',layers:layers.map((l,i)=>({id:'t'+i,kind:'text',text:'Text '+i,font:'ArialMT',size:20}))};
c.psReadback(doc,job);const validReads=reads;
layers[99].textItem.contents='wrong';let contentRejected=false;
try{c.psReadback(doc,job)}catch(e){contentRejected=true}
layers[99].textItem.contents='Text 99';layers[99].identity='t0';let duplicateRejected=false;
try{c.psReadback(doc,job)}catch(e){duplicateRejected=true}
console.log(JSON.stringify({validReads,contentRejected,duplicateRejected}));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx')],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertTrue(data['contentRejected'])
        self.assertTrue(data['duplicateRejected'])
        self.assertLessEqual(data['validReads'],400,data)


if __name__=='__main__':unittest.main()
