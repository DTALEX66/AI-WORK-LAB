# SPDX-License-Identifier: MIT
"""The real JSX reader must reject misplaced live text, not only wrong content."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


class TextReadbackTests(unittest.TestCase):
    def test_position_drift_is_rejected_with_correct_text_and_font(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required for JSX reader')
        script=r'''
const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
const spec={kind:'text',id:'title',text:'Editable',font:'ArialMT',size:24,position:[40,330],color:[0,0,0]};
const actual={contents:'Editable',position:[40,330],textRange:{characterAttributes:{textFont:{name:'ArialMT'},size:24}}};
const layer={textFrames:{getByName:()=>actual}};
const doc={layers:{length:1,getByName:()=>layer},artboards:[{artboardRect:[0,400,600,0]}],
 textFrames:{length:1},pathItems:{length:0},rasterItems:{length:0},placedItems:{length:0}};
const job={artboard:{height:400,width:600},layers:[{id:'layer0',items:[spec]}]};
const results=[];
for(const pos of [[40,330],[41,330],[40,329],[NaN,330],[40,undefined]]){
 actual.position=pos;let rejected=false;try{c.readbackJob(doc,job);}catch(e){rejected=true;}
 results.push(rejected);
}
console.log(JSON.stringify(results));
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx')],
            capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[False,True,True,True,True])


if __name__=='__main__':unittest.main()
