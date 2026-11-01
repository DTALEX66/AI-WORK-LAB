# Security and provenance

This repository uses path-aware ownership, secret-safe evidence and provenance
records for imported assets. Credentials, auth stores, private keys, browser
data, prompt/response bodies and tokens are forbidden in tracked content and
local evidence. Large files are routed through LFS or approved release
artifacts; size alone is never a deletion reason. SBOM, license and NOTICE
artifacts must be generated from the exact release SHA.
