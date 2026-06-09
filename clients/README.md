# Verity API clients

Thin clients for the Verity calibrated-LR API ([api.verity.codes](https://api.verity.codes)),
in Python and R. Both mirror the same surface: `compare`, the metadata endpoints
(`scorer_config`, `references`), the calibration firewall (`calibrate`), and the
glass-box step graph (`upload` → `step`).

Every comparison returns a reproducible **recipe** (the methods section as JSON — every
step, its parameters, the engine version, the input hashes, the reference provenance)
stamped with a content **handle**. Same inputs + scorer config + reference + engine ⇒
same handle, so **verifying a published likelihood ratio is a hash-equality check** — and
it's identical across the Python and R clients.

Point either client at a deployment with `VERITY_API_URL` (default
`https://api.verity.codes`).

## Python

```python
# pip install requests   (the only dependency)
import sys; sys.path.append("clients/python")
from verity_client import VerityClient

v = VerityClient("https://api.verity.codes")
report = v.compare("impressed", "breech_a.x3p", "breech_b.x3p")   # or a list of land paths
print(report["likelihood_ratio"], report["verbal"])
print("handle:", report["handle"])                                # the content address

# reproduce: re-run and check the handle matches — a one-line provenance check
assert v.reproduce("impressed", "breech_a.x3p", "breech_b.x3p", expect_handle=report["handle"])
```

Drive the pipeline as a graph, or explore an off-config scorer (the firewall returns the
raw score with `calibrated: false` rather than a mis-scaled LR):

```python
h_a = v.upload("breech_a.x3p")
sig = v.step("areal-signature", surface=h_a)        # → a content-addressed signature.2d
v.compare("impressed", "a.x3p", "b.x3p", scorer_config={"cmr_corr": 0.5})  # → calibrated: False
```

## R

```r
# install.packages(c("httr2", "curl", "jsonlite"))
source("clients/r/verity.R")

report <- verity_compare("impressed", "breech_a.x3p", "breech_b.x3p")
cat(report$likelihood_ratio, report$verbal, "\n")
cat("handle:", report$handle, "\n")

# reproduce: the handle is identical across runs and across the Python/R clients
again <- verity_compare("impressed", "breech_a.x3p", "breech_b.x3p", include = "recipe")
stopifnot(identical(again$handle, report$handle))
```

## What the handle proves

The handle is `sha256:` over the canonical recipe — inputs, scorer config, reference, and
result. Two runs that produce the same handle are the same computation on the same scans;
a different engine version, a changed parameter, or a different scan changes it. It is the
reproducibility contract for a reported likelihood ratio.
