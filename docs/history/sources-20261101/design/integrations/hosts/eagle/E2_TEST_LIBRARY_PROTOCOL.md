# Eagle E2 Test-Library Protocol

This protocol is inactive until a user grants an explicit test-library write authorization. It must not write to the active personal library.

1. Confirm the loopback API version and test-library identity.
2. Create or select a dedicated test library only after user confirmation.
3. Import one synthetic fixture asset with controlled tags.
4. Read back its ID, hash/path-derived identity and tags.
5. Delete only that recorded test asset and verify it is absent.
6. Capture request/result metadata without API tokens, private library paths or personal asset metadata.

An installed service or read-only API response is E1. Successful import/readback/rollback in the test library is the earliest E2 candidate.
