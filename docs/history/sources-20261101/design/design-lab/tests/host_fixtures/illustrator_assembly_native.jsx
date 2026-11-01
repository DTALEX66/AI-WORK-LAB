// SPDX-License-Identifier: MIT
// Synthetic qualification of the actual product bridge. Not human acceptance.
#target illustrator
(function () {
    var root = 'D:/All projects/DESIGN-LAB/.project-local/task-artifacts/illustrator-product-20260908';
    var product = File('D:/All projects/DESIGN-LAB/integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx');
    var session = Folder(root + '/run-' + new Date().getTime());
    if (session.exists || !session.create()) throw new Error('Exclusive session required');
    var before = app.documents.length, d = null, status = 'FAIL', message = '', count = -1;
    var original = before ? app.activeDocument : null;
    function check(test, why) { if (!test) throw new Error(why); }
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
        d = runApprovedJob(job,session.fsName);
        count = d.textFrames.length;
        check(count === 1, 'product bridge missing editable text');
        check(d.textFrames.getByName('title').contents === 'DESIGN LAB', 'text readback mismatch');
        check(d.pathItems.getByName('curve').pathPoints.length === 4, 'path readback mismatch');
        check(d.pathItems.getByName('curve').pathPoints[0].rightDirection[0] === 200, 'Bezier readback mismatch');
        check(d.rasterItems.length === 1 && d.placedItems.length === 0, 'raster not embedded');
        check(File(job.targets.ai).exists && File(job.targets.png).exists && File(job.targets.svg).exists, 'missing native outputs');
        check(d.fullName.fsName.toLowerCase() === File(job.targets.ai).fsName.toLowerCase(), 'reopen identity mismatch');
        status='PASS';
    } catch (e) { message=String(e).replace(/[\r\n\t]/g,' ')+' line='+e.line; }
    // Only close the document returned by this fixture's call; preserve unknown failure residue.
    if (d) d.close(SaveOptions.DONOTSAVECHANGES);
    if (original) original.activate();
    var result=File(session.fsName+'/result.tsv');result.encoding='UTF-8';
    if (!result.open('w')) throw new Error('cannot write result');
    result.write('status\t'+status+'\nmessage\t'+message+'\nhost\t'+app.version+'\ntextCount\t'+count+
      '\ndocumentsBefore\t'+before+'\ndocumentsAfter\t'+app.documents.length+'\n');result.close();
})();
