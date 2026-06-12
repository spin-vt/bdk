# BDC filing windows & the CostQuest fabric delivery format

Interop reference for the code that handles FCC Broadband Data Collection
(BDC) filing cadence and CostQuest Associates (CQA) Broadband Serviceable
Location Fabric deliveries: `services/filing_windows.py`,
`services/fabric_intake.py`, `services/fabric_service.py`, and the fabric
ingestion in `controllers/database_controller/`.

## BDC filing windows

Everything in the BDC process is referred to by its "data as of" date, except
the fabric, which goes by version number:

- data as of **June 30** of year Y → filing due the following **September 1**
- data as of **December 31** of year Y → filing due the following **March 1**
- due dates falling on a weekend roll to the next business day
  (e.g. March 1, 2026 was a Sunday → due March 2, 2026)
- fabric versions count up one per window from **v1 = June 2022**:
  `version = 2*(year − 2022) + (1 if June else 2)` — so v2 = Dec 2022,
  v8 = Dec 2025, v9 = Jun 2026, v10 = Dec 2026.

## Delivery shape

- A delivery is a zip whose **own filename is an opaque license key** — it
  carries no role or vintage information. The **inner CSV filenames are the
  reliable signal**.
- Current-era inner files (one per role):
  - `FCC_Active_BSL_<MMDDYYYY>_rel_<N>.csv` — all `bsl_flag=TRUE` records for
    the licensed counties (whole counties; records beyond the service area are
    expected). This is the fabric proper that drives coverage computation.
  - `FCC_Active_NoBSL_<MMDDYYYY>_rel_<N>.csv` — all `bsl_flag=FALSE` records
    (hospitals, schools, ...). Optional at intake; stored and rendered, never
    exported as served.
  - `FCC_Supplemental_<MMDDYYYY>_rel_<N>.csv` — extra addresses per
    `location_id`. Optional at intake; feeds address search only, never
    computation or export.
- Filename pattern: `FCC_<role>_<MMDDYYYY>_rel_<N>[_<M>].csv` where MMDDYYYY is
  the **data-as-of date** and N the **fabric version**; `_rel_N_M` marks a
  **revised release** mid-window (these have really shipped — which is why
  mid-filing fabric replacement is supported).

## Naming/format history (the intake tolerates all of it)

- **v1 (Jun 2022):** two files — `FCC_Active_<MMDDYYYY>_ver`,
  `FCC_Secondary_<MMDDYYYY>_ver`.
- **v2 (Dec 2022):** Active split into `FCC_Active_BSL_…` +
  `FCC_Active_NoBSL_…`; suffix style `verX`.
- **v3 (Jun 2023):** `fcc_rel` column added (only present for tier 2/3/4
  licensees — don't rely on it existing). A revised release (`_rel_3_2`)
  shipped this window.
- **v6 (Dec 2024):** "Secondary" renamed **"Supplemental"** (the file and the
  `primary_secondary` → `primary_supplemental` column).
- **v8 (Dec 2025):** suffix style `rel_8`. Format otherwise stable since ~v2.

`location_id` is persistent across versions *most* of the time but can change
(records that cycle out and return may get a new id) — the basis for the
"wrong vintage → location IDs won't line up" warning at intake.

## Schemas

**Active_BSL / Active_NoBSL (identical columns):** `location_id` (int, unique
key), `address_primary`, `city`, `state`, `zip`, `zip_suffix`, `unit_count`,
`bsl_flag` (TRUE/FALSE — constant per file), `building_type_code`,
`land_use_code`, `address_confidence_code`, `county_geoid` (5-digit FIPS),
`block_geoid` (15-digit FIPS), `h3_9`, `latitude`/`longitude` (WGS84),
`fcc_rel` (when present).

**Supplemental:** `location_id`, `address_id` + `parcel_id` (not persistent
across releases), `address_confidence_code`, parsed address parts
(`address_range`, `pre_direction`, `street_name`, `suffix`, `post_direction`),
`primary_supplemental` (P/S — exactly one P row per active location, mirroring
its primary address, plus S rows), `address`, `city`, `state`, `zip`,
`zip_suffix`, `address_source`, `fcc_rel`. **No `county_geoid`** — joining
goes through `location_id`. The CSV has no coordinates; they come from the
location's Active record.

Mapping to the `fabric_data` model is 1:1 except CSV `zip` → model `zip_code`,
and CSV `county_geoid` → model `country_geoid` (a pre-existing column-name typo
kept for schema stability).

## CSV dialect

- Header rows fully quoted; data rows quote only string-ish fields
  (`location_id`, `unit_count`, `land_use_code`, `latitude`, `longitude` are
  bare). RFC-4180 doubled quotes; embedded `\r\n` inside quoted fields occurs.
  Parsers must be dialect-tolerant, and anything that round-trips rows cannot
  re-serialize through one fixed csv dialect and stay byte-identical — copy
  raw bytes.
- CRLF line endings, UTF-8 without BOM, comma-delimited.

## Intake detection strategy

1. **Filename** regex over inner names: role (`Active_BSL` | `Active_NoBSL` |
   `Supplemental`/`Secondary` | bare `Active`), data-as-of `MMDDYYYY`, release
   `N[_M]`. The vintage check compares the data-as-of date against the filing
   window's expected fabric version (hard warning, user-overridable).
2. **Content sniff fallback** (loose/renamed files): the header set
   distinguishes Active (`address_primary`, `bsl_flag`) from Supplemental
   (`primary_supplemental`/`primary_secondary`, `address_id`); the first data
   row's `bsl_flag` splits BSL from NoBSL. A sniffed file has no detectable
   vintage, which counts as a vintage mismatch (overridable).
3. Whole-zip or individual CSVs are accepted; `Active_NoBSL` and
   `Supplemental` are optional.
