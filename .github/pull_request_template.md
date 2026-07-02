## Summary

<!-- What does this PR change, and why? One focused change per PR.
     Use a conventional-commit style title, e.g. "fix(api): ..." -->

## Test plan

<!-- How was this verified? Check what applies and list the commands run. -->

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (Rust changes)
- [ ] `uv run --extra dev ruff check . && uv run --extra dev pytest` in each touched Python service
- [ ] `pnpm typecheck` / `pnpm build` (web changes)
- [ ] New/changed behavior is covered by tests

## Does this change any published number?

<!-- Preprocessing, registration, scoring, calibration, reference bundles, or
     protocol definitions can move validation numbers. See the method-change
     policy in CONTRIBUTING.md. -->

- [ ] No — this PR cannot affect validation numbers
- [ ] Yes — `docs/headline-numbers.md` is updated **in this PR**, and the
      change (and why it's intended) is explained below

<!-- If yes: which numbers moved, from what to what, under which protocol label? -->
