# Open-data coverage check for Abha -- what we can fetch ourselves vs. what still needs ASDA

**Date:** 2026-08-10/11
**Status:** research + fetch scripts done and tested against real data for Abha's exact
neighborhood point (18.2264426, 42.5053914 -- Jory's Google-Maps-verified point, same one
`configs/city_madina_abha.yaml` already uses). **No large download run** (WorldPop, ~10MB) --
holding for explicit go-ahead. Nothing wired into `StreetNetworkEnv`/configs yet -- these are
extra layers for a written case study, not (yet) env inputs.

Every number below is a live query result against this exact point, not a general claim that
"OSM has this tag somewhere." Same caution as the Al Olaya commercial-core / 0-residential-
buildings case in `configs/city_madina.yaml` -- radius and location change what's actually there.

## What has a real, working open source

| item | source | status at Abha's point | notes |
|---|---|---|---|
| Schools | OSM `amenity=school` | **4** @ r=1000m | 2 @ 250m, 3 @ 500m -- thin close in, real |
| Mosques | OSM `amenity=place_of_worship` | **6** @ r=1000m | 1 @ 250m, 4 @ 500m |
| Hospitals | OSM `amenity=hospital` | **1** @ r=1000m, 2 @ r=2000m | **0 at 250/500m** -- need >=1km, not a bug |
| Clinics | OSM `amenity=clinic` | **1** @ r=1000m | 0 @ 250m |
| Road classification | OSM `highway=*` | 1208 edges @ r=1000m (drive network) | every edge tagged, this part is NOT missing |
| Elevation | Open Topo Data public SRTM API (no key) | **2225m at the center point**, 2194-2275m / 81m relief across a 1km-radius grid (137 pts) | verified live, not assumed |
| Population (coarse) | WorldPop Saudi Arabia raster, direct HTTPS, no login | confirmed downloadable (~10MB, 1km-aggregated) | **not downloaded yet -- needs a go/no-go** |
| Population (city totals) | GASTAT 2022 census, via public reporting | Asir region 2,024,285; Abha city 334,290; Abha Governorate 422,243 | citable context number, not a spatial layer -- see caveat below |

## What's confirmed genuinely absent, not a query bug

| item | tags tried | result |
|---|---|---|
| Traffic signals | `highway=traffic_signals` | **0 features up to r=2000m** (250/500/1000/2000m all checked) |
| Government buildings/offices | `office=government`, `amenity=townhall`, `building=government` | **0 at r<=1000m.** `office=government` found **1** at r=2000m; the other two tags stayed at 0 even there |
| Lane counts | `lanes=` on road edges | 0/160 (r=250 walk net), 0/685 (r=500 walk net), 8/1208 (r=1000 drive net, 0.66%) |

Read honestly: this specific point is a residential neighborhood. Traffic signals and government
buildings cluster on Abha's arterial roads and administrative core, which this point's own
road-hierarchy check shows it barely touches (0 primary-road edges at r=250m, still only a
handful at r=1000m). A different, more central Abha point would likely find these -- not tested,
out of scope here since the project's existing scenarios (Al Nakheel, Jeddah) are all
neighborhood-scale, and switching to a commercial-core point risks repeating the Al Olaya
0-residential-buildings problem in the other direction. Lane counts are the one item that looks
like a genuine, radius-independent OSM data gap for this whole area, not a location choice issue.

## Scripts built and tested (Phase 2)

- **`scripts/fetch_pois.py`** -- schools/hospitals/clinics/mosques/traffic_signals/government as
  separate geojson layers, plus `road_hierarchy.geojson` (streets with `highway`+`lanes`
  attributes, which `fetch_osm_data.py` currently drops). Tested end-to-end against Abha's point
  (`data/raw/abha_pois/`, r=1000m) -- output matches the table above. One real bug found and fixed
  during testing: the first version computed POI centroids directly in WGS84 degrees (geopandas
  warns this is measurably wrong); fixed to project to UTM 38N first, matching
  `fetch_osm_data.py`'s existing pattern for building centroids.
- **`scripts/fetch_terrain.py`** -- Open Topo Data SRTM30m point API, grid-sampled over the study
  area, no API key. Tested end-to-end (`data/raw/abha_terrain/`, r=1000m, 100m spacing) -- 137
  points, 2194-2275m range. Respects the API's 1-call/sec and warns if a run would approach the
  1000-calls/day free-tier cap.
- **`scripts/fetch_population.py`** -- downloads (once, cached) WorldPop's ~10MB Saudi Arabia
  1km-aggregated raster and clips it to the study area. A windowed *remote* read (no download at
  all, via `rasterio`'s `/vsicurl/`) was tried first to avoid the download entirely -- confirmed
  **not** to work: the server advertises `Accept-Ranges: bytes` but GDAL's actual range request
  fails with "Range downloading not supported by this server". Download-then-clip was the
  fallback. **Run** against Abha's point (10.2MB downloaded once, cached under
  `data/raw/_worldpop_cache/`): clipped to `data/raw/abha_population/population.geojson`, 4 grid
  cells at r=1000m, estimated population in the clipped window ~827. Confirms the 1km-resolution
  caveat in practice -- a small neighborhood radius really does only resolve to a handful of
  cells, useful as a coarse density check, not per-street granularity.

`rasterio` was added to the `snrl` conda env for this (not yet in `requirements.txt`/
`environment.yml` -- add it there if `fetch_population.py` is kept).

## GASTAT / official statistics -- partial, and honestly mixed

- **stats.gov.sa** exists and links to an Open Data Platform (`open.data.gov.sa`) and a
  Statistical Database (`database.stats.gov.sa`). **Both rejected automated access** -- confirmed
  via WebFetch *and* a real rendered browser, both got a WAF-level "Request Rejected" page, not a
  content-level 404. This is a genuine access barrier for automation, not a tooling gap on our
  side; would need a human to browse it interactively.
- **City/region population totals ARE findable**, just not as a downloadable dataset: 2022 census
  figures for Asir region (2,024,285), Abha city (334,290), and Abha Governorate (422,243),
  sourced to GASTAT via public secondary reporting (Wikipedia's citation chain). Useful as a
  sanity-check number (e.g. "does our residential-building resident estimate roughly match Abha's
  known population"), not as a spatial/granular layer.
- **A promising-looking open dataset turned out to be a dead end.** RCRC ("Royal Commission for
  Riyadh City") hosts `opendata.rcrc.gov.sa`, including a dataset literally named "Population by
  age, citizenship, gender **and governorate** (2022)" -- title suggests full national coverage.
  Queried its real API directly (not just the landing page): confirmed **Riyadh-region only**.
  Querying for Abha/Asir returns 0 hits; the dataset's own region facet only offers `Ar Riyadh`,
  `Others (not Ar Riyadh Region)`, and a KSA-wide total -- Asir is folded into an undifferentiated
  "Others" bucket. Worth knowing so nobody re-discovers this same dead end later.
- **GASTAT does publish quarterly Tourism Establishment Statistics bulletins** (real, on
  stats.gov.sa, e.g. Q1 2025: 63% hotel occupancy, 983,253 tourism employees) -- confirmed
  **national-level only**, no regional breakdown, no linked downloadable microdata. GASTAT does
  offer a formal "Request Statistical Information" service
  (stats.gov.sa/en/request-statistical-information) for region-level breakdowns -- functionally
  similar to needing ASDA: a request to an external body, not something fetchable now.

## Still genuinely needs ASDA (no public/open substitute found)

- **Built-but-currently-closed roads** -- physical street/segment closure status isn't tracked by
  OSM (OSM records what a street *is*, not administrative closure orders) or by any dataset found
  above. This is exactly the kind of ground-truth-vs-map discrepancy only a local authority would
  have.
- **Accident/collision data** -- not researched in depth this pass (out of the time available);
  no Saudi open traffic-accident dataset is known to exist publicly. Flagging as "likely needs
  ASDA/Ministry of Interior traffic police data," not confirmed absent the way traffic_signals/
  government buildings were confirmed absent above -- worth a dedicated search pass if this
  becomes a priority.
- **Origin-destination (OD) travel survey** -- inherently primary survey data; no public
  substitute exists or was expected to.
- **Intervention cost estimates** (cost of a pedestrianization scheme, closure infrastructure,
  etc.) -- economic/engineering estimates, not a spatial dataset; would come from ASDA or a
  municipal budget/planning document, not an open geodata source.
- **Region-level tourism/population breakdowns from GASTAT specifically** -- see above: the data
  exists in aggregate (national bulletins, city/region census totals) but not broken down to
  Asir/Abha in any publicly downloadable form found. GASTAT's own "Request Statistical
  Information" channel is the closest thing to a substitute, and it is itself an external-body
  request, not an open-data fetch.
