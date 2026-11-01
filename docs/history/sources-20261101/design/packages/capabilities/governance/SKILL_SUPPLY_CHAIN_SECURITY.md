# Skill supply-chain security

Treat natural-language skills as executable dependencies.

## Threats

- Trigger stuffing that makes one skill dominate retrieval.
- Claims of authority or quality not supported by tests.
- Instructions that suppress competing tools or safety rules.
- Hidden network, credential, file-deletion or publishing behavior.
- License laundering through rewritten prompts.
- Brand extraction that encourages pixel cloning or trademark misuse.
- Benchmark overfitting and self-judging.

## Required controls

1. Pin repository and commit.
2. Record SPDX license and source URL.
3. Parse frontmatter and compare triggers against capability scope.
4. Run static pattern checks before agent loading.
5. Execute in a restricted project fixture.
6. Require explicit capabilities in `open-design.json`.
7. Use independent evaluators and no-skill baselines.
8. Store output provenance, token cost and artifact hashes.
9. Disable the source automatically when its license or integrity changes.
