# Other marks Verity can include — extension roadmap

**The question:** what additional toolmark families can Verity score, and how much
is real-today vs. needs data/work? The answer is unusually concrete because the
architecture was built domain-general: one algorithm (CMR), one frozen scorer config,
reduced per modality. Adding a mark family is *data + a registry entry*, not new science.

## Where a new mark family plugs in (the three touch points)

1. **Compute** — `services/engine/verity/compare.py` (`DOMAINS`, `_compare`). The CMR
   reductions already cover the two geometries every firearm/tool mark needs:
   striated → CMR-1D (consecutive matching striae), impressed → CMR-2D (congruent
   matching cells). A new *striated* or *impressed* family reuses the existing path
   verbatim — no new compute.
2. **Catalog** — `services/catalog/verity_catalog/models.py`. The cartridge schema
   already declares `MARK_TYPES = ("breech_face", "firing_pin", "ejector", "aperture_shear")`
   and ingest accepts all four (verified: the schema constructs `firing_pin` / `ejector` /
   `aperture_shear` marks today). Bullets and 1-D toolmark profiles have their own paths.
3. **Serve** — `services/api/verity_api/references.py` (`_REFERENCES`). A served domain is
   one dict entry → a calibrated `<family>.npz` reference (KM/KNM scores + cluster IDs +
   provenance) built by an engine `examples/build_*_reference.py`, modeled on
   `build_cartridge_fadul_reference.py`. **The npz reference is the only gated artifact**,
   and the gate is always *data*.

## Data-availability matrix

| Mark family | Geometry → reduction | Data status | Effort |
|---|---|---|---|
| **Cartridge breech face (Weller)** | impressed → CMR-2D | **Available now** — `CSAFE-ISU/cartridgeCaseScans/wellerMasked`: 95 scans, **11 consecutively-manufactured Ruger P95 slides**, CC-BY, masks included. A *second, independent* impressed study. | **Low** (ingest + 2nd reference) |
| **Firing-pin impressions** | impressed → CMR-2D | **Needs segmentation.** The Fadul/Weller primer scans *contain* the firing-pin crater, but the FiX3P masks annotate the **breech face** and exclude the crater. Source: extract the central firing-pin ROI from the same scans, or crawl the NBTRD firing-pin measurements (NRBTD GUIDs are in the repo MANIFEST). | **Medium** (ROI extraction/segmentation + validation) |
| **Ejector / aperture-shear marks** | striated → CMR-1D | Schema ready; needs a marked dataset. Present on many NBTRD cartridge studies. | **Medium** (sourcing + segmentation) |
| **Non-firearm tool striae** (screwdrivers — shipped; pliers, bolt/wire cutters, pry bars, chisels) | striated → CMR-1D | tmaRks screwdriver set is shipped. Other tool classes need a public consecutively-made set (ameslab-style; ameslab itself is GPL — not redistributable from the MIT catalog). | **Medium** (license-clean data) |
| **Fractured / sheared surfaces** (tape, metal, bone, glass) | 3-D patch → SE(3) rigid pose | Research geometry; named in the CMR table as the 3-D reduction. | **High** (new vote producer + data) |

## Recommended sequence

1. **Weller breech faces — the immediate, real next dataset.** It is available now under a
   clean license and turns the single-study Fadul impressed result into a **two-study,
   cross-instrument** generalization claim (Glock slides → Ruger slides), exactly the
   independent-validation move a forensic statistician asks for. *Caveat:* `wellerMasked`
   is nested one sub-folder per firearm (`TW01…TW11`), and the `github` harvester
   (`harvest/github.py`) lists a single directory — so this needs a small nested-directory
   harvest pass (or 11 manifest entries) before ingest. No new science.
2. **Firing-pin impressions** — the headline "fourth mark." Schema and CMR-2D are ready; the
   work is a firing-pin ROI extractor (the crater the breech-face mask currently excludes)
   plus source-disjoint validation, producing `cartridge_firingpin.npz` and a `firing_pin`
   entry in `_REFERENCES`. Reinforces "one scorer, four marks."
3. **Ejector / aperture-shear striae** — CMR-1D, after a marked source is located.

## Why we are not shipping a live firing-pin domain before the Carriquiry meeting

Putting an *unvalidated* forensic domain behind a calibrated-LR API would contradict the
core discipline Verity is built on — no LR without a source-disjoint reference under the
frozen scorer-config hash. The schema is ready and the path is one builder + one registry
entry, but the reference must be **built and validated** first. The credible position for
the meeting is exactly this roadmap: the platform demonstrably accepts these marks today,
Weller is the next ingest, and firing-pin is a segmentation step away.
