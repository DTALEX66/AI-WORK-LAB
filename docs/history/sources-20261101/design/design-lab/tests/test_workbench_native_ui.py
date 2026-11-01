# SPDX-License-Identifier: MIT
"""Execute the actual workbench script with a narrow DOM/fetch boundary."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


class WorkbenchNativeUiTests(unittest.TestCase):
    def test_pagination_keeps_both_pages_and_stops_at_end(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},calls=[];
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},fetch:async path=>{
calls.push(path);const label=path.includes('?after=next')?'second':'first';
return {ok:true,json:async()=>({tasks:[{kind:label,job_id:label,state:'PENDING',attempt:{attempt_no:1,state:'PENDING'}}],
assets:[{id:label,kind:'psd',version_no:1,version_id:label}],next_cursor:label==='first'?'next':null})};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{const fn=process.argv[2];vm.runInContext("project='p'",c);
await vm.runInContext(fn+'()',c);await vm.runInContext(fn+'(true)',c);await vm.runInContext(fn+'(true)',c);
const id=fn==='tasks'?'tasks':'native-assets';
console.log(JSON.stringify({calls,labels:elements[id].children.map(li=>li.children[0].textContent)}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        for function,route in (('tasks','tasks'),('nativeAssets','native-assets')):
            with self.subTest(function=function):
                result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js'),function],capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                data=json.loads(result.stdout)
                self.assertEqual(data['calls'],['/api/projects/p/'+route,'/api/projects/p/'+route+'?after=next'])
                self.assertEqual(len(data['labels']),2)
                self.assertIn('first',data['labels'][0]);self.assertIn('second',data['labels'][1])

    def test_refresh_invalidates_pagination_and_current_errors_remain_visible(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},pending=[];
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},fetch:path=>new Promise(resolve=>pending.push({path,resolve}))};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{const fn=process.argv[2];vm.runInContext("project='p';taskCursor=nativeCursor='old-page'",c);
const base=vm.runInContext(fn+'()',c).catch(e=>e.message);
const append=vm.runInContext(fn+'(true)',c).catch(e=>e.message);
const count=pending.length;
for(const p of pending)p.resolve({ok:false,json:async()=>({error:'CURRENT_ERROR'})});
const error=await base;await append;
console.log(JSON.stringify({count,error}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        for function in ('tasks','nativeAssets'):
            with self.subTest(function=function):
                result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js'),function],capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout),{'count':1,'error':'CURRENT_ERROR'})

    def test_list_responses_and_errors_cannot_overwrite_newer_refresh(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},pending=[];
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E(),createTextNode:()=>({nodeType:3})},
fetch:path=>new Promise(resolve=>pending.push({path,resolve}))};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{const fn=process.argv[2],mode=process.argv[3];vm.runInContext("project='"+'c'.repeat(32)+"';taskCursor=nativeCursor='page1'",c);
const first=vm.runInContext(fn+'('+(mode==='append'?'true':'')+')',c).catch(e=>e.message);
const offset=pending.length;const second=vm.runInContext(fn+'()',c);
const response=(path,label)=>({ok:true,json:async()=>path.endsWith('/tasks')||path.includes('/tasks?')?
{tasks:[{kind:label,job_id:label,state:'PENDING',attempt:{attempt_no:1,state:'PENDING'}}],next_cursor:label}:
{assets:[{id:label,kind:'psd',version_no:1,version_id:label,width:1,height:1,media_type:'image/png'}],next_cursor:label}});
for(const p of pending.slice(offset))p.resolve(response(p.path,'recent'));await second;
for(const p of pending.slice(0,offset))p.resolve(mode==='error'?{ok:false,json:async()=>({error:'STALE_ERROR'})}:response(p.path,'old'));
const error=await first;
const id=fn==='tasks'?'tasks':fn==='nativeAssets'?'native-assets':'assets';
console.log(JSON.stringify({error:error||null,labels:elements[id].children.map(li=>li.children[0].textContent),cursor:vm.runInContext(fn==='nativeAssets'?'nativeCursor':'taskCursor',c)}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        for function in ('tasks','nativeAssets','refresh'):
            for mode in ('success','error','append'):
                if function=='refresh' and mode=='append':continue
                with self.subTest(function=function,mode=mode):
                    result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js'),function,mode],capture_output=True,text=True,encoding='utf-8',timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    data=json.loads(result.stdout)
                    self.assertIsNone(data['error'])
                    self.assertEqual(len(data['labels']),1)
                    self.assertIn('recent',data['labels'][0])
                    self.assertNotIn('old',data['labels'][0])
                    self.assertEqual(data['cursor'],'recent')

    def test_photoshop_patch_form_binds_source_and_reuses_key_without_dispatch(self):
        self.test_patch_form_binds_source_and_reuses_key_without_dispatch('photoshop-native')

    def test_patch_form_binds_source_and_reuses_key_without_dispatch(self,host='illustrator-native'):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},calls=[],owner='c'.repeat(32);let keys=0;
const task={kind:process.argv[2],job_id:'native-job-'+'a'.repeat(64),state:'SUCCEEDED',attempt:{attempt_id:'att-'+'b'.repeat(32),attempt_no:1,state:'RECEIPTED'}};
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},crypto:{randomUUID:()=>String(++keys)},
fetch:async(path,options)=>{calls.push({path,body:options.body});return {ok:true,json:async()=>path.endsWith('/patch')?{task:{attempt:{state:'PENDING'}},parent:{version_id:'v-test'}}:{tasks:[task],next_cursor:null}};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{await vm.runInContext("project='"+owner+"';tasks()",c);
const b=elements.tasks.children.map(li=>li.children[0]).find(b=>b.textContent.startsWith('修改对象'));
if(b)await b.onclick();c.document.getElementById('patch-json').value=JSON.stringify({kind:'text',id:'title',text:'After'});
if(elements['patch-form']?.onsubmit){await elements['patch-form'].onsubmit({preventDefault(){}});await elements['patch-form'].onsubmit({preventDefault(){}});}
console.log(JSON.stringify({found:!!b,calls,status:elements.status?.textContent}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js'),host],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);self.assertTrue(data['found'])
        calls=[c for c in data['calls'] if c['path'].endswith('/patch')]
        self.assertEqual(len(calls),2)
        body=json.loads(calls[0]['body']);self.assertEqual(body,json.loads(calls[1]['body']))
        self.assertEqual(body['source_attempt_id'],'att-'+'b'*32)
        self.assertEqual(body['patch'],{'kind':'text','id':'title','text':'After'})
        self.assertFalse(any(c['path'].endswith('/run') for c in data['calls']))
        self.assertIn('PENDING',data['status'])

    def test_plan_submission_reuses_key_without_starting_host(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},calls=[];let keys=0;
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},crypto:{randomUUID:()=>String(++keys)},
fetch:async(path,options)=>{calls.push({path,body:options.body});return {ok:true,json:async()=>path.endsWith('/native-plans')?{task:{attempt:{state:'PENDING'}}}:{tasks:[],next_cursor:null}};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{vm.runInContext("project='"+'c'.repeat(32)+"'",c);
c.document.getElementById('plan-host').value='photoshop';c.document.getElementById('plan-rir').value='{"layers":[]}';c.document.getElementById('plan-styles').value='{}';
if(elements['plan-form']?.onsubmit){await elements['plan-form'].onsubmit({preventDefault(){}});await elements['plan-form'].onsubmit({preventDefault(){}});}
console.log(JSON.stringify({calls,status:elements.status?.textContent}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);calls=[c for c in data['calls'] if c['path'].endswith('/native-plans')]
        self.assertEqual(len(calls),2)
        self.assertEqual(json.loads(calls[0]['body']),json.loads(calls[1]['body']))
        self.assertFalse(any(c['path'].endswith('/run') for c in data['calls']))
        self.assertIn('PENDING',data['status'])

    def test_start_queued_task_sends_bound_attempt(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},calls=[],owner='c'.repeat(32);
const task={kind:'photoshop-native',job_id:'native-job-'+'a'.repeat(64),state:'PENDING',attempt:{attempt_id:'att-'+'b'.repeat(32),attempt_no:1,state:'PENDING'}};
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
fetch:async(path,options)=>{calls.push({path,body:options.body});return {ok:true,json:async()=>path.endsWith('/run')?{task,worker:'STARTED'}:{tasks:[task],next_cursor:null}};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{await vm.runInContext("project='"+owner+"';tasks()",c);
const b=elements.tasks.children.map(li=>li.children[0]).find(b=>b.textContent.startsWith('启动任务'));
if(b)await b.onclick();console.log(JSON.stringify({found:!!b,calls,status:elements.status?.textContent}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);self.assertTrue(data['found'])
        calls=[c for c in data['calls'] if c['path'].endswith('/run')]
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads(calls[0]['body']),{'attempt_id':'att-'+'b'*32})
        self.assertIn('不代表制作成功',data['status'])

    def test_cancel_button_binds_attempt_and_reads_back_requested_state(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},calls=[],owner='c'.repeat(32);
const task={kind:'photoshop-native',job_id:'native-job-'+'a'.repeat(64),state:'DISPATCHING',attempt:{attempt_id:'att-'+'b'.repeat(32),attempt_no:1,state:'RUNNING'}};
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
fetch:async(path,options)=>{calls.push({path,body:options.body});let data;
if(path.endsWith('/cancel')){task.attempt.state='CANCEL_REQUESTED';task.state='CANCEL_REQUESTED';data={task};}
else if(path.endsWith('/tasks'))data={tasks:[task],next_cursor:null};
else throw Error('unexpected request');return {ok:true,json:async()=>data};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{await vm.runInContext("project='"+owner+"';tasks()",c);
const b=elements.tasks.children.map(li=>li.children[0]).find(b=>b.textContent.startsWith('请求取消'));
if(b)await b.onclick();
console.log(JSON.stringify({found:!!b,calls,status:elements.status?.textContent,labels:elements.tasks.children.map(li=>li.children[0].textContent)}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertTrue(data['found'])
        requests=[c for c in data['calls'] if c['path'].endswith('/cancel')]
        self.assertEqual(len(requests),1)
        self.assertEqual(json.loads(requests[0]['body']),{'attempt_id':'att-'+'b'*32})
        self.assertIn('CANCEL_REQUESTED',data['status'])
        self.assertIn('不代表宿主已停止',data['status'])
        self.assertFalse(any(s.startswith('请求取消') for s in data['labels']))

    def test_late_asset_preview_and_verification_cannot_replace_latest_selection(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.classList={toggle(){}};}removeAttribute(){}replaceChildren(){}append(){}}
const elements={},pending=[];
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
fetch:path=>new Promise(resolve=>pending.push(resolve))};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{const fn=process.argv[2];vm.runInContext("project='"+'c'.repeat(32)+"'",c);
const old=vm.runInContext(fn+"({id:'old'})",c),recent=vm.runInContext(fn+"({id:'recent'})",c);
const response=label=>({ok:true,json:async()=>({content_base64:label,asset:{kind:'psd',media_type:'image/png',version_id:label,verification:label,width:1,height:1,sha256:label}})});
pending[1](response('recent'));await recent;pending[0](response('old'));await old;
console.log(JSON.stringify({result:elements[fn==='preview'?'asset-info':'native-info'].textContent}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        for function in ('preview','verifyNative'):
            with self.subTest(function=function):
                result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js'),function],capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                text=json.loads(result.stdout)['result']
                self.assertIn('recent',text)
                self.assertNotIn('old',text)

    def test_late_task_events_cannot_replace_new_selection(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class E {constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={},pending=[];
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
fetch:path=>new Promise(resolve=>pending.push({path,resolve}))};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{vm.runInContext("project='"+'c'.repeat(32)+"'",c);
const old=vm.runInContext("loadEvents('old')",c),recent=vm.runInContext("loadEvents('recent')",c);
const response=label=>({ok:true,json:async()=>({events:[{at:label,attempt_no:1,to_state:'RECEIPTED'}],next_cursor:null})});
pending[1].resolve(response('recent'));await recent;pending[0].resolve(response('old'));await old;
console.log(JSON.stringify({job:vm.runInContext('eventJob',c),text:elements.events.children.map(e=>e.textContent)}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['job'],'recent')
        self.assertEqual(data['text'],['recent · attempt 1 · NEW → RECEIPTED'])

    def test_bundle_download_checks_hash_before_saving(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
let saved=0,tamper=false;const bytes=Buffer.from('controlled archive');
const hash=crypto.createHash('sha256').update(bytes).digest('hex');
class E {constructor(){this.classList={toggle(){}};}click(){saved++;}removeAttribute(){}replaceChildren(){}append(){}}
const elements={},owner='c'.repeat(32),route='/api/projects/'+owner+'/bundles/bundle-native-'+'b'.repeat(64)+'/versions/v-'+'d'.repeat(32)+'/content';
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
crypto:crypto.webcrypto,Blob,Uint8Array,URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}},setTimeout:fn=>fn(),
fetch:async path=>path.endsWith('/bundle')?{ok:true,json:async()=>({bundle:{sha256:hash,byte_size:bytes.length},download_path:route})}:
{ok:true,arrayBuffer:async()=>Uint8Array.from(tamper?Buffer.from('bad'):bytes).buffer}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{await vm.runInContext("project='"+owner+"';exportBundle({job_id:'native-job-"+'a'.repeat(64)+"'})",c);
tamper=true;let rejected=false;try{await vm.runInContext("exportBundle({job_id:'native-job-"+'a'.repeat(64)+"'})",c)}catch(e){rejected=true;}
console.log(JSON.stringify({saved,rejected}));})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'saved':1,'rejected':True})

    def test_native_listing_and_explicit_verification_use_scoped_api(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class Element {constructor(){this.children=[];this.textContent='';this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(...xs){this.children=xs;}removeAttribute(){}}
const elements={},calls=[],asset={id:'native-'+ 'a'.repeat(64),kind:'psd',version_id:'v-native',version_no:1,byte_size:123,sha256:'sha256:'+ 'b'.repeat(64),rights:'NOT_REVIEWED',verification:'METADATA_ONLY'};
const c={document:{getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element()},
 fetch:async route=>{calls.push(route);let data;
 if(route.endsWith('/native-assets'))data={assets:[asset],next_cursor:null};
 else if(route.endsWith('/verify'))data={asset:{...asset,verification:'HASH_VERIFIED'}};
 else if(route.endsWith('/tasks'))data={tasks:[],next_cursor:null};
 else if(route.endsWith('/assets'))data={assets:[]};
 else throw Error('unexpected request');
 return {ok:true,json:async()=>data};}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{await vm.runInContext("project='"+'c'.repeat(32)+"';refresh()",c);
 const list=elements['native-assets'];const labels=list?list.children.map(li=>li.children[0].textContent):[];
 if(list?.children[0])await list.children[0].children[0].onclick();
 console.log(JSON.stringify({labels,calls,info:elements['native-info']?.textContent||''}));})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(len(data['labels']),1,'native assets are not rendered')
        self.assertIn('PSD',data['labels'][0]);self.assertIn('HASH_VERIFIED',data['info'])
        prefix='/api/projects/'+'c'*32
        self.assertIn(prefix+'/native-assets',data['calls'])
        self.assertIn(prefix+'/native-assets/native-'+'a'*64+'/verify',data['calls'])

    def test_revision_entry_prefills_from_row_and_revision_errors_fail_closed(self):
        # F-2b: the row's「新版本」entry must prefill the revision form from the
        # persisted version it was opened on, the POST must go to the revision
        # route with that content, and a rejected revision (409 STALE_REVISION /
        # 401 UNAUTHORIZED) must surface on the shared error line instead of
        # silently doing nothing.
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class El{constructor(){this.children=[];this.textContent='';this.value='';this.hidden=false;this.disabled=false;const s=new Set();
this.classList={add:c=>s.add(c),remove:c=>s.delete(c),toggle:(c,on)=>{const want=on===undefined?!s.has(c):on;want?s.add(c):s.delete(c)},contains:c=>s.has(c)};}
append(...xs){for(const x of xs)this.children.push(x)}replaceChildren(...xs){this.children=xs}removeAttribute(){}focus(){}}
class Option{constructor(text,value){this.text=text;this.value=value}}
const elements={},calls=[],owner='c'.repeat(32),briefId='brief-'+'a'.repeat(32);
let keys=0,mode='stale';
const brief={brief_id:briefId,title:'E2E Autumn',goals:['modern','warm'],constraints:null,
reference_asset_ids:['asset-'+'d'.repeat(64)],spec_sha256:'sha256:'+'b'.repeat(64),version:1,superseded_by:null,created_at:'2026-01-01T00:00:00+00:00'};
const layer={design_layer:{briefs:[brief],directions:[],chosen_direction:null,bindings:[],active_binding:null,design_systems:[]}};
const c={document:{getElementById:id=>elements[id]??=new El(),createElement:()=>new El(),createTextNode:()=>({nodeType:3}),querySelectorAll:()=>[]},
crypto:{randomUUID:()=>String(++keys)},Option,
fetch:async(path,options)=>{calls.push({path,body:options&&options.body});
if(path.endsWith('/design-layer'))return{ok:true,json:async()=>layer};
if(path.endsWith('/revisions'))return mode==='stale'?{ok:false,json:async()=>({error:'STALE_REVISION'})}:{ok:false,json:async()=>({error:'UNAUTHORIZED'})};
throw Error('unexpected request '+path)}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{vm.runInContext("project='"+owner+"'",c);
await vm.runInContext('refreshDesign()',c);
const row=elements['design-briefs'].children[0];
const entry=row.children.find(b=>b.textContent==='新版本');
if(entry)await entry.onclick();
// The submit handler returns void (the action is fire-and-forget by design), so
// flush the microtask queue until the handled chain has settled before reading.
const flush=async()=>{for(let i=0;i<200;i++)await null;};
const prefilled={title:elements['revision-brief-title'].value,goals:elements['revision-brief-goals'].value,target:elements['revision-brief-target'].textContent};
if(elements['brief-revision-form'].onsubmit)await elements['brief-revision-form'].onsubmit({preventDefault(){}});
await flush();
const stale={status:elements.status.textContent,error:elements.status.classList.contains('error'),rows:elements['design-briefs'].children.length};
mode='unauthorized';
if(elements['brief-revision-form'].onsubmit)await elements['brief-revision-form'].onsubmit({preventDefault(){}});
await flush();
const unauthorized={status:elements.status.textContent,error:elements.status.classList.contains('error')};
console.log(JSON.stringify({rowText:row.textContent,buttons:row.children.map(b=>b.textContent),prefilled,stale,unauthorized,
posts:calls.filter(x=>x.path.endsWith('/revisions'))}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['buttons'],['新版本','版本链'],'row revision entries missing')
        self.assertIn('v1 · 当前',data['rowText'])
        self.assertEqual(data['prefilled']['title'],'E2E Autumn')
        self.assertEqual(data['prefilled']['goals'],'modern, warm')
        self.assertIn('版本 1',data['prefilled']['target'])
        self.assertIn('另有 1 个参考素材',data['prefilled']['target'])
        self.assertEqual(len(data['posts']),2)
        route='/api/projects/'+'c'*32+'/briefs/brief-'+'a'*32+'/revisions'
        for post in data['posts']:
            self.assertEqual(post['path'],route)
            body=json.loads(post['body'])
            self.assertEqual(body['title'],'E2E Autumn')
            self.assertEqual(body['goals'],['modern','warm'])
            self.assertEqual(body['reference_asset_ids'],['asset-'+'d'*64])
            self.assertTrue(body['idempotency_key'])
        self.assertIn('STALE_REVISION',data['stale']['status'])
        self.assertIn('已被取代',data['stale']['status'])
        self.assertTrue(data['stale']['error'],'rejected revision must render as an error')
        self.assertEqual(data['stale']['rows'],1,'a rejected revision must not append a row')
        self.assertIn('UNAUTHORIZED',data['unauthorized']['status'])
        self.assertTrue(data['unauthorized']['error'])

    def test_revised_chosen_direction_reports_binding_needs_rebuild(self):
        # F-2b: after the CHOSEN direction is revised the append-only binding is
        # left on the retired version, so active_binding is null. The UI must say
        # 「绑定需重新建立」and must never render that retired binding as current.
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm');
class El{constructor(){this.children=[];this.textContent='';this.value='';this.hidden=false;this.disabled=false;const s=new Set();
this.classList={add:c=>s.add(c),remove:c=>s.delete(c),toggle:(c,on)=>{const want=on===undefined?!s.has(c):on;want?s.add(c):s.delete(c)},contains:c=>s.has(c)};}
append(...xs){for(const x of xs)this.children.push(x)}replaceChildren(...xs){this.children=xs}removeAttribute(){}focus(){}}
class Option{constructor(text,value){this.text=text;this.value=value}}
const elements={},calls=[],owner='c'.repeat(32),retired='direction-'+'a'.repeat(32),live='direction-'+'b'.repeat(32);
const base={brief_id:'brief-'+'c'.repeat(32),style_notes:null,color_mood:'warm',typography_mood:null,created_at:'2026-01-01T00:00:00+00:00'};
const v1={...base,direction_id:retired,title:'Warm Gradient',chosen:false,actor:null,actor_kind:null,spec_sha256:'sha256:'+'1'.repeat(64),version:1,superseded_by:live};
const v2={...base,direction_id:live,title:'Warm Gradient II',chosen:true,actor:'workbench-user',actor_kind:'human',spec_sha256:'sha256:'+'2'.repeat(64),version:2,superseded_by:null};
const binding={binding_id:'binding-'+'e'.repeat(32),direction_id:retired,design_system_name:'anomaly-monitor-dark',spec_sha256:'sha256:'+'f'.repeat(64),version:1,superseded_by:null,created_at:'2026-01-01T00:00:00+00:00'};
const layer={design_layer:{briefs:[],directions:[v1,v2],chosen_direction:v2,bindings:[binding],active_binding:null,design_systems:[]}};
const c={document:{getElementById:id=>elements[id]??=new El(),createElement:()=>new El(),createTextNode:()=>({nodeType:3}),querySelectorAll:()=>[]},
crypto:{randomUUID:()=>'k'},Option,
fetch:async path=>{calls.push(path);if(path.endsWith('/design-layer'))return{ok:true,json:async()=>layer};throw Error('unexpected request '+path)}};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
(async()=>{vm.runInContext("project='"+owner+"'",c);
await vm.runInContext('refreshDesign()',c);
console.log(JSON.stringify({active:elements['design-binding-active'].textContent,
warn:elements['design-binding-active'].classList.contains('warn'),
binding:elements['design-bindings'].children[0].textContent,
rows:elements['design-directions'].children.map(r=>({text:r.textContent,buttons:r.children.map(b=>b.textContent)}))}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertIn('绑定需重新建立',data['active'])
        self.assertNotIn('已绑定设计系统',data['active'])
        self.assertTrue(data['warn'],'the rebuild notice must be visually marked')
        self.assertIn('未生效',data['binding'])
        self.assertNotIn('生效中',data['binding'])
        self.assertIn('绑定留在已被取代的方向版本上',data['binding'])
        self.assertEqual(len(data['rows']),2)
        retired_row,live_row=min(data['rows'],key=lambda r:'CHOSEN by' in r['text']),max(data['rows'],key=lambda r:'CHOSEN by' in r['text'])
        self.assertIn('已取代 → 版本 2',retired_row['text'])
        self.assertNotIn('CHOSEN by',retired_row['text'])
        self.assertFalse([b for b in retired_row['buttons'] if b.startswith('选为方向')],
                         'a superseded version must not offer the choose entry')
        self.assertIn('CHOSEN by workbench-user',live_row['text'])
        self.assertIn('当前',live_row['text'])
        self.assertTrue([b for b in live_row['buttons'] if b.startswith('选为方向')])


    def test_default_composed_plan_receipt_and_key_are_contract_shaped(self):
        """Batch 22 / D02 + D01 + D04: the parts of the plan screen a contract can pin.

        * D02 — ``composeTargetPlan`` used to set ``locked: host === 'illustrator'``.
          The lowering contract refuses a locked node without an explicit fallback, so
          the Illustrator default plan was refused before a job existed.
        * D01 — the idempotency key must be bound to the intent, so the same composed
          plan always yields the same key and a different plan a different one.
        * D04 — the 202 puts the task under ``task``; the receipt reader must read that
          nesting, not top-level fields that the route never sends.
        """
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script=r'''
const fs=require('fs'),vm=require('vm'),nc=require('crypto');
class E{constructor(){this.children=[];this.classList={toggle(){}};}append(x){this.children.push(x)}replaceChildren(){this.children=[];}removeAttribute(){}}
const elements={};
const c={document:{getElementById:id=>elements[id]??=new E(),createElement:()=>new E()},
crypto:{subtle:{digest:async(alg,bytes)=>nc.createHash('sha256').update(Buffer.from(bytes)).digest()}},
TextEncoder,Buffer,console,fetch:async()=>({ok:true,json:async()=>({})})};
// D06 gave `api()` a deadline (AbortController + setTimeout). Each sandbox here is a browser
// boundary for the real bundle, so the Abort classes are supplied for the same reason crypto
// and TextEncoder were: without them `api()` threw before reaching the fetch mock and these
// tests measured nothing. The clock is deliberately NOT the real one. A timer that actually
// fires would (a) let the deadline abort a request mid-assertion and (b) keep node's event
// loop alive for up to 45s per call, which is how this fix first turned one test into a
// 30s subprocess timeout -- the sandbox's own synchronous `setTimeout:fn=>fn()` stub was what
// kept that hidden until now. Deadlines are proved in the appshell suite's timed block.
const noTimer=()=>0;
Object.assign(c,{AbortController,AbortSignal,setTimeout:noTimer,clearTimeout:()=>{}});vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
// The bundle's top-level declarations live on the vm context, not in this outer
// script: every call has to be evaluated inside the context, the way the other
// contract tests in this file already do.
vm.runInContext(`
(async()=>{
const asset={id:'img-'+'a'.repeat(64),media_type:'image/png',width:8,height:6,rights:'NOT_REVIEWED',
version_id:'v-'+'b'.repeat(32)};
const job='native-job-'+'c'.repeat(64);
const ps=composeTargetPlan(asset,'photoshop'),ai=composeTargetPlan(asset,'illustrator');
const plan=JSON.stringify(ps.rir);
const k1=await contentKey(['p','photoshop',plan,'{}']);
const k2=await contentKey(['p','photoshop',plan,'{}']);
const k3=await contentKey(['p','illustrator',plan,'{}']);
globalThis.__out=JSON.stringify({
locked:[ps.rir.layers[0].locked,ai.rir.layers[0].locked],
keys:[k1,k2,k3],
receipts:[readPlanReceipt({task:{job_id:job,state:'PENDING'}}),readPlanReceipt({}),readPlanReceipt(null)],
bytes:[await sha256Hex(new TextEncoder().encode('x'))]});
})()`,c).then(()=>console.log(c.__out)).catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run([node,'-e',script,str(ROOT/'apps/workbench/build/main.js')],
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['locked'],[False,False],
            'both hosts must compose an unlocked layer; the lowering contract refuses locked ones')
        first,second,other=data['keys']
        self.assertEqual(first,second,'the same intent must produce the same idempotency key')
        self.assertNotEqual(first,other,'a different host must produce a different key')
        for key in data['keys']:
            self.assertRegex(key,r'^[0-9a-f]{64}$',
                'the service accepts [A-Za-z0-9_-]{1,64}; a 64-char hex digest fits')
        queued,empty,nothing=data['receipts']
        self.assertEqual(queued,{'id':'native-job-'+'c'*64,'state':'PENDING'})
        self.assertEqual(empty['id'],'未给出任务号')
        self.assertEqual(nothing['id'],'未给出任务号')
        self.assertEqual(data['bytes'],[__import__('hashlib').sha256(b'x').hexdigest()])


if __name__ == '__main__':
    unittest.main()
