# Adobe E3 Fixture Protocol

This protocol is inactive until a user grants a single-session write authorization. It must use a dedicated fixture directory and must never open a user project.

## Required sequence

1. Start a clean application session.
2. Create a 1920×1080 layered source document with text, group, image/linked object, adjustment and mask semantics appropriate to the tool.
3. Save the native editable source into the fixture directory.
4. Close and reopen it; read back dimensions and the relevant editable object tree.
5. Export a non-source preview.
6. Restore the explicit backup/rollback point and verify the readback.
7. Repeat three times; record duration, failure count, application version, source/output hashes and residue.

The protocol upgrades evidence only when all steps have repeatable readback. A connection, tool enumeration, or a single smoke action remains E1.
