# Report specification: Edmonton 311 Service Request Analytics

Five report pages, 16:9 canvas (1280 x 720), theme `theme/yeg311_theme.json`.
Every page carries the same slicer bar on the left (Date range, Service Group, Ward, Channel Group) and a
`[Data As Of Label]` card in the top-right corner so viewers always know the freshness of what they see.

Design rules used throughout:

* One question per page, stated in the page subtitle, answered by the first visual the eye lands on.
* Measures only (no implicit sums). Every number traces back to `dax/measures.dax`.
* Category colours are fixed by the theme; red/amber/green appears only for SLA status.
* Tooltips carry the secondary detail so the canvas stays uncluttered.

---

## Page 1 - Executive Overview

**Question:** What is 311 handling, how fast, and is it getting better or worse?

```
+---------------------------------------------------------------------------------------------+
| Slicers | Total Requests | Service Requests | Open Service Req. | Median Res. | SLA Attain.  |
| (left)  |  [#,0] + YoY%  |  [#,0] + YoY%    |  [Backlog EoP]    |  days       |  % + status  |
|         +------------------------------------------------------+---------------------------+
|         | Monthly trend: Total Requests vs Service Requests    | Top 10 Service Categories |
|         | (line, Month Year on axis, Rolling 3M Avg dashed)    | (bar, Service Requests)   |
|         +------------------------------------------------------+---------------------------+
|         | Channel mix (donut, Channel)   | Requests by Ward (filled map / bar, Service Req.) |
+---------------------------------------------------------------------------------------------+
```

| Visual | Type | Fields / measures | Notes |
|---|---|---|---|
| KPI cards x5 | Card (new) | `[Total Requests]`, `[Service Requests]`, `[Backlog (End of Period)]`, `[Median Resolution Days]`, `[SLA Attainment %]` | Reference labels: `[Requests YoY %]`, `[Service Requests YoY %]`, `[Backlog Change vs Prior Month]`, `[SLA Status]` |
| Monthly trend | Line chart | X: `Dim Date[Month Year]` (sorted by Year Month Key); Y: `[Total Requests]`, `[Service Requests]`, `[Requests Rolling 3M Avg]` | Rolling average as dashed line (Format > Lines > style) |
| Top categories | Clustered bar | Axis: `Dim Service[Service Category]`; Value: `[Service Requests]`; Tooltip: `[Median Resolution Days]`, `[SLA Attainment %]` | Filter on visual: Top N = 10 by `[Service Requests]` |
| Channel mix | Donut | Legend: `Dim Intake[Channel]`; Value: `[Total Requests]` | Detail label shows `[Mobile App Share %]` in a card next to it |
| Ward map | Map (bubble) or Filled map | Location: `Dim Neighbourhood[Ward]`, Latitude/Longitude: `Ward Latitude`/`Ward Longitude`; Size: `[Service Requests]` | Exclude `Is Unknown = TRUE` with a visual-level filter |
| Title | Text box / card | `[Overview Title]` | Dynamic, follows the date slicer |

---

## Page 2 - Operations and SLA

**Question:** Which business areas are meeting their response targets, and where is the backlog ageing?

```
+---------------------------------------------------------------------------------------------+
| Slicers | SLA Attainment by Service Area (bar + goal line 85%)   | SLA Met / Missed (stacked |
|         |                                                        | column by Month Year)     |
|         +--------------------------------------------------------+---------------------------+
|         | Resolution time distribution (column, Resolution Bucket)| Backlog ageing (stacked   |
|         |                                                        | bar, Backlog Age Bucket)  |
|         +--------------------------------------------------------+---------------------------+
|         | Table: Service Category | Service Req. | Open | Median | P90 | SLA % | Rank         |
+---------------------------------------------------------------------------------------------+
```

| Visual | Type | Fields / measures | Notes |
|---|---|---|---|
| SLA by area | Clustered bar | Axis: `Dim Service[Service Area]`; Value: `[SLA Attainment %]`; Constant line: `[SLA Attainment Goal %]` (0.85) | Conditional colour: `[SLA Status]` -> On goal green, Watch amber, Below goal red |
| SLA trend | Stacked column | X: `Month Year`; Y: `[SLA Met]`, `[SLA Missed]` | Add `[SLA Attainment %]` as a line on the secondary axis |
| Resolution distribution | Column | X: `Fact Service Request[Resolution Bucket]` (custom sort via a small sort table or by renaming with prefixes); Y: `[Closed Requests]` filtered to service requests | Tooltip `[Resolved Within 7 Days %]` |
| Backlog ageing | Stacked bar | Axis: `Dim Service[Service Group]`; Legend: `Fact Service Request[Backlog Age Bucket]`; Value: `[Open Service Requests]` | Shows where the 90+ day work sits |
| Operations table | Table | `Service Category`, `[Service Requests]`, `[Open Service Requests]`, `[Median Resolution Days]`, `[P90 Resolution Days]`, `[SLA Attainment %]`, `[Category Rank]` | Data bars on SLA %, conditional icon on `[SLA Status]` |

SLA targets are **illustrative** (seeds/sla_targets.csv) and are surfaced in the tooltip through
`[SLA Target Days (Selected)]` and `Dim Service[SLA Basis]`, so nobody mistakes them for official City standards.

---

## Page 3 - Neighbourhoods and Wards

**Question:** Where do service requests come from, and what does each area ask for?

```
+---------------------------------------------------------------------------------------------+
| Slicers | Neighbourhood bubble map (Latitude / Longitude, size = Service Requests)          |
|         |                                                        +--------------------------+
|         |                                                        | Ward comparison (bar,     |
|         |                                                        | Service Requests, YoY %)  |
|         +--------------------------------------------------------+--------------------------+
|         | Top 15 neighbourhoods (table with rank, top category)  | Matrix: Ward x Service    |
|         |                                                        | Group (heatmap colouring) |
+---------------------------------------------------------------------------------------------+
```

| Visual | Type | Fields / measures | Notes |
|---|---|---|---|
| Neighbourhood map | Map | Latitude / Longitude from `Dim Neighbourhood`; Size `[Service Requests]`; Tooltip `[Top Service Category]`, `[Median Resolution Days]` | Filter `Is Unknown = FALSE` |
| Ward bars | Clustered bar | Axis `Ward`; Value `[Service Requests]`; Tooltip `[Service Requests YoY %]` | |
| Neighbourhood table | Table | `Neighbourhood`, `Ward`, `[Service Requests]`, `[Neighbourhood Rank]`, `[Top Service Category]`, `[SLA Attainment %]` | Top N 15 by `[Service Requests]`; drill-through target: page 5 detail |
| Ward x group matrix | Matrix | Rows `Ward`; Columns `Service Group`; Values `[Service Requests % of Total]` | Background colour scale (theme minimum -> maximum) |

Add a **drill-through page** "Neighbourhood detail" (hidden) with the monthly trend, category breakdown and open
backlog for the selected neighbourhood. Drill-through field: `Dim Neighbourhood[Neighbourhood]`.

---

## Page 4 - Seasonality and Channels

**Question:** When does demand arrive, and how are residents choosing to contact the City?

```
+---------------------------------------------------------------------------------------------+
| Slicers | Heatmap matrix: Service Group x Month Name (Requests per Day)                       |
|         +--------------------------------------------------------+---------------------------+
|         | Intake heatmap: Day Name x Created Hour (Total Req.)   | Channel adoption trend    |
|         |                                                        | (line: Mobile App Share %,|
|         |                                                        |  Digital Share %, by Qtr) |
|         +--------------------------------------------------------+---------------------------+
|         | Requests per Day by Day Type (Business day / Weekend / Holiday)  | Season cards     |
+---------------------------------------------------------------------------------------------+
```

| Visual | Type | Fields / measures | Notes |
|---|---|---|---|
| Seasonality matrix | Matrix | Rows `Service Group`; Columns `Month Name`; Values `[Requests per Day]` | Per-row colour scale; potholes spike in spring, snow/ice in winter |
| Intake heatmap | Matrix | Rows `Day Name`; Columns `Fact Service Request[Created Hour]`; Values `[Total Requests]` | Shows the 311 call-centre curve (opens 7 am) |
| Channel adoption | Line | X `Year Quarter`; Y `[Mobile App Share %]`, `[Digital Share %]`, `[Phone Share %]` | |
| Day type | Clustered column | X `Day Type`; Y `[Requests per Day]` | Holiday vs business-day volume |
| Season cards | Cards | `[Service Requests]` with `Season` slicer / small multiples | |

---

## Page 5 - Data Quality and Pipeline

**Question:** Can this data be trusted today?

| Visual | Type | Fields / measures | Notes |
|---|---|---|---|
| Status cards | Cards | `[DQ Status]`, `[DQ Checks Passed]` of `[DQ Checks Total]`, `[Pipeline Built At (UTC)]`, `[Pipeline Version]`, `[Fact Rows (Build)]` | Colour `[DQ Status]` via conditional formatting (PASS green, WARN amber, FAIL red) |
| Check table | Table | `Data Quality[Check]`, `Description`, `Severity`, `Value`, `Threshold`, `Unit`, `Passed` | Icon set on `Passed` |
| Build info | Table | `Build Info[Key]`, `Value` | Row counts by layer, as-of timestamp, git SHA |
| Freshness | Card | `[Data As Of Label]` | |

---

## Model-wide settings

* **Date table:** mark `Dim Date` as the date table using `Date`.
* **Sort by column:** Month Name -> Month, Day Name -> Day Of Week, Season -> Season Sort, Month Year -> Year Month Key, Quarter Name -> Quarter.
* **Hidden:** all key columns, `Fact Service Request[Created At]`/`[Closed At]` (expose through measures), `Security Ward Users`.
* **Relationships:** see `docs/data_dictionary.md`. The `Closed Date Key` relationship is inactive and used by `[Closed by Close Date]`.
* **Row-level security:** two roles in `tmdl/model.tmdl` (static ward example and dynamic `USERPRINCIPALNAME()` lookup against `Security Ward Users`). Test with *Modeling > View as*.
* **Field parameters (optional):** create a field parameter "Analyse by" containing `Service Group`, `Service Area`, `Service Category`, `Ward`, `Channel` to let users re-slice the top-N bar on page 1 without extra visuals.
* **Bookmarks (optional):** "Service requests only" (slicer `Is Service Request = TRUE`) and "Everything" toggled by buttons.
* **Performance:** `Fact Service Request` is ~3.5M rows; keep `Created At`/`Closed At` at second precision only if needed (or remove them from the import and rely on the date keys) to reduce the model size.
