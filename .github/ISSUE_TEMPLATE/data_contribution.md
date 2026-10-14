---
name: Data contribution
about: Propose or contribute a forensic scan dataset, reference bundle, or study
title: "[data] "
labels: data
assignees: ''
---

<!--
Forensic datasets and open surface metrology are core to Verity.
Use this template to propose or share new 3D surface scans (X3P), reference
materials, or comparison studies with the platform.
-->

## Dataset summary

A brief overview of the dataset: what surfaces were scanned, under what research
or operational context, and what hypothesis or comparison they support.

## Data provenance & acquisition

- **Originating institution / laboratory**:
- **Study / project reference** (DOI, paper citation, NBTRD study id, if any):
- **Instrument(s)**: make, model, objective, acquisition mode (e.g. Sensofar S neox confocal, Leica DCM8, etc.)
- **Resolution**:
  - Lateral sampling (X/Y increment in µm):
  - Vertical resolution / noise floor (in nm/µm):
- **Surface / mark type**:
  - [ ] Bullet land (striated / 2D profile / 3D topography)
  - [ ] Cartridge breech face (impressed)
  - [ ] Firing pin impression
  - [ ] Toolmark / chisel / screwdriver
  - [ ] Other:

## Format & metadata compliance

- **File format**: (Native X3P ISO 25178-72 / other)
- **Known ground truth**: (Known matches / non-matches, barrel/firearm identifiers, ammunition type, shot order)
- **Metadata fields included**: (Operator, date, instrument serial, lighting/sensor settings)

## Licensing & permissions

- [ ] The data is publicly shareable under an open license (e.g. CC0, CC-BY 4.0, or Open Data Commons)
- [ ] No restricted or identifiable case/evidentiary constraints apply
- **License / Terms**:

## Proposed scope in Verity

- [ ] New study in data catalog (`services/catalog`)
- [ ] Inclusion in validation benchmark / calibration fold
- [ ] Regression test fixture for `crates/verity-x3p` or `services/engine`
- [ ] Other:

## Links or sample files

Link to download location, sample scan URLs, or repository.
