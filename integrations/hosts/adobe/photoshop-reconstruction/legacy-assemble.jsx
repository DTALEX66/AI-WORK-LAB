// SPDX-License-Identifier: MIT
// Closed Photoshop native DOM candidate. Separate from the UXP adapter.
#target photoshop

function psFields(v,names){
 if(!v||typeof v!=='object'||v instanceof Array)throw Error('object required');
 var allowed='|'+names.join('|')+'|',k,i;
 for(k in v)if(!v.hasOwnProperty(k)||allowed.indexOf('|'+k+'|')<0)throw Error('unknown field');
 for(i=0;i<names.length;i++)if(!v.hasOwnProperty(names[i]))throw Error('missing field');
}
function psNumber(v,min,max){if(typeof v!=='number'||!isFinite(v)||v<min||v>max)throw Error('invalid number');}
function psVector(v,size,min,max){if(!(v instanceof Array)||v.length!==size)throw Error('invalid vector');for(var i=0;i<size;i++)psNumber(v[i],min,max);}
function psPath(v){
 if(typeof v!=='string')throw Error('path required');var p=v.replace(/\\/g,'/');
 if(!/^[A-Za-z]:\//.test(p)||/[\x00-\x1f<>"|?*]/.test(p)||p.slice(2).indexOf(':')>=0||/(^|\/)\.\.?($|\/)/.test(p)||/[. ]($|\/)/.test(p))throw Error('unsafe native path');
 return File(p).fsName.replace(/\\/g,'/').toLowerCase().replace(/\/+$/,'');
}
function psInside(v,root){var p=psPath(v),r=psPath(root);if(p.indexOf(r+'/')!==0)throw Error('path outside approved root');return File(v);}
function psNew(v,root,ext){var f=psInside(v,root);if(f.exists||!new RegExp('\\.'+ext+'$','i').test(v))throw Error('output exists or wrong type');return f;}
function psValidate(job,root){
 psFields(job,['schemaVersion','jobId','runRoot','width','height','outputName','previewName','assets','layers']);
 if(job.schemaVersion!=='design-lab/photoshop-native-job/v1'||psPath(job.runRoot)!==psPath(root)||!Folder(root).exists)throw Error('unapproved root/schema');
 if(typeof job.jobId!=='string'||!/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(job.jobId))throw Error('invalid job ID');
 psNumber(job.width,1,16383);psNumber(job.height,1,16383);
 if(Math.floor(job.width)!==job.width||Math.floor(job.height)!==job.height)throw Error('integer dimensions required');
 if(typeof job.outputName!=='string'||!/^[A-Za-z][A-Za-z0-9_-]{0,79}\.psd$/i.test(job.outputName)||typeof job.previewName!=='string'||!/^[A-Za-z][A-Za-z0-9_-]{0,79}\.png$/i.test(job.previewName))throw Error('simple output names required');
 psNew(root+'/'+job.outputName,root,'psd');psNew(root+'/'+job.previewName,root,'png');
 var ids={},assets={},count=0,i;
 function id(v){if(typeof v!=='string'||!/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(v)||ids['$'+v])throw Error('duplicate/invalid ID');ids['$'+v]=true;}
 function rectangle(v){psVector(v,4,0,16383);if(!v[2]||!v[3]||v[0]+v[2]>job.width||v[1]+v[3]>job.height)throw Error('rectangle outside canvas');}
 function layers(list,depth){
  if(!(list instanceof Array)||!list.length||list.length>1000||depth>8)throw Error('invalid layer count/depth');
  for(var j=0;j<list.length;j++){
   var n=list[j];if(++count>10000||!n)throw Error('complexity limit');
   if(n.kind==='text'){
    psFields(n,['id','kind','text','font','size','position','color']);
    if(typeof n.text!=='string'||!n.text.length||n.text.length>10000||typeof n.font!=='string'||!n.font.length)throw Error('text/font required');
    app.fonts.getByName(n.font);psNumber(n.size,1,1296);psVector(n.position,2,0,16383);psVector(n.color,3,0,255);
   }else if(n.kind==='raster'){
    psFields(n,['id','kind','assetId','position','width','height']);
    if(typeof n.assetId!=='string'||!assets['$'+n.assetId])throw Error('unknown asset');
    psVector(n.position,2,0,16383);psNumber(n.width,.01,16383);psNumber(n.height,.01,16383);
   }else if(n.kind==='fill'){
    psFields(n,['id','kind','bounds','color']);rectangle(n.bounds);psVector(n.color,3,0,255);
   }else if(n.kind==='group'){
    psFields(n,['id','kind','children','mask']);if(n.mask!==null)rectangle(n.mask);layers(n.children,depth+1);
   }else throw Error('unsupported layer kind');
   id(n.id);
  }
 }
 if(!(job.assets instanceof Array)||job.assets.length>500)throw Error('invalid assets');
 for(i=0;i<job.assets.length;i++){var a=job.assets[i];psFields(a,['id','path']);id(a.id);var f=psInside(a.path,root);if(!f.exists||!/\.(png|jpe?g)$/i.test(a.path))throw Error('missing raster');assets['$'+a.id]=a.path;}
 layers(job.layers,0);
}
function psRGB(v){var c=new SolidColor();c.rgb.red=v[0];c.rgb.green=v[1];c.rgb.blue=v[2];return c;}
function psRect(v){var x=v[0],y=v[1],w=v[2],h=v[3];function point(a,b){return [UnitValue(a,'px'),UnitValue(b,'px')];}return [point(x,y),point(x+w,y),point(x+w,y+h),point(x,y+h)];}
function psBounds(layer){var b=layer.bounds;return [b[0].as('px'),b[1].as('px'),b[2].as('px'),b[3].as('px')];}
function psHasMask(layer){var r=new ActionReference();r.putIdentifier(stringIDToTypeID('layer'),layer.id);var d=executeActionGet(r),k=stringIDToTypeID('hasUserMask');return d.hasKey(k)&&d.getBoolean(k);}
function psApplyMask(doc,layer,bounds){
 doc.activeLayer=layer;doc.selection.select(psRect(bounds));
 var d=new ActionDescriptor(),r=new ActionReference();
 d.putClass(charIDToTypeID('Nw  '),charIDToTypeID('Chnl'));
 r.putEnumerated(charIDToTypeID('Chnl'),charIDToTypeID('Chnl'),charIDToTypeID('Msk '));d.putReference(charIDToTypeID('At  '),r);
 d.putEnumerated(charIDToTypeID('Usng'),charIDToTypeID('UsrM'),charIDToTypeID('RvlS'));
 executeAction(charIDToTypeID('Mk  '),d,DialogModes.NO);doc.selection.deselect();
 if(!psHasMask(layer))throw Error('mask creation failed');
}
function psFind(parent,id){var found=null,count=0;function walk(p){for(var i=0;i<p.layers.length;i++){var l=p.layers[i];if(l.name===id){found=l;count++;}if(l.typename==='LayerSet')walk(l);}}walk(parent);if(count!==1)throw Error('absent/ambiguous layer');return found;}
function psReadback(doc,job){
 if(doc.width.as('px')!==job.width||doc.height.as('px')!==job.height||psPath(doc.fullName.fsName)!==psPath(job.runRoot+'/'+job.outputName))throw Error('document readback mismatch');
 var seen={};
 function check(parent,list){
  if(parent.layers.length!==list.length)throw Error('layer count mismatch');
  var indexed={},j,actual,key;
  for(j=0;j<parent.layers.length;j++){
   actual=parent.layers[j];key='$'+actual.name;
   if(seen[key])throw Error('absent/ambiguous layer');
   seen[key]=true;indexed[key]=actual;
  }
  for(var i=0;i<list.length;i++){
   var n=list[i],l=indexed['$'+n.id];
   if(!l)throw Error('absent/ambiguous layer');
   if(n.kind==='group'){if(l.typename!=='LayerSet'||psHasMask(l)!==(n.mask!==null))throw Error('group/mask mismatch');check(l,n.children);}
   else if(n.kind==='text'){if(l.kind!==LayerKind.TEXT||l.textItem.contents!==n.text||l.textItem.font!==n.font||Math.abs(l.textItem.size.as('pt')-n.size)>.01)throw Error('editable text mismatch');}
   else if(l.kind!==LayerKind.NORMAL)throw Error('independent pixel layer missing');
  }
 }
 check(doc,job.layers);return true;
}
function psSaveNew(doc,path,root){
 var f=psNew(path,root,'psd'),options=new PhotoshopSaveOptions();options.layers=true;options.embedColorProfile=true;options.alphaChannels=true;
 doc.saveAs(f,options,false,Extension.LOWERCASE);if(!f.exists||!f.length)throw Error('PSD absent');
 doc.close(SaveOptions.DONOTSAVECHANGES);doc=app.open(f);if(psPath(doc.fullName.fsName)!==psPath(path))throw Error('reopen mismatch');return doc;
}
function psExportPNG(doc,path,root){var f=psNew(path,root,'png');doc.saveAs(f,new PNGSaveOptions(),true,Extension.LOWERCASE);if(!f.exists||!f.length)throw Error('PNG absent');}
function psRejectOpenInputs(job){
 for(var i=0;i<app.documents.length;i++){
  var path=null;try{path=app.documents[i].fullName.fsName;}catch(e){} // New unsaved docs have no file identity.
  if(path!==null)for(var j=0;j<job.assets.length;j++)if(psPath(path)===psPath(job.assets[j].path))throw Error('input already open');
 }
}
function psRunJob(job,root,observe){
 function stage(name){if(observe)observe(name);}
 psValidate(job,root);psRejectOpenInputs(job);
 stage('validated');stage('build-start');
 var doc=app.documents.add(UnitValue(job.width,'px'),UnitValue(job.height,'px'),72,job.jobId,NewDocumentMode.RGB,DocumentFill.TRANSPARENT),blank=doc.activeLayer,assets={};
 for(var i=0;i<job.assets.length;i++)assets['$'+job.assets[i].id]=job.assets[i].path;
 function build(parent,n){
  var l;
  if(n.kind==='group'){l=parent.layerSets.add();l.name=n.id;for(var j=0;j<n.children.length;j++)build(l,n.children[j]);if(n.mask!==null)psApplyMask(doc,l,n.mask);}
  else if(n.kind==='raster'){
   var source=null;
   try{source=app.open(File(assets['$'+n.assetId]));var b=psBounds(source.activeLayer),sx=n.width/source.width.as('px'),sy=n.height/source.height.as('px');l=source.activeLayer.duplicate(doc,ElementPlacement.PLACEATBEGINNING);}
   finally{if(source)source.close(SaveOptions.DONOTSAVECHANGES);}
   app.activeDocument=doc;l.name=n.id;l.resize(sx*100,sy*100,AnchorPosition.TOPLEFT);var actual=psBounds(l);l.translate(UnitValue(n.position[0]+b[0]*sx-actual[0],'px'),UnitValue(n.position[1]+b[1]*sy-actual[1],'px'));
   if(parent!==doc)l.move(parent,ElementPlacement.INSIDE);
  }else{
   l=parent.artLayers.add();l.name=n.id;
   if(n.kind==='text'){l.kind=LayerKind.TEXT;l.textItem.contents=n.text;l.textItem.font=n.font;l.textItem.size=UnitValue(n.size,'pt');l.textItem.position=[UnitValue(n.position[0],'px'),UnitValue(n.position[1],'px')];l.textItem.color=psRGB(n.color);}
   else{doc.activeLayer=l;doc.selection.select(psRect(n.bounds));doc.selection.fill(psRGB(n.color));doc.selection.deselect();}
  }
  return l;
 }
 for(i=0;i<job.layers.length;i++)build(doc,job.layers[i]);blank.remove();
 stage('build-end');stage('save-reopen-start');
 doc=psSaveNew(doc,root+'/'+job.outputName,root);stage('save-reopen-end');
 psReadback(doc,job);stage('readback-end');stage('export-start');
 psExportPNG(doc,root+'/'+job.previewName,root);stage('export-end');stage('final-reopen-start');
 doc.close(SaveOptions.DONOTSAVECHANGES);doc=app.open(File(root+'/'+job.outputName));psReadback(doc,job);stage('final-readback-end');return doc;
}
function psRunPatchJob(job,baseline,expected,root,observe){
 function stage(name){if(observe)observe(name);}
 psValidate(baseline,root);psValidate(expected,root);psRejectOpenInputs(baseline);
 var checkpoint=psInside(job.checkpoint,root),i;
 if(!checkpoint.exists||!/\.psd$/i.test(job.checkpoint))throw Error('missing PSD checkpoint');
 for(i=0;i<app.documents.length;i++){
  var openPath=null;try{openPath=app.documents[i].fullName.fsName;}catch(e){}
  if(openPath!==null&&psPath(openPath)===psPath(job.checkpoint))throw Error('checkpoint already open');
 }
 stage('validated');
 var readJob={},key;for(key in baseline)if(baseline.hasOwnProperty(key))readJob[key]=baseline[key];
 readJob.outputName=job.checkpoint.replace(/\\/g,'/').split('/').pop();
 var doc=app.open(checkpoint);psReadback(doc,readJob);
 stage('save-reopen-start');
 doc=psPatch(doc,job.checkpoint,job.patch,root+'/'+expected.outputName,root);stage('save-reopen-end');
 psReadback(doc,expected);stage('readback-end');stage('export-start');
 psExportPNG(doc,root+'/'+expected.previewName,root);stage('export-end');stage('final-reopen-start');
 doc.close(SaveOptions.DONOTSAVECHANGES);doc=app.open(File(root+'/'+expected.outputName));
 psReadback(doc,expected);stage('final-readback-end');return doc;
}
function psPatch(doc,expected,patch,output,root){
 if(!doc.saved||psPath(doc.fullName.fsName)!==psPath(expected))throw Error('wrong/dirty document');
 psInside(expected,root);psNew(output,root,'psd');
 var before,l;
 if(patch.kind==='text'){psFields(patch,['kind','id','text']);if(typeof patch.text!=='string'||!patch.text.length||patch.text.length>10000)throw Error('invalid text patch');l=psFind(doc,patch.id);if(l.kind!==LayerKind.TEXT)throw Error('not text');l.textItem.contents=patch.text;}
 else if(patch.kind==='move'){psFields(patch,['kind','id','delta']);psVector(patch.delta,2,-16383,16383);l=psFind(doc,patch.id);if(l.typename==='LayerSet')throw Error('move one leaf only');before=psBounds(l);l.translate(UnitValue(patch.delta[0],'px'),UnitValue(patch.delta[1],'px'));}
 else throw Error('unsupported patch');
 doc=psSaveNew(doc,output,root);l=psFind(doc,patch.id);
 if(patch.kind==='text'){if(l.textItem.contents!==patch.text)throw Error('text patch readback mismatch');}
 else{var b=psBounds(l);for(var i=0;i<4;i++)if(Math.abs(b[i]-before[i]-patch.delta[i%2])>.1)throw Error('move patch readback mismatch');}
 return doc;
}
