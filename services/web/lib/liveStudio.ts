// The live glass-box walk: run an uploaded pair through the real engine, gathering the
// per-stage artifacts the Studio animates. The final report comes from /compare (the
// calibrated LR + attribution); the intermediate grids/signature/CCF come from the
// /v1/steps/* endpoints. Every step call is best-effort — if the step API is unavailable
// or CORS-blocked, the run still resolves from the report alone (derived intermediates),
// so an upload never fails just because the deep walk couldn't complete.

import { compareMarks } from "./api";
import { alignStep, arealSignatureStep, ingestArtifact, preprocessStep, signatureStep } from "./stepApi";
import { uploadRunRich, type LiveExtras, type StudioRun } from "./studio";
import { isRefusal, type GallerySignatures, type MarkDomain, type RefusalResponse } from "./types";

export type LiveResult =
  | { kind: "run"; run: StudioRun }
  | { kind: "refused"; refusal: RefusalResponse };

let seq = 0;

export async function runLivePipeline(
  domain: MarkDomain,
  marksA: File[],
  marksB: File[],
): Promise<LiveResult> {
  // The calibrated result is required (throws on a network/API error → surfaced to the user).
  const report = await compareMarks(domain, marksA, marksB);
  if (isRefusal(report)) return { kind: "refused", refusal: report };

  const extras: LiveExtras = { idSuffix: String(++seq) };
  try {
    const [aRef, bRef] = await Promise.all([
      ingestArtifact(marksA[0]),
      ingestArtifact(marksB[0]),
    ]);

    if (domain === "impressed") {
      const [areal, pa, pb] = await Promise.all([
        arealSignatureStep(aRef.handle),
        preprocessStep(aRef.handle).catch(() => null),
        preprocessStep(bRef.handle).catch(() => null),
      ]);
      extras.arealRaw = areal.preview.grid;
      if (pa) extras.bandA = pa.preview.grid;
      if (pb) extras.bandB = pb.preview.grid;
    } else {
      // One signature call backfills raw + bandpassed + rotated + the 1-D signature.
      const [sa, sb] = await Promise.all([signatureStep(aRef.handle), signatureStep(bRef.handle)]);
      extras.rawA = sa.preview.raw_preview;
      extras.rawB = sb.preview.raw_preview;
      extras.bandA = sa.preview.bandpassed_preview;
      extras.bandB = sb.preview.bandpassed_preview;
      extras.tiltDeg = sa.preview.tilt_deg;
      const signatures: GallerySignatures = {
        a: sa.preview.signature,
        b: sb.preview.signature,
        bandsA: [],
        bandsB: [],
      };
      extras.signatures = signatures;
      try {
        const al = await alignStep(sa.handle, sb.handle);
        extras.align = { lag: al.lag, ccf: al.ccf };
      } catch {
        // the align CCF is a bonus readout; its absence falls back to the band count
      }
    }
  } catch {
    // step API unavailable / CORS-blocked — the run falls back to report-derived stages
  }

  return { kind: "run", run: uploadRunRich(report, domain, extras) };
}
