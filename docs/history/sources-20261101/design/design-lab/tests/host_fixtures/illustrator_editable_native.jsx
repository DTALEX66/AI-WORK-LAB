// SPDX-License-Identifier: MIT
// Synthetic qualification of the actual product bridge. Not human acceptance.
#target illustrator
(function () {
    var root = 'D:/All projects/DESIGN-LAB/.project-local/task-artifacts/illustrator-editable-20260908';
    if (!Folder(root).exists && !Folder(root).create()) throw new Error('Cannot create owned fixture root');
    var product = File('D:/All projects/DESIGN-LAB/integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx');
    var session = Folder(root + '/run-' + new Date().getTime());
    if (session.exists || !session.create()) throw new Error('Exclusive session required');
    var before = app.documents.length, d = null, status = 'FAIL', message = '', count = -1, stages = 0;
    var original = before ? app.activeDocument : null;
    function check(test, why) { if (!test) throw new Error(why); }
    function stageEvidence(name, doc) {
        var snapshot=File(session.fsName+'/'+name+'.tsv');snapshot.encoding='UTF-8';
        check(!snapshot.exists && snapshot.open('w'),'exclusive snapshot required');
        snapshot.write('native\t'+doc.fullName.fsName+'\ntext\t'+doc.textFrames.getByName('title').contents+
            '\ncurveRight\t'+doc.pathItems.getByName('curve').pathPoints[0].rightDirection+
            '\ntextCount\t'+doc.textFrames.length+'\npathCount\t'+doc.pathItems.length+
            '\nrasterCount\t'+doc.rasterItems.length+'\nclipped\t'+doc.groupItems.getByName('masked-image').clipped+
            '\nmaskBounds\t'+doc.pathItems.getByName('image-clip').geometricBounds+'\n');snapshot.close();
        var nativeCheckpoint=File(doc.fullName.fsName),preview=File(session.fsName+'/'+name+'.png');
        check(!preview.exists,'exclusive preview required');
        var po=new ExportOptionsPNG24();po.artBoardClipping=true;po.transparency=true;
        po.antiAliasing=true;po.horizontalScale=100;po.verticalScale=100;
        doc.exportFile(preview,ExportType.PNG24,po);check(preview.exists && preview.length,'preview absent');
        doc.close(SaveOptions.DONOTSAVECHANGES);
        return app.open(nativeCheckpoint);
    }
    try {
        $.evalFile(product);
        var source = File('D:/All projects/DESIGN-LAB/.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/fixture.png');
        check(source.copy(session.fsName + '/input.png'), 'fixture copy failed');
        var job = {
            schemaVersion:'design-lab/adobe-host-job/v1',jobId:'native-fixture',
            rirHash:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            runRoot:session.fsName,artboard:{width:800,height:600},
            authorization:{required:true,scope:'single-session'},
            operations:REQUIRED_OPERATIONS.slice(0),
            targets:{ai:session.fsName+'/baseline.ai',svg:session.fsName+'/baseline.svg',png:session.fsName+'/baseline.png'},
            assets:[{id:'image',path:session.fsName+'/input.png'}],
            layers:[{id:'foreground',items:[
                {id:'title',kind:'text',text:'DESIGN LAB',position:[40,530],font:'ArialMT',size:48,color:[20,40,60]},
                {id:'curve',kind:'path',points:[
                    {anchor:[40,300],left:[40,300],right:[200,520]},
                    {anchor:[700,300],left:[540,80],right:[700,300]},
                    {anchor:[700,240],left:[700,240],right:[700,240]},
                    {anchor:[40,240],left:[40,240],right:[40,240]}],closed:true,color:[245,90,65]},
                {id:'picture',kind:'raster',assetId:'image',position:[300,230],width:180,height:160}
            ]}]
        };
        var picture = job.layers[0].items[2];
        job.layers[0].items[2] = {id:'masked-image',kind:'group',items:[picture],mask:{
            id:'image-clip',kind:'path',closed:true,color:[0,0,0],points:[
                {anchor:[300,230],left:[300,230],right:[300,230]},
                {anchor:[420,230],left:[420,230],right:[420,230]},
                {anchor:[420,100],left:[420,100],right:[420,100]},
                {anchor:[300,100],left:[300,100],right:[300,100]}]}};
        d = runApprovedJob(job,session.fsName);
        count = d.textFrames.length;
        check(count === 1, 'product bridge missing editable text');
        check(d.textFrames.getByName('title').contents === 'DESIGN LAB', 'text readback mismatch');
        check(d.pathItems.getByName('curve').pathPoints.length === 4, 'path readback mismatch');
        check(d.pathItems.getByName('curve').pathPoints[0].rightDirection[0] === 200, 'Bezier readback mismatch');
        check(d.rasterItems.length === 1 && d.placedItems.length === 0, 'raster not embedded');
        check(File(job.targets.ai).exists && File(job.targets.png).exists && File(job.targets.svg).exists, 'missing native outputs');
        check(d.fullName.fsName.toLowerCase() === File(job.targets.ai).fsName.toLowerCase(), 'reopen identity mismatch');
        check(d.groupItems.getByName('masked-image').clipped, 'clipping group lost');
        check(d.pathItems.getByName('image-clip').clipping, 'clipping path lost');
        check(d.pathItems.length === 2, 'unexpected path count');
        d=stageEvidence('stage-baseline',d);
        stages = 1;
        var first = session.fsName+'/text-edited.ai';
        d = applyApprovedPatch(d,job.targets.ai,{kind:'text',id:'title',text:'DESIGN LAB / EDITED'},first,session.fsName);
        job.layers[0].items[0].text='DESIGN LAB / EDITED';
        readbackJob(d,job);
        check(d.textFrames.getByName('title').contents==='DESIGN LAB / EDITED','first edit lost');
        check(d.pathItems.getByName('curve').pathPoints[0].rightDirection[1]===520,'text edit changed geometry');
        d=stageEvidence('stage-text',d);
        stages = 2;
        var points=job.layers[0].items[1].points;
        points[0].right=[200,420];
        var second=session.fsName+'/geometry-edited.ai';
        d=applyApprovedPatch(d,first,{kind:'path',id:'curve',points:points},second,session.fsName);
        readbackJob(d,job);
        check(d.textFrames.getByName('title').contents==='DESIGN LAB / EDITED','geometry edit changed text');
        check(d.pathItems.getByName('curve').pathPoints[0].rightDirection[1]===420,'second edit lost');
        check(d.rasterItems.length===1 && d.groupItems.getByName('masked-image').clipped,'edits changed media');
        d=stageEvidence('stage-geometry',d);
        stages = 3;
        // Native checkpoint restoration, not a coordinator/crash recovery claim.
        d.close(SaveOptions.DONOTSAVECHANGES);d=null;
        d=app.open(File(job.targets.ai));
        job.layers[0].items[0].text='DESIGN LAB';points[0].right=[200,520];
        readbackJob(d,job);
        check(d.textFrames.getByName('title').contents==='DESIGN LAB','baseline text was overwritten');
        check(d.pathItems.getByName('curve').pathPoints[0].rightDirection[1]===520,'baseline path was overwritten');
        d=stageEvidence('stage-restored',d);
        stages = 4;
        status='PASS';
    } catch (e) { message=String(e).replace(/[\r\n\t]/g,' ')+' line='+e.line; }
    // Only close the document returned by this fixture's call; preserve unknown failure residue.
    if (d) try { d.close(SaveOptions.DONOTSAVECHANGES); }
    catch (cleanupError) { status='FAIL';message+=' task document cleanup: '+String(cleanupError); }
    if (original) original.activate();
    var result=File(session.fsName+'/result.tsv');result.encoding='UTF-8';
    if (!result.open('w')) throw new Error('cannot write result');
    result.write('status\t'+status+'\nmessage\t'+message+'\nhost\t'+app.version+'\ntextCount\t'+count+
      '\nstages\t'+stages+'\ndocumentsBefore\t'+before+'\ndocumentsAfter\t'+app.documents.length+'\n');result.close();
})();
