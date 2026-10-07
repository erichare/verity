# Marketplace submissions — October 7, 2026

## Published packages

[Verity plugins 0.1.1](https://github.com/erichare/verity/releases/tag/plugins-v0.1.1)
contains separate Claude and Codex ZIPs, their SHA-256 checksums, and two explicitly
synthetic X3P reviewer fixtures. Public downloads were compared byte for byte
with the local packages. The earlier 0.1.0 release remains available unchanged.

The 0.1.1 tag points to `0e5e918b5f7f78928182c7ecd420b3df79aa087c`.
The [privacy notice](privacy.md) and [hosted-service terms](terms.md) were approved
by the maintainer before publication. Both manifests link to the tagged copies.

## Claude

[Submission](https://claude.ai/directory/manage/plugins/4b880655-eea8-4ca9-844e-a5e7258b7cce)
was submitted successfully. The security and policy scan passed, and publication
was requested. The portal shows **In review** and **Live: not yet**. An Anthropic
reviewer must approve it. Submission is not a public listing.

The tracked source is `plugins/claude` at `plugins-v0.1.1`. Scheduled checks are
selected. Automatic publication of later versions is disabled. The directory
recognizes the three skills, the hosted MCP server, and all six listing links.
Separate connector registration is optional according to the portal and was not
required for this plugin submission.

## Codex / OpenAI

[Submission portal](https://platform.openai.com/plugins/manage/plugin_asdk_app_6ac6985e54f48191ba34595d8f34989c?tab=details)
contains the 0.1.1 Codex ZIP. Metadata has no issues, all three skill checks
passed, the MCP connection is configured, and the parent domain is verified.
The MCP scan also passed with no issues. Earlier incomplete scans resolved
after reconnection and a later retry against the settled production deployment.
All five positive and three negative review cases and release notes are saved in
the portal. The [genuine recorded walkthrough](https://github.com/erichare/verity/releases/download/plugins-v0.1.1/verity-live.mp4)
is uploaded and linked. Its public download matched the local file byte for byte
and decoded completely without errors. The maintainer approved all six final
legal declarations, which were accepted, and Submit was clicked. The portal then
lost its authenticated session before a submission receipt could be confirmed.
Receipt verification is pending restored sign-in. Do not infer acceptance or
create a duplicate submission without checking the existing portal entry.

The positive and negative cases, observed behavior, and test limitations are in
[the review materials](marketplace-review.md). Five initial positive cases passed
through the actual installed Codex plugin. A fresh post-deployment recording
completed eight sessions with 14 positive-case MCP calls and zero negative-case
MCP calls. Negative-case variances, including an explanation omission in N3,
are recorded explicitly rather than presented as exact passes.

The 6 minute 51.4 second MP4 has SHA-256
`1cd64de63e7d0e705bd2a78d2254c75191c6f4d39cd385012b031d94664435e7`.
The release also contains its original cast, displayed transcript, recording
notes, video metadata, and separate review-asset checksums. The temporary
`verity@verity` test installation and marketplace registration were removed
after the recording completed. Other installed plugins were left in place.

## Deployment and source review

With explicit maintainer approval, commit `0e5e918` was deployed while
[PR #169](https://github.com/erichare/verity/pull/169) awaited required review.
The protected branch was not merged or bypassed.

- Vercel production deployment: `dpl_DQyDBhFyisUPkAWARukKdXdKPsn4`, status READY,
  source SHA confirmed as `0e5e918b5f7f78928182c7ecd420b3df79aa087c`.
- Railway API production deployment: `7cd964fc-3142-47ab-8f9a-56dce1779627`,
  status SUCCESS, uploaded from a clean `git archive` of that exact commit.
  The catalog service was not redeployed.
- The public parent-domain challenge returned HTTP 200 with the exact expected
  bytes. The OpenAI portal subsequently confirmed domain verification.
- The public API health probe succeeded. Its live `tools/list` response contains
  all six titles and explicit read-only, non-destructive, idempotent annotations.
- All nine CI jobs, all five CodeQL language analyses, and the aggregate CodeQL
  check passed on `0e5e918`. The security audit job remains report-only.

The complete scientific-dataset revalidation limitations recorded in
[the sweep report](sweep-2026-10-07.md) remain applicable. Plugin installation,
runtime connectivity, deployment success, and marketplace acceptance are
separate evidence.
