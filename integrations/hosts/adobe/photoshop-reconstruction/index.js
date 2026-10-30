/* SPDX-License-Identifier: MIT */
/* DESIGN-LAB bounded UXP entrypoint: all document changes are modal and job-bound. */
const { app, core } = require("photoshop");

function closed(value, fields) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).length !== fields.length ||
      fields.some(key => !Object.prototype.hasOwnProperty.call(value, key))) {
    throw new Error("invalid closed record");
  }
}

function nativePath(value) {
  if (typeof value !== "string") throw new Error("native path required");
  const path = value.replace(/\\/g, "/");
  if (!/^[A-Za-z]:\//.test(path) || /[\x00-\x1f]/.test(path) ||
      path.slice(3).includes(":") || path.split("/").some(part =>
        part === "." || part === ".." || /[. ]$/.test(part))) {
    throw new Error("unsafe native path");
  }
  return path.replace(/\/+$/, "").toLowerCase();
}

function assertRunRelative(job, approvedFolder) {
  closed(job, ["runRoot", "outputName", "width", "height", "layers"]);
  if (!approvedFolder || approvedFolder.isFolder !== true ||
      nativePath(job.runRoot) !== nativePath(approvedFolder.nativePath)) {
    throw new Error("trusted session folder required");
  }
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,79}\.psd$/i.test(job.outputName)) throw new Error("simple PSD output name required");
  for (const size of [job.width, job.height]) {
    if (!Number.isInteger(size) || size < 1 || size > 16383) throw new Error("invalid dimensions");
  }
  if (!Array.isArray(job.layers) || !job.layers.length || job.layers.length > 100) throw new Error("invalid layers");
  const ids = new Set();
  for (const layer of job.layers) {
    closed(layer, ["id", "kind", "contents", "fontSize"]);
    if (typeof layer.id !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(layer.id) || ids.has(layer.id)) throw new Error("invalid or duplicate layer ID");
    ids.add(layer.id);
    if (layer.kind !== "text") throw new Error("unsupported layer kind");
    if (typeof layer.contents !== "string" || !layer.contents.length || layer.contents.length > 10000 ||
        typeof layer.fontSize !== "number" || !Number.isFinite(layer.fontSize) || layer.fontSize < 1 || layer.fontSize > 1296) throw new Error("invalid editable text");
  }
}

function cancelled(context) {
  if (context.isCancelled) throw new Error("cancelled; reconcile any retained task output");
}

async function prepareRunRelativeLayers(hostApp, job, approvedFolder, executionContext) {
  assertRunRelative(job, approvedFolder);
  cancelled(executionContext);
  const version = String(hostApp.version).split(".").map(Number);
  if (!Number.isFinite(version[0]) || version[0] < 24 ||
      (version[0] === 24 && (!Number.isFinite(version[1]) || version[1] < 2))) throw new Error("Photoshop 24.2+ required");
  const entries = await approvedFolder.getEntries();
  if (entries.some(entry => entry.name.toLowerCase() === job.outputName.toLowerCase())) throw new Error("existing output refused");
  cancelled(executionContext);
  // Create exclusively through the trusted UXP Folder; do not resolve payload URLs.
  const output = await approvedFolder.createFile(job.outputName, { overwrite: false });
  const expected = nativePath(job.runRoot) + "/" + job.outputName.toLowerCase();
  if (output.isFile !== true || nativePath(output.nativePath) !== expected) throw new Error("unexpected UXP output entry");
  let ownedDocument = null;
  try {
    cancelled(executionContext);
    ownedDocument = await hostApp.createDocument({width:job.width, height:job.height,
      resolution:72, mode:"RGBColorMode", fill:"transparent"});
    for (const layer of job.layers) {
      cancelled(executionContext);
      await ownedDocument.createTextLayer({name:layer.id, contents:layer.contents, fontSize:layer.fontSize});
    }
    cancelled(executionContext);
    await ownedDocument.saveAs.psd(output, {embedColorProfile:true}, false);
    await ownedDocument.closeWithoutSaving();
    ownedDocument = null;
    cancelled(executionContext);
    ownedDocument = await hostApp.open(output);
    if (nativePath(ownedDocument.path) !== expected || ownedDocument.width !== job.width || ownedDocument.height !== job.height) throw new Error("native document readback mismatch");
    for (const spec of job.layers) {
      const matches = Array.from(ownedDocument.layers).filter(layer => layer.name === spec.id);
      if (matches.length !== 1 || matches[0].textItem.contents !== spec.contents) throw new Error("editable text readback mismatch");
    }
    cancelled(executionContext);
    return {status:"NATIVE_READBACK", documentId:ownedDocument.id,
      outputPath:output.nativePath, textCount:job.layers.length};
  } catch (error) {
    // Preserve own partial state for coordinator reconciliation; never close a user document.
    error.taskDocumentId = ownedDocument ? ownedDocument.id : null;
    error.taskOutputPath = output.nativePath;
    throw error;
  }
}

async function executeJob(job, approvedFolder) {
  assertRunRelative(job, approvedFolder);
  const snapshot = JSON.parse(JSON.stringify(job));
  return await core.executeAsModal(async (executionContext) => {
    if (executionContext.isCancelled) throw new Error("cancelled");
    return await prepareRunRelativeLayers(app, snapshot, approvedFolder, executionContext);
  }, { commandName: "DESIGN-LAB Reconstruction Layer Preparation" });
}

module.exports = { executeJob, prepareRunRelativeLayers };
