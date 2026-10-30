// SPDX-License-Identifier: MIT
// DESIGN-LAB bounded Illustrator host-job assembly entrypoint.
#target illustrator

var REQUIRED_OPERATIONS = [
    "createDocument", "createLayer", "placePath", "placeText", "placeRaster", "applyMask",
    "saveAI", "exportSVG", "reopen", "readback", "exportPNG"
];

function assertInside(child, root) {
    var c = File(child).fsName.replace(/\\/g, "/").toLowerCase();
    var r = Folder(root).fsName.replace(/\\/g, "/").toLowerCase();
    if (r.charAt(r.length - 1) !== "/") r += "/";
    if (c.indexOf(r) !== 0) throw new Error("target outside run root");
}

function createDocument(job) {
    var doc = app.documents.add(DocumentColorSpace.RGB, job.artboard.width, job.artboard.height);
    doc.artboards[0].artboardRect = [0, job.artboard.height, job.artboard.width, 0];
    return doc;
}

function jobObject(value, fields) {
    if (!value || typeof value !== "object" || value instanceof Array) throw new Error("object required");
    var allowed = "|" + fields.join("|") + "|", k, i;
    for (k in value) if (!value.hasOwnProperty(k) || allowed.indexOf("|" + k + "|") < 0) throw new Error("unknown field: " + k);
    for (i = 0; i < fields.length; i++) if (!value.hasOwnProperty(fields[i])) throw new Error("missing field: " + fields[i]);
}

function jobArray(value, min, max) {
    if (!(value instanceof Array) || value.length < min || value.length > max) throw new Error("invalid array size");
}

function jobNumber(value, min, max) {
    if (typeof value !== "number" || !isFinite(value) || value < min || value > max) throw new Error("invalid number");
}

function jobVector(value, count, min, max) {
    jobArray(value, count, count);
    for (var i = 0; i < count; i++) jobNumber(value[i], min, max);
}

function jobId(value, seen) {
    if (typeof value !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(value)) throw new Error("invalid ID");
    if (seen["$" + value]) throw new Error("duplicate ID: " + value);
    seen["$" + value] = true;
}

function jobPath(value, root) {
    if (typeof value !== "string" || !/^[A-Za-z]:\//.test(value.replace(/\\/g, "/")) || /[\x00-\x1f<>"|?*]/.test(value) || value.slice(2).indexOf(":") >= 0) throw new Error("absolute local path required");
    assertInside(value, root);
}

// approvedRoot comes from the trusted caller's session, never from payload.runRoot.
// The caller also owns reparse/race checks, asset hashes, rights and writer lease.
function validateJob(job, approvedRoot) {
    jobObject(job, ["schemaVersion", "jobId", "rirHash", "runRoot", "artboard", "layers", "assets", "targets", "operations", "authorization"]);
    if (!job || job.schemaVersion !== "design-lab/adobe-host-job/v1") throw new Error("invalid host job");
    var ids = {}, assets = {}, i, j, k, item;
    jobId(job.jobId, {});
    if (typeof job.rirHash !== "string" || !/^[0-9a-f]{64}$/.test(job.rirHash) || /^0+$/.test(job.rirHash)) throw new Error("invalid RIR hash");
    if (typeof approvedRoot !== "string" || !/^[A-Za-z]:\//.test(approvedRoot.replace(/\\/g, "/")) || typeof job.runRoot !== "string") throw new Error("trusted root required");
    if (Folder(job.runRoot).fsName.toLowerCase() !== Folder(approvedRoot).fsName.toLowerCase() || !Folder(approvedRoot).exists) throw new Error("unapproved run root");
    jobObject(job.authorization, ["required", "scope"]);
    if (!job.authorization || job.authorization.required !== true || job.authorization.scope !== "single-session") throw new Error("authorization missing");
    jobObject(job.artboard, ["width", "height"]);
    jobNumber(job.artboard.width, 1, 16383); jobNumber(job.artboard.height, 1, 16383);
    jobArray(job.operations, REQUIRED_OPERATIONS.length, REQUIRED_OPERATIONS.length);
    for (i = 0; i < REQUIRED_OPERATIONS.length; i++) if (job.operations[i] !== REQUIRED_OPERATIONS[i]) throw new Error("invalid operation sequence");
    jobObject(job.targets, ["ai", "svg", "png"]);
    for (k in job.targets) {
        jobPath(job.targets[k], approvedRoot);
        if (job.targets[k].slice(-(k.length + 1)).toLowerCase() !== "." + k) throw new Error("wrong output extension");
        if (File(job.targets[k]).exists) throw new Error("refusing existing output");
    }
    jobArray(job.assets, 0, 500);
    for (i = 0; i < job.assets.length; i++) {
        jobObject(job.assets[i], ["id", "path"]); jobId(job.assets[i].id, ids);
        jobPath(job.assets[i].path, approvedRoot);
        if (!/\.(png|jpe?g)$/i.test(job.assets[i].path) || !File(job.assets[i].path).exists) throw new Error("missing or unsupported raster");
        assets["$" + job.assets[i].id] = job.assets[i].path;
    }
    jobArray(job.layers, 1, 100);
    var objectCount = 0;
    function validateItem(item, depth) {
            var k;
            if (depth > 8 || ++objectCount > 10000) throw new Error("object complexity limit");
            if (!item || typeof item !== "object") throw new Error("object required");
            if (item.kind === "text") {
                jobObject(item, ["id", "kind", "text", "position", "font", "size", "color"]);
                if (typeof item.text !== "string" || !item.text.length || item.text.length > 10000) throw new Error("invalid text");
                if (typeof item.font !== "string" || !item.font.length) throw new Error("font required");
                app.textFonts.getByName(item.font);
                jobVector(item.position, 2, -16383, 16383); jobNumber(item.size, 1, 1296);
                jobVector(item.color, 3, 0, 255);
            } else if (item.kind === "path") {
                jobObject(item, ["id", "kind", "points", "closed", "color"]);
                if (typeof item.closed !== "boolean") throw new Error("closed must be boolean");
                jobVector(item.color, 3, 0, 255); jobArray(item.points, 2, 10000);
                for (k = 0; k < item.points.length; k++) {
                    jobObject(item.points[k], ["anchor", "left", "right"]);
                    jobVector(item.points[k].anchor, 2, -16383, 16383);
                    jobVector(item.points[k].left, 2, -16383, 16383);
                    jobVector(item.points[k].right, 2, -16383, 16383);
                }
            } else if (item.kind === "compound") {
                jobObject(item, ["id", "kind", "contours", "color"]);
                jobVector(item.color, 3, 0, 255); jobArray(item.contours, 2, 256);
                var pointCount = 0;
                for (k = 0; k < item.contours.length; k++) {
                    var contour = item.contours[k];
                    if (!contour || contour.kind !== "path" || contour.closed !== true) throw new Error("invalid compound contour");
                    validateItem(contour, depth + 1); jobArray(contour.points, 3, 10000);
                    for (var channel = 0; channel < 3; channel++) if (contour.color[channel] !== item.color[channel]) throw new Error("compound color mismatch");
                    pointCount += contour.points.length;
                }
                if (pointCount > 10000) throw new Error("compound point limit");
            } else if (item.kind === "raster") {
                jobObject(item, ["id", "kind", "assetId", "position", "width", "height"]);
                if (typeof item.assetId !== "string" || !assets["$" + item.assetId]) throw new Error("unknown asset reference");
                jobVector(item.position, 2, -16383, 16383);
                jobNumber(item.width, 0.01, 16383); jobNumber(item.height, 0.01, 16383);
            } else if (item.kind === "group") {
                jobObject(item, ["id", "kind", "items", "mask"]);
                jobArray(item.items, 1, 1000);
                for (k = 0; k < item.items.length; k++) validateItem(item.items[k], depth + 1);
                if (item.mask !== null) {
                    if (!item.mask || item.mask.kind !== "path" || item.mask.closed !== true) throw new Error("closed path mask required");
                    validateItem(item.mask, depth + 1);
                }
            } else throw new Error("unsupported object kind");
            jobId(item.id, ids);
    }
    for (i = 0; i < job.layers.length; i++) {
        jobObject(job.layers[i], ["id", "items"]); jobId(job.layers[i].id, ids);
        jobArray(job.layers[i].items, 1, 1000);
        for (j = 0; j < job.layers[i].items.length; j++) validateItem(job.layers[i].items[j], 0);
    }
}

function runApprovedJob(job, approvedRoot) {
    validateJob(job, approvedRoot);
    var doc = createDocument(job);
    var assets = {}, i, j, layer;
    for (i = 0; i < job.assets.length; i++) assets["$" + job.assets[i].id] = job.assets[i].path;
    function buildItem(parent, spec) {
            var item, anchors, k;
            if (spec.kind === "text") {
                item = parent.textFrames.add(); item.name = spec.id; item.contents = spec.text;
                item.textRange.characterAttributes.textFont = app.textFonts.getByName(spec.font);
                item.textRange.characterAttributes.size = spec.size;
                item.textRange.characterAttributes.fillColor = jobRGB(spec.color);
                // Font metrics move point-text bounds around a fixed baseline.
                // Set the requested top-left only after the final font and size.
                item.position = spec.position;
            } else if (spec.kind === "path") {
                item = parent.pathItems.add(); item.name = spec.id; anchors = [];
                for (k = 0; k < spec.points.length; k++) anchors.push(spec.points[k].anchor);
                item.setEntirePath(anchors); item.closed = spec.closed;
                for (k = 0; k < spec.points.length; k++) {
                    item.pathPoints[k].leftDirection = spec.points[k].left;
                    item.pathPoints[k].rightDirection = spec.points[k].right;
                }
                item.stroked = false; item.filled = true; item.fillColor = jobRGB(spec.color);
            } else if (spec.kind === "compound") {
                item = parent.compoundPathItems.add(); item.name = spec.id;
                for (k = 0; k < spec.contours.length; k++) {
                    var child = buildItem(item, spec.contours[k]);
                    child.evenodd = false;
                }
            } else if (spec.kind === "raster") {
                item = parent.placedItems.add(); item.file = File(assets["$" + spec.assetId]);
                item.name = spec.id; item.width = spec.width; item.height = spec.height;
                item.position = spec.position;
            } else {
                item = parent.groupItems.add(); item.name = spec.id;
                for (k = 0; k < spec.items.length; k++) buildItem(item, spec.items[k]);
                if (spec.mask !== null) {
                    var mask = buildItem(item, spec.mask);
                    mask.clipping = true; mask.filled = false; mask.stroked = false;
                    item.clipped = true;
                }
            }
            return item;
    }
    // Layer and item order is back-to-front: each add creates a frontmost object.
    for (i = 0; i < job.layers.length; i++) {
        layer = i === 0 ? doc.layers[0] : doc.layers.add();
        layer.name = job.layers[i].id;
        for (j = 0; j < job.layers[i].items.length; j++) buildItem(layer, job.layers[i].items[j]);
    }
    var nativeFile = jobNewOutput(job.targets.ai, approvedRoot);
    var options = new IllustratorSaveOptions();
    options.pdfCompatible = true; options.compressed = true; options.embedLinkedFiles = true;
    doc.saveAs(nativeFile, options);
    if (!nativeFile.exists || nativeFile.length === 0) throw new Error("native output absent");
    if (doc.fullName.fsName.toLowerCase() !== nativeFile.fsName.toLowerCase()) throw new Error("saved document identity mismatch");
    doc.close(SaveOptions.DONOTSAVECHANGES);
    doc = app.open(nativeFile);
    if (doc.fullName.fsName.toLowerCase() !== nativeFile.fsName.toLowerCase()) throw new Error("reopened document identity mismatch");
    readbackJob(doc, job);
    var png = jobNewOutput(job.targets.png, approvedRoot), po = new ExportOptionsPNG24();
    po.artBoardClipping = true; po.transparency = true; po.antiAliasing = true;
    po.horizontalScale = 100; po.verticalScale = 100;
    doc.exportFile(png, ExportType.PNG24, po);
    var svg = jobNewOutput(job.targets.svg, approvedRoot), so = new ExportOptionsSVG();
    so.embedRasterImages = true; so.coordinatePrecision = 4;
    doc.exportFile(svg, ExportType.SVG, so);
    if (!png.exists || !png.length || !svg.exists || !svg.length) throw new Error("preview output absent");
    // SVG export can change the in-memory document's file association in this host.
    // Never return that export-associated document as the native editing session.
    doc.close(SaveOptions.DONOTSAVECHANGES);
    doc = app.open(nativeFile);
    if (doc.fullName.fsName.toLowerCase() !== nativeFile.fsName.toLowerCase()) throw new Error("final native identity mismatch");
    readbackJob(doc, job);
    // Keep the reopened task document available for caller-owned local patches.
    // Errors deliberately propagate; the coordinator must reconcile partial effects.
    return doc;
}

function jobRGB(values) {
    var c = new RGBColor(); c.red = values[0]; c.green = values[1]; c.blue = values[2]; return c;
}

function jobNewOutput(path, root) {
    jobPath(path, root);
    var f = File(path);
    if (f.exists || !f.parent.exists) throw new Error("output exists or parent missing");
    return f;
}

function patchObject(doc, kind, id) {
    var collection = kind === "text" ? doc.textFrames : doc.pathItems;
    var found = null, count = 0;
    for (var i = 0; i < collection.length; i++) if (collection[i].name === id) { found = collection[i]; count++; }
    if (count !== 1) throw new Error("patch target absent or ambiguous");
    return found;
}

// Closed checkpoint -> one existing-object edit -> new native version.
// Original rirHash identifies the checkpoint design; patch and checkpoint
// bytes are independently bound in the coordinator request/receipt.
function runApprovedPatchJob(job, approvedRoot) {
    jobObject(job, ["schemaVersion","jobId","rirHash","runRoot","artboard","layers","assets","targets","operations","authorization","checkpoint","checkpointSha256","patch"]);
    if(job.schemaVersion!=="design-lab/adobe-patch-job/v1")throw Error("invalid patch schema");
    var sequence=["openAI","readback","patchObject","saveAI","reopen","readback","exportPNG","exportSVG"],i,k;
    jobArray(job.operations,sequence.length,sequence.length);
    for(i=0;i<sequence.length;i++)if(job.operations[i]!==sequence[i])throw Error("invalid patch sequence");
    var base={};for(k in job)if(k!=="checkpoint" && k!=="checkpointSha256" && k!=="patch")base[k]=job[k];
    base.schemaVersion="design-lab/adobe-host-job/v1";base.operations=REQUIRED_OPERATIONS.slice(0);
    validateJob(base,approvedRoot);jobPath(job.checkpoint,approvedRoot);
    if(!/\.ai$/i.test(job.checkpoint) || !File(job.checkpoint).exists || !/^[0-9a-f]{64}$/.test(job.checkpointSha256))throw Error("invalid checkpoint");
    var patch=job.patch,target=null,count=0;
    if(!patch || (patch.kind!=="text" && patch.kind!=="path"))throw Error("invalid patch kind");
    jobObject(patch,patch.kind==="text"?["kind","id","text"]:["kind","id","points"]);jobId(patch.id,{});
    function visit(n){
        if(n.id===patch.id){target=n;count++;}
        var children=[];
        if(n.kind==="group")children=n.items;
        else if(n.kind==="compound")children=n.contours;
        for(var j=0;j<children.length;j++)visit(children[j]);
        if(n.kind==="group" && n.mask)visit(n.mask);
    }
    for(i=0;i<base.layers.length;i++)for(k=0;k<base.layers[i].items.length;k++)visit(base.layers[i].items[k]);
    if(count!==1 || target.kind!==patch.kind)throw Error("patch plan target ambiguous or absent");
    if(patch.kind==="text"){
        if(typeof patch.text!=="string" || !patch.text.length || patch.text.length>10000)throw Error("invalid patch text");
    }else{
        jobArray(patch.points,target.points.length,target.points.length);
        for(i=0;i<patch.points.length;i++){
            jobObject(patch.points[i],["anchor","left","right"]);
            jobVector(patch.points[i].anchor,2,-16383,16383);jobVector(patch.points[i].left,2,-16383,16383);jobVector(patch.points[i].right,2,-16383,16383);
        }
    }
    var input=File(job.checkpoint);
    // Never attach to an already open document, including an unsaved user edit.
    for(i=0;i<app.documents.length;i++){
        var openName=null;try{openName=app.documents[i].fullName.fsName;}catch(e){}
        if(openName && openName.toLowerCase()===input.fsName.toLowerCase())throw Error("checkpoint already open");
    }
    var doc=app.open(input);
    if(doc.fullName.fsName.toLowerCase()!==input.fsName.toLowerCase())throw Error("checkpoint identity mismatch");
    readbackJob(doc,base);
    doc=applyApprovedPatch(doc,job.checkpoint,patch,job.targets.ai,approvedRoot);
    if(patch.kind==="text")target.text=patch.text;else target.points=patch.points;
    readbackJob(doc,base);
    var png=jobNewOutput(job.targets.png,approvedRoot),po=new ExportOptionsPNG24();
    po.artBoardClipping=true;po.transparency=true;po.antiAliasing=true;po.horizontalScale=100;po.verticalScale=100;
    doc.exportFile(png,ExportType.PNG24,po);
    var svg=jobNewOutput(job.targets.svg,approvedRoot),so=new ExportOptionsSVG();so.embedRasterImages=true;so.coordinatePrecision=4;
    doc.exportFile(svg,ExportType.SVG,so);
    if(!png.exists || !png.length || !svg.exists || !svg.length)throw Error("patch previews missing");
    doc.close(SaveOptions.DONOTSAVECHANGES);doc=app.open(File(job.targets.ai));
    if(doc.fullName.fsName.toLowerCase()!==File(job.targets.ai).fsName.toLowerCase())throw Error("patch final identity mismatch");
    readbackJob(doc,base);return doc;
}

// Each call changes one existing object and saves to a new AI version.
// The caller's attempt/lease must cover this synchronous call and any recovery.
function applyApprovedPatch(doc, expectedNativePath, patch, outputNativePath, approvedRoot) {
    jobPath(expectedNativePath, approvedRoot);
    var output = jobNewOutput(outputNativePath, approvedRoot);
    if (!/\.ai$/i.test(expectedNativePath) || !/\.ai$/i.test(outputNativePath)) throw new Error("native AI paths required");
    if (!File(expectedNativePath).exists || doc.fullName.fsName.toLowerCase() !== File(expectedNativePath).fsName.toLowerCase() || doc.saved !== true) throw new Error("document identity or unsaved state mismatch");
    if (!patch || (patch.kind !== "text" && patch.kind !== "path")) throw new Error("unsupported patch kind");
    jobObject(patch, patch.kind === "text" ? ["kind", "id", "text"] : ["kind", "id", "points"]);
    jobId(patch.id, {});
    var item = patchObject(doc, patch.kind, patch.id), i;
    if (patch.kind === "text") {
        if (typeof patch.text !== "string" || !patch.text.length || patch.text.length > 10000) throw new Error("invalid patch text");
    } else {
        jobArray(patch.points, 2, 10000);
        if (patch.points.length !== item.pathPoints.length) throw new Error("path topology change requires a new object plan");
        for (i = 0; i < patch.points.length; i++) {
            jobObject(patch.points[i], ["anchor", "left", "right"]);
            jobVector(patch.points[i].anchor, 2, -16383, 16383);
            jobVector(patch.points[i].left, 2, -16383, 16383);
            jobVector(patch.points[i].right, 2, -16383, 16383);
        }
    }
    // No side effects above this point. Do not reconstruct the document or layer.
    if (patch.kind === "text") item.contents = patch.text;
    else for (i = 0; i < patch.points.length; i++) {
        item.pathPoints[i].anchor = patch.points[i].anchor;
        item.pathPoints[i].leftDirection = patch.points[i].left;
        item.pathPoints[i].rightDirection = patch.points[i].right;
    }
    var options = new IllustratorSaveOptions();
    options.pdfCompatible = true; options.compressed = true; options.embedLinkedFiles = true;
    // Recheck at write time; atomic lease/race handling belongs to coordinator.
    if (output.exists) throw new Error("output appeared before save; reconcile mutation");
    doc.saveAs(output, options);
    if (!output.exists || !output.length) throw new Error("patch save missing");
    doc.close(SaveOptions.DONOTSAVECHANGES);
    var reopened = app.open(output);
    if (reopened.fullName.fsName.toLowerCase() !== output.fsName.toLowerCase()) throw new Error("patch reopen identity mismatch");
    var actual = patchObject(reopened, patch.kind, patch.id);
    if (patch.kind === "text") {
        if (actual.contents !== patch.text) throw new Error("patch text readback mismatch");
    } else for (i = 0; i < patch.points.length; i++) {
        patchVectorMatch(actual.pathPoints[i].anchor, patch.points[i].anchor);
        patchVectorMatch(actual.pathPoints[i].leftDirection, patch.points[i].left);
        patchVectorMatch(actual.pathPoints[i].rightDirection, patch.points[i].right);
    }
    return reopened;
}

function patchVectorMatch(actual, expected) {
    for (var i = 0; i < 2; i++) if (typeof actual[i] !== "number" || !isFinite(actual[i]) || Math.abs(actual[i] - expected[i]) > 0.02) throw new Error("patch geometry readback mismatch");
}

function readbackJob(doc, job) {
    var textCount = 0, pathCount = 0, rasterCount = 0, i, j, k, spec, actual;
    function near(a, b) { if (typeof a !== "number" || !isFinite(a) || typeof b !== "number" || !isFinite(b) || Math.abs(a - b) > 0.02) throw new Error("numeric readback mismatch"); }
    function vector(a, b) { for (var n = 0; n < b.length; n++) near(a[n], b[n]); }
    if (doc.layers.length !== job.layers.length) throw new Error("layer count mismatch");
    vector(doc.artboards[0].artboardRect, [0, job.artboard.height, job.artboard.width, 0]);
    function readItem(parent, spec, isMask) {
            var actual, k;
            if (spec.kind === "text") {
                textCount++; actual = parent.textFrames.getByName(spec.id);
                if (actual.contents !== spec.text || actual.textRange.characterAttributes.textFont.name !== spec.font) throw new Error("text/font readback mismatch");
                near(actual.textRange.characterAttributes.size, spec.size);
                vector(actual.position, spec.position);
            } else if (spec.kind === "path") {
                pathCount++; actual = parent.pathItems.getByName(spec.id);
                if (actual.pathPoints.length !== spec.points.length || actual.closed !== spec.closed) throw new Error("path readback mismatch");
                if (actual.clipping !== (isMask === true)) throw new Error("mask flag mismatch");
                for (k = 0; k < spec.points.length; k++) {
                    vector(actual.pathPoints[k].anchor, spec.points[k].anchor);
                    vector(actual.pathPoints[k].leftDirection, spec.points[k].left);
                    vector(actual.pathPoints[k].rightDirection, spec.points[k].right);
                }
            } else if (spec.kind === "compound") {
                actual = parent.compoundPathItems.getByName(spec.id);
                if (actual.pathItems.length !== spec.contours.length) throw new Error("compound contour count mismatch");
                for (k = 0; k < spec.contours.length; k++) {
                    if (actual.pathItems.getByName(spec.contours[k].id).evenodd !== false) throw new Error("compound fill rule mismatch");
                    readItem(actual, spec.contours[k], false);
                }
            } else if (spec.kind === "raster") rasterCount++;
            else {
                actual = parent.groupItems.getByName(spec.id);
                if (actual.clipped !== (spec.mask !== null)) throw new Error("clipping group mismatch");
                for (k = 0; k < spec.items.length; k++) readItem(actual, spec.items[k], false);
                if (spec.mask !== null) readItem(actual, spec.mask, true);
            }
    }
    for (i = 0; i < job.layers.length; i++) {
        var layer = doc.layers.getByName(job.layers[i].id);
        for (j = 0; j < job.layers[i].items.length; j++) readItem(layer, job.layers[i].items[j], false);
    }
    if (doc.textFrames.length !== textCount || doc.pathItems.length !== pathCount || doc.rasterItems.length !== rasterCount || doc.placedItems.length !== 0) throw new Error("editable object counts mismatch");
    return {textCount:textCount,pathCount:pathCount,rasterCount:rasterCount};
}
