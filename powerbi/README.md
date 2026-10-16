# Power BI model and report

Everything needed to build the Power BI semantic model and report on top of the exported star schema.
The model is defined **as code** in this folder; the `.pbix` is built from it in Power BI Desktop.

| Folder / file | What it is |
|---|---|
| `power_query/*.pq` | Power Query (M) for every table, the three parameters and the `fnLoadExport` loader function |
| `dax/measures.dax` | 64 DAX measures with display folders and format strings |
| `tmdl/model.tmdl` | Whole model (tables, columns, relationships, measures, RLS roles) as a TMDL `createOrReplace` script |
| `theme/yeg311_theme.json` | Report theme (colours, fonts, visual defaults) |
| `dashboard_spec.md` | Page-by-page report design: visuals, fields, layout, interactions |
| `rls/security_ward_users.csv` | Sample mapping for the dynamic row-level-security role |

All of these are generated from one spec (`scripts/powerbi_model_spec.py`) by `python scripts/build_powerbi_assets.py`,
so the data dictionary, the M scripts, the DAX and the TMDL can never drift apart.

## Prerequisites

* Power BI Desktop (free, Windows). Macs: run Windows in Parallels/UTM or a cloud VM; nothing here needs a Power BI account.
* Data: either the published GitHub Release (default, nothing to download) or a local `data/exports` folder from `yeg311 export`.

## Path A: build the model from the TMDL script (fastest)

1. Open Power BI Desktop, create a blank report.
2. `File > Options and settings > Options > Preview features`: enable **TMDL view** (skip if already available).
3. Open the **TMDL view** tab, paste the contents of `tmdl/model.tmdl` into the script pane and click **Apply**.
   Every table, relationship, measure and role is created in one go.
4. Set the three parameters (`Home > Transform data > Edit parameters`):
   * `DataSourceMode`: `GitHub Release` (refreshes from the Release assets) or `Local Folder`.
   * `GitHubReleaseBaseUrl`: `https://github.com/<you>/edmonton-311-analytics/releases/download/data-latest/`
   * `LocalExportFolder`: full path to `data/exports` if using the local option.
5. `Home > Refresh`. First refresh asks for credentials: choose **Anonymous** for the GitHub URL (public repo).
6. `Modeling > Mark as date table` on `Dim Date` using `Date` (if the script did not already do it).
7. `View > Themes > Browse for themes` and pick `theme/yeg311_theme.json`.
8. Build the pages following `dashboard_spec.md`.

If Desktop rejects part of the script (TMDL support still evolves between releases), fall back to Path B for
that part only; the M and DAX files are the same definitions in copy-paste form.

## Path B: manual build (always works)

1. **Parameters** `Home > Transform data > Manage parameters > New parameter` for `DataSourceMode`, `GitHubReleaseBaseUrl`, `LocalExportFolder`
   (values in `power_query/Parameter - *.pq`).
2. **Loader function** `Get data > Blank query`, open the Advanced Editor, paste `power_query/fnLoadExport.pq`, name it `fnLoadExport`.
3. **Tables** repeat for each `power_query/<Table>.pq` (blank query, Advanced Editor, paste, rename the query to the table name).
   Load `Security Ward Users` only if you want the dynamic RLS role.
4. **Close & Apply**, then in Model view create the relationships listed in `docs/data_dictionary.md`
   (all many-to-one, single direction; `Closed Date Key -> Date Key` set to inactive).
5. **Measures** create an empty table `_Measures` (Enter data, one blank column, hide the column) and add each measure
   from `dax/measures.dax`; set the format string and display folder noted above each measure.
6. **Date table** `Modeling > Mark as date table` -> `Dim Date[Date]`. Set *Sort by column* for Month Name, Day Name, Season, Month Year, Quarter Name.
7. **RLS** `Modeling > Manage roles`: create the roles with the filters in `tmdl/model.tmdl` (section `role`).
8. Theme, then pages as in `dashboard_spec.md`.

## Refresh options

| Mode | How it refreshes | Best for |
|---|---|---|
| GitHub Release | `Web.Contents` reads the Parquet assets the weekly workflow uploads | Sharing the `.pbix`; anyone can refresh without the repo |
| Local Folder | `File.Contents` reads `data/exports` | Development, offline work |
| Power BI Service | Publish the `.pbix`; with the GitHub mode it needs no gateway (web source, anonymous) | Scheduled refresh, dashboards, apps |

## Checklist before committing the `.pbix`

* Visuals use measures only (no implicit aggregations).
* Slicers synced across pages, date slicer defaults to the last 12 months (relative date filter).
* `Is Unknown = FALSE` filter on every map.
* Screenshots of each page saved to `docs/img/` and linked from the main README.
* `.pbix` saved as `powerbi/Edmonton 311 Analytics.pbix` (keep it under 100 MB; drop `Created At`/`Closed At` from the import if needed).
