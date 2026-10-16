"""Single source of truth for the Power BI semantic model.

``scripts/build_powerbi_assets.py`` renders this spec into:
  * powerbi/power_query/*.pq      Power Query (M) scripts, one per table + parameters + loader
  * powerbi/dax/measures.dax      every measure with folder + format string
  * powerbi/tmdl/model.tmdl       a TMDL "createOrReplace" script (tables, relationships, measures, RLS)
  * docs/data_dictionary.md       column-level documentation of the exported star schema

Column tuples: (source_name, friendly_name, m_type, tmdl_type, description, options)
options keys: hidden, summarize ("none"|"sum"|"count"), format, sort_by, category ("Latitude"|"Longitude"), key
"""

from __future__ import annotations

GITHUB_OWNER = "bl4ck0uc4st"
GITHUB_REPO = "edmonton-311-analytics"
RELEASE_TAG = "data-latest"
RELEASE_BASE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/"

INT = ("Int64.Type", "int64")
TXT = ("type text", "string")
DT = ("type datetime", "dateTime")
DATE = ("type date", "dateTime")
BOOL = ("type logical", "boolean")
DBL = ("type number", "double")


def col(source, friendly, kind, description, **opts):
    m_type, tmdl_type = kind
    return (source, friendly, m_type, tmdl_type, description, opts)


TABLES: list[dict] = [
    {
        "name": "Dim Date",
        "export": "dim_date",
        "description": "Calendar dimension (one row per day). Marked as the date table; drives all time intelligence.",
        "is_date_table": True,
        "columns": [
            col(
                "date_key",
                "Date Key",
                INT,
                "Surrogate key yyyymmdd, joins to fact tables",
                hidden=True,
                key=True,
            ),
            col("date", "Date", DATE, "Calendar date", format="yyyy-mm-dd", key=True),
            col("year", "Year", INT, "Calendar year"),
            col("quarter", "Quarter", INT, "Quarter number 1-4", hidden=True),
            col("quarter_name", "Quarter Name", TXT, "Q1..Q4", sort_by="Quarter"),
            col("year_quarter", "Year Quarter", TXT, "e.g. 2026 Q3"),
            col("month", "Month", INT, "Month number 1-12", hidden=True),
            col("month_name", "Month Name", TXT, "Full month name", sort_by="Month"),
            col("month_short", "Month Short", TXT, "Three-letter month", sort_by="Month"),
            col("year_month_key", "Year Month Key", INT, "yyyymm integer for sorting", hidden=True),
            col("year_month", "Year Month", TXT, "yyyy-mm text", sort_by="Year Month Key"),
            col(
                "month_year_label",
                "Month Year",
                TXT,
                "e.g. Oct 2026 (chart axis label)",
                sort_by="Year Month Key",
            ),
            col("day", "Day", INT, "Day of month"),
            col("day_of_week", "Day Of Week", INT, "ISO weekday 1=Monday..7=Sunday", hidden=True),
            col("day_name", "Day Name", TXT, "Weekday name", sort_by="Day Of Week"),
            col("day_short", "Day Short", TXT, "Three-letter weekday", sort_by="Day Of Week"),
            col("is_weekend", "Is Weekend", BOOL, "Saturday or Sunday"),
            col("iso_week", "ISO Week", INT, "ISO week number"),
            col("season", "Season", TXT, "Winter (Dec-Feb), Spring, Summer, Fall", sort_by="Season Sort"),
            col("season_sort", "Season Sort", INT, "Season ordering 1-4", hidden=True),
            col("is_holiday", "Is Holiday", BOOL, "Alberta statutory holiday"),
            col("holiday_name", "Holiday Name", TXT, "Holiday name when applicable"),
            col("day_type", "Day Type", TXT, "Business day / Weekend / Holiday"),
        ],
    },
    {
        "name": "Dim Service",
        "export": "dim_service",
        "description": "Service hierarchy: Service Group > Service Area > Service Category > Service Description, plus illustrative SLA targets.",
        "columns": [
            col("service_key", "Service Key", INT, "Surrogate key", hidden=True, key=True),
            col("service_area", "Service Area", TXT, "City business area responsible for the request"),
            col(
                "service_category",
                "Service Category",
                TXT,
                "Type of request (e.g. Potholes, Bylaw Complaints)",
            ),
            col("service_description", "Service Description", TXT, "Most detailed request description"),
            col(
                "service_group",
                "Service Group",
                TXT,
                "Analyst roll-up of service areas (seeds/service_groups.csv)",
            ),
            col("area_category", "Area / Category", TXT, "Area and category concatenated for labels"),
            col(
                "sla_target_days",
                "SLA Target Days",
                INT,
                "Illustrative response target in days (seeds/sla_targets.csv)",
                summarize="none",
            ),
            col(
                "sla_basis",
                "SLA Basis",
                TXT,
                "Where the target came from (exact / area default / global default)",
            ),
            col("is_informational", "Is Informational", BOOL, "True for information-only call types"),
        ],
    },
    {
        "name": "Dim Neighbourhood",
        "export": "dim_neighbourhood",
        "description": "Edmonton neighbourhoods with ward roll-up and centroid coordinates (the finest geography the source publishes).",
        "columns": [
            col(
                "neighbourhood_key",
                "Neighbourhood Key",
                INT,
                "Surrogate key (= neighbourhood id, -1 = Unknown)",
                hidden=True,
                key=True,
            ),
            col(
                "neighbourhood_id",
                "Neighbourhood ID",
                INT,
                "City of Edmonton neighbourhood number",
                hidden=True,
            ),
            col("neighbourhood_name", "Neighbourhood", TXT, "Neighbourhood name (title case)"),
            col(
                "neighbourhood_name_source",
                "Neighbourhood (Source)",
                TXT,
                "Name exactly as published (upper case)",
                hidden=True,
            ),
            col("ward", "Ward", TXT, "2021 City of Edmonton ward (Indigenous names)"),
            col(
                "nbhd_latitude",
                "Latitude",
                DBL,
                "Neighbourhood centroid latitude",
                category="Latitude",
                summarize="none",
            ),
            col(
                "nbhd_longitude",
                "Longitude",
                DBL,
                "Neighbourhood centroid longitude",
                category="Longitude",
                summarize="none",
            ),
            col(
                "ward_latitude",
                "Ward Latitude",
                DBL,
                "Ward centroid latitude",
                category="Latitude",
                summarize="none",
            ),
            col(
                "ward_longitude",
                "Ward Longitude",
                DBL,
                "Ward centroid longitude",
                category="Longitude",
                summarize="none",
            ),
            col("is_unknown_member", "Is Unknown", BOOL, "True for the Unknown placeholder member"),
        ],
    },
    {
        "name": "Dim Intake",
        "export": "dim_intake",
        "description": "How a request came in (channel) and whether it became a service request (referral type).",
        "columns": [
            col("intake_key", "Intake Key", INT, "Surrogate key", hidden=True, key=True),
            col("interaction_channel", "Channel", TXT, "Phone Call, Mobile App, Web Form, ESRI MAP, Email"),
            col(
                "referral_type",
                "Referral Type",
                TXT,
                "Full Service (answered at first contact) or Referral (sent to a business area)",
            ),
            col("channel_group", "Channel Group", TXT, "Digital vs Voice"),
            col("request_type", "Request Type", TXT, "Readable label for referral type"),
            col(
                "is_service_request",
                "Is Service Request",
                BOOL,
                "True when the request was referred to a business area",
            ),
        ],
    },
    {
        "name": "Dim Status",
        "export": "dim_status",
        "description": "Open/Closed plus the outcome detail recorded by the business area.",
        "columns": [
            col("status_key", "Status Key", INT, "Surrogate key", hidden=True, key=True),
            col("request_status", "Status", TXT, "Open or Closed"),
            col("status_detail", "Status Detail", TXT, "Outcome / progress note (Not specified when blank)"),
            col("is_closed_status", "Is Closed", BOOL, "True when Status = Closed"),
            col(
                "outcome_group",
                "Outcome Group",
                TXT,
                "Grouping of status details (Resolved, Duplicate, Redirected, ...)",
            ),
        ],
    },
    {
        "name": "Fact Service Request",
        "export": "fact_service_request",
        "description": "Transaction fact: one row per 311 request with timings, SLA evaluation and foreign keys.",
        "columns": [
            col("request_id", "Request ID", INT, "Source row id", hidden=True, key=True),
            col(
                "created_at",
                "Created At",
                DT,
                "Request creation timestamp (Edmonton local time)",
                hidden=True,
            ),
            col("closed_at", "Closed At", DT, "Close timestamp, blank while open", hidden=True),
            col(
                "created_date_key",
                "Created Date Key",
                INT,
                "FK to Dim Date (active relationship)",
                hidden=True,
            ),
            col(
                "closed_date_key",
                "Closed Date Key",
                INT,
                "FK to Dim Date (inactive relationship)",
                hidden=True,
            ),
            col(
                "created_hour",
                "Created Hour",
                INT,
                "Hour of day 0-23 the request was created",
                summarize="none",
            ),
            col("service_key", "Service Key", INT, "FK to Dim Service", hidden=True),
            col("neighbourhood_key", "Neighbourhood Key", INT, "FK to Dim Neighbourhood", hidden=True),
            col("intake_key", "Intake Key", INT, "FK to Dim Intake", hidden=True),
            col("status_key", "Status Key", INT, "FK to Dim Status", hidden=True),
            col("is_closed", "Is Closed", BOOL, "True when the request is closed"),
            col(
                "is_service_request",
                "Is Service Request",
                BOOL,
                "Denormalised from Dim Intake for fast filters",
            ),
            col(
                "resolution_hours", "Resolution Hours", DBL, "Hours from creation to close", summarize="none"
            ),
            col(
                "resolution_days",
                "Resolution Days",
                DBL,
                "Days from creation to close (fractional)",
                summarize="none",
            ),
            col(
                "resolution_calendar_days",
                "Resolution Calendar Days",
                INT,
                "Whole calendar days between create and close dates",
                summarize="none",
            ),
            col("sla_target_days", "SLA Target Days", INT, "Target applied to this request", hidden=True),
            col("sla_met", "SLA Met", BOOL, "True/False for closed service requests, blank otherwise"),
            col(
                "open_age_days",
                "Open Age Days",
                DBL,
                "Age of open requests as of the data as-of date",
                summarize="none",
            ),
            col(
                "backlog_age_bucket",
                "Backlog Age Bucket",
                TXT,
                "0-7 / 8-30 / 31-90 / 90+ days (open requests only)",
            ),
            col(
                "resolution_bucket",
                "Resolution Bucket",
                TXT,
                "Under 1 hour / Same day / 1-7 days / 8-30 / 31-90 / Over 90",
            ),
            col(
                "closed_before_created_flag",
                "Closed Before Created Flag",
                BOOL,
                "Source close timestamp preceded creation (rejected)",
                hidden=True,
            ),
            col(
                "request_count",
                "Request Count",
                INT,
                "Always 1; convenience column",
                hidden=True,
                summarize="sum",
            ),
        ],
    },
    {
        "name": "Fact Backlog Snapshot",
        "export": "fact_backlog_snapshot",
        "description": "Periodic snapshot: open service requests at the end of each day, by service.",
        "columns": [
            col("date_key", "Date Key", INT, "FK to Dim Date (snapshot day)", hidden=True),
            col("service_key", "Service Key", INT, "FK to Dim Service", hidden=True),
            col(
                "open_requests", "Open Requests", INT, "Service requests open at end of day", summarize="sum"
            ),
            col(
                "open_over_30_days", "Open Over 30 Days", INT, "Of which older than 30 days", summarize="sum"
            ),
            col(
                "open_over_90_days", "Open Over 90 Days", INT, "Of which older than 90 days", summarize="sum"
            ),
        ],
    },
    {
        "name": "Data Quality",
        "export": "quality_results",
        "description": "Results of the pipeline's data-quality checks for the loaded build.",
        "columns": [
            col("run_at_utc", "Run At (UTC)", TXT, "When the checks ran"),
            col("check_name", "Check", TXT, "Check identifier"),
            col("description", "Description", TXT, "What the check verifies"),
            col("severity", "Severity", TXT, "critical or warning"),
            col("value", "Value", DBL, "Measured value (failing rows, %, days)", summarize="none"),
            col("threshold", "Threshold", DBL, "Maximum acceptable value", summarize="none"),
            col("unit", "Unit", TXT, "rows / % / days"),
            col("passed", "Passed", BOOL, "True when value <= threshold"),
        ],
    },
    {
        "name": "Build Info",
        "export": "build_info",
        "description": "Key/value metadata about the warehouse build (version, timestamps, row counts).",
        "columns": [
            col("key", "Key", TXT, "Metadata key"),
            col("value", "Value", TXT, "Metadata value"),
        ],
    },
]

RELATIONSHIPS: list[dict] = [
    {"from": ("Fact Service Request", "Created Date Key"), "to": ("Dim Date", "Date Key"), "active": True},
    {"from": ("Fact Service Request", "Closed Date Key"), "to": ("Dim Date", "Date Key"), "active": False},
    {"from": ("Fact Service Request", "Service Key"), "to": ("Dim Service", "Service Key"), "active": True},
    {
        "from": ("Fact Service Request", "Neighbourhood Key"),
        "to": ("Dim Neighbourhood", "Neighbourhood Key"),
        "active": True,
    },
    {"from": ("Fact Service Request", "Intake Key"), "to": ("Dim Intake", "Intake Key"), "active": True},
    {"from": ("Fact Service Request", "Status Key"), "to": ("Dim Status", "Status Key"), "active": True},
    {"from": ("Fact Backlog Snapshot", "Date Key"), "to": ("Dim Date", "Date Key"), "active": True},
    {"from": ("Fact Backlog Snapshot", "Service Key"), "to": ("Dim Service", "Service Key"), "active": True},
]

# (name, folder, format string, DAX)
F = "'Fact Service Request'"
D = "'Dim Date'"
MEASURES: list[tuple[str, str, str, str]] = [
    # ---------------------------------------------------------------- Volume
    ("Total Requests", "1. Volume", "#,0", f"COUNTROWS ( {F} )"),
    (
        "Service Requests",
        "1. Volume",
        "#,0",
        "CALCULATE ( [Total Requests], 'Dim Intake'[Is Service Request] = TRUE () )",
    ),
    (
        "First-Contact Resolutions",
        "1. Volume",
        "#,0",
        "CALCULATE ( [Total Requests], 'Dim Intake'[Referral Type] = \"Full Service\" )",
    ),
    ("Service Request Share %", "1. Volume", "0.0%", "DIVIDE ( [Service Requests], [Total Requests] )"),
    ("Closed Requests", "1. Volume", "#,0", f"CALCULATE ( [Total Requests], {F}[Is Closed] = TRUE () )"),
    ("Open Requests", "1. Volume", "#,0", f"CALCULATE ( [Total Requests], {F}[Is Closed] = FALSE () )"),
    (
        "Open Service Requests",
        "1. Volume",
        "#,0",
        f"CALCULATE ( [Service Requests], {F}[Is Closed] = FALSE () )",
    ),
    ("Closure Rate %", "1. Volume", "0.0%", "DIVIDE ( [Closed Requests], [Total Requests] )"),
    (
        "First Data Date",
        "1. Volume",
        "yyyy-mm-dd",
        f"CALCULATE ( MIN ( {F}[Created At] ), REMOVEFILTERS () )",
    ),
    (
        "Last Data Date",
        "1. Volume",
        "yyyy-mm-dd",
        f"CALCULATE ( MAX ( {F}[Created At] ), REMOVEFILTERS () )",
    ),
    (
        "Days in Period",
        "1. Volume",
        "#,0",
        f"""VAR FirstDay = INT ( [First Data Date] )
VAR LastDay = INT ( [Last Data Date] )
RETURN
    COUNTROWS (
        FILTER (
            VALUES ( {D}[Date] ),
            INT ( {D}[Date] ) >= FirstDay && INT ( {D}[Date] ) <= LastDay
        )
    )""",
    ),
    ("Requests per Day", "1. Volume", "#,0.0", "DIVIDE ( [Total Requests], [Days in Period] )"),
    ("Service Requests per Day", "1. Volume", "#,0.0", "DIVIDE ( [Service Requests], [Days in Period] )"),
    (
        "Closed by Close Date",
        "1. Volume",
        "#,0",
        f"CALCULATE ( [Closed Requests], USERELATIONSHIP ( {F}[Closed Date Key], {D}[Date Key] ) )",
    ),
    (
        "Service Requests Closed by Close Date",
        "1. Volume",
        "#,0",
        f"CALCULATE ( [Closed Requests], 'Dim Intake'[Is Service Request] = TRUE (), USERELATIONSHIP ( {F}[Closed Date Key], {D}[Date Key] ) )",
    ),
    (
        "Net Backlog Change (Opened - Closed)",
        "1. Volume",
        "+#,0;-#,0;0",
        "[Service Requests] - [Service Requests Closed by Close Date]",
    ),
    # ------------------------------------------------------------ Resolution
    (
        "Median Resolution Days",
        "2. Resolution",
        "0.0",
        f"CALCULATE ( MEDIAN ( {F}[Resolution Days] ), 'Dim Intake'[Is Service Request] = TRUE (), {F}[Is Closed] = TRUE () )",
    ),
    (
        "Avg Resolution Days",
        "2. Resolution",
        "0.0",
        f"CALCULATE ( AVERAGE ( {F}[Resolution Days] ), 'Dim Intake'[Is Service Request] = TRUE (), {F}[Is Closed] = TRUE () )",
    ),
    (
        "P90 Resolution Days",
        "2. Resolution",
        "0.0",
        f"CALCULATE ( PERCENTILE.INC ( {F}[Resolution Days], 0.9 ), 'Dim Intake'[Is Service Request] = TRUE (), {F}[Is Closed] = TRUE () )",
    ),
    (
        "Median Resolution Hours (First Contact)",
        "2. Resolution",
        "0.00",
        f"CALCULATE ( MEDIAN ( {F}[Resolution Hours] ), 'Dim Intake'[Referral Type] = \"Full Service\", {F}[Is Closed] = TRUE () )",
    ),
    (
        "Resolved Within 7 Days %",
        "2. Resolution",
        "0.0%",
        f"""VAR ClosedSR = CALCULATE ( [Closed Requests], 'Dim Intake'[Is Service Request] = TRUE () )
VAR Within7 = CALCULATE ( [Closed Requests], 'Dim Intake'[Is Service Request] = TRUE (), {F}[Resolution Bucket] IN {{ "Under 1 hour", "Same day", "1-7 days" }} )
RETURN
    DIVIDE ( Within7, ClosedSR )""",
    ),
    # ------------------------------------------------------------------- SLA
    (
        "SLA Evaluated",
        "3. SLA",
        "#,0",
        f"CALCULATE ( [Total Requests], {F}[SLA Met] IN {{ TRUE (), FALSE () }} )",
    ),
    ("SLA Met", "3. SLA", "#,0", f"CALCULATE ( [Total Requests], {F}[SLA Met] = TRUE () )"),
    ("SLA Missed", "3. SLA", "#,0", f"CALCULATE ( [Total Requests], {F}[SLA Met] = FALSE () )"),
    ("SLA Attainment %", "3. SLA", "0.0%", "DIVIDE ( [SLA Met], [SLA Evaluated] )"),
    ("SLA Attainment Goal %", "3. SLA", "0%", "0.85"),
    (
        "SLA Status",
        "3. SLA",
        "",
        """SWITCH (
    TRUE (),
    ISBLANK ( [SLA Attainment %] ), "No closed service requests",
    [SLA Attainment %] >= [SLA Attainment Goal %], "On goal",
    [SLA Attainment %] >= [SLA Attainment Goal %] - 0.10, "Watch",
    "Below goal"
)""",
    ),
    (
        "SLA Target Days (Selected)",
        "3. SLA",
        "0",
        "IF ( HASONEVALUE ( 'Dim Service'[SLA Target Days] ), VALUES ( 'Dim Service'[SLA Target Days] ) )",
    ),
    # --------------------------------------------------------------- Backlog
    ("Backlog (Snapshot Sum)", "4. Backlog", "#,0", "SUM ( 'Fact Backlog Snapshot'[Open Requests] )"),
    (
        "Backlog (End of Period)",
        "4. Backlog",
        "#,0",
        f"CALCULATE ( [Backlog (Snapshot Sum)], LASTNONBLANK ( {D}[Date], [Backlog (Snapshot Sum)] ) )",
    ),
    (
        "Backlog Over 30 Days (End of Period)",
        "4. Backlog",
        "#,0",
        f"CALCULATE ( SUM ( 'Fact Backlog Snapshot'[Open Over 30 Days] ), LASTNONBLANK ( {D}[Date], [Backlog (Snapshot Sum)] ) )",
    ),
    (
        "Backlog Over 90 Days (End of Period)",
        "4. Backlog",
        "#,0",
        f"CALCULATE ( SUM ( 'Fact Backlog Snapshot'[Open Over 90 Days] ), LASTNONBLANK ( {D}[Date], [Backlog (Snapshot Sum)] ) )",
    ),
    (
        "Backlog Aged Over 30 Days %",
        "4. Backlog",
        "0.0%",
        "DIVIDE ( [Backlog Over 30 Days (End of Period)], [Backlog (End of Period)] )",
    ),
    (
        "Backlog Change vs Prior Month",
        "4. Backlog",
        "+#,0;-#,0;0",
        f"[Backlog (End of Period)] - CALCULATE ( [Backlog (End of Period)], PREVIOUSMONTH ( {D}[Date] ) )",
    ),
    (
        "Avg Open Age Days",
        "4. Backlog",
        "0.0",
        f"CALCULATE ( AVERAGE ( {F}[Open Age Days] ), {F}[Is Closed] = FALSE (), 'Dim Intake'[Is Service Request] = TRUE () )",
    ),
    # ------------------------------------------------------ Time intelligence
    (
        "Requests PY",
        "5. Time Intelligence",
        "#,0",
        f"CALCULATE ( [Total Requests], SAMEPERIODLASTYEAR ( {D}[Date] ) )",
    ),
    (
        "Requests YoY %",
        "5. Time Intelligence",
        "+0.0%;-0.0%;0.0%",
        "DIVIDE ( [Total Requests] - [Requests PY], [Requests PY] )",
    ),
    (
        "Service Requests PY",
        "5. Time Intelligence",
        "#,0",
        f"CALCULATE ( [Service Requests], SAMEPERIODLASTYEAR ( {D}[Date] ) )",
    ),
    (
        "Service Requests YoY %",
        "5. Time Intelligence",
        "+0.0%;-0.0%;0.0%",
        "DIVIDE ( [Service Requests] - [Service Requests PY], [Service Requests PY] )",
    ),
    ("Requests MTD", "5. Time Intelligence", "#,0", f"TOTALMTD ( [Total Requests], {D}[Date] )"),
    ("Requests YTD", "5. Time Intelligence", "#,0", f"TOTALYTD ( [Total Requests], {D}[Date] )"),
    (
        "Requests Rolling 3M Avg",
        "5. Time Intelligence",
        "#,0",
        f"""VAR LastDay = MAX ( {D}[Date] )
VAR Period = DATESINPERIOD ( {D}[Date], LastDay, -3, MONTH )
RETURN
    CALCULATE ( AVERAGEX ( VALUES ( {D}[Year Month Key] ), [Total Requests] ), Period )""",
    ),
    (
        "Requests Last 30 Days",
        "5. Time Intelligence",
        "#,0",
        f"""VAR AsOf = [Last Data Date]
RETURN
    CALCULATE ( [Total Requests], REMOVEFILTERS ( {D} ), DATESINPERIOD ( {D}[Date], AsOf, -30, DAY ) )""",
    ),
    (
        "Requests Prior 30 Days",
        "5. Time Intelligence",
        "#,0",
        f"""VAR AsOf = [Last Data Date] - 30
RETURN
    CALCULATE ( [Total Requests], REMOVEFILTERS ( {D} ), DATESINPERIOD ( {D}[Date], AsOf, -30, DAY ) )""",
    ),
    (
        "Requests 30-Day Change %",
        "5. Time Intelligence",
        "+0.0%;-0.0%;0.0%",
        "DIVIDE ( [Requests Last 30 Days] - [Requests Prior 30 Days], [Requests Prior 30 Days] )",
    ),
    # -------------------------------------------------------------- Channels
    (
        "Mobile App Requests",
        "6. Channels",
        "#,0",
        "CALCULATE ( [Total Requests], 'Dim Intake'[Channel] = \"Mobile App\" )",
    ),
    ("Mobile App Share %", "6. Channels", "0.0%", "DIVIDE ( [Mobile App Requests], [Total Requests] )"),
    (
        "Digital Share %",
        "6. Channels",
        "0.0%",
        "DIVIDE ( CALCULATE ( [Total Requests], 'Dim Intake'[Channel Group] = \"Digital\" ), [Total Requests] )",
    ),
    (
        "Phone Share %",
        "6. Channels",
        "0.0%",
        "DIVIDE ( CALCULATE ( [Total Requests], 'Dim Intake'[Channel] = \"Phone Call\" ), [Total Requests] )",
    ),
    # ------------------------------------------------------- Ranking & share
    (
        "Requests % of Total",
        "7. Ranking & Share",
        "0.0%",
        "DIVIDE ( [Total Requests], CALCULATE ( [Total Requests], REMOVEFILTERS ( 'Dim Service' ) ) )",
    ),
    (
        "Service Requests % of Total",
        "7. Ranking & Share",
        "0.0%",
        "DIVIDE ( [Service Requests], CALCULATE ( [Service Requests], REMOVEFILTERS ( 'Dim Service' ) ) )",
    ),
    (
        "Category Rank",
        "7. Ranking & Share",
        "0",
        "IF ( HASONEVALUE ( 'Dim Service'[Service Category] ), RANKX ( ALL ( 'Dim Service'[Service Category] ), [Service Requests], , DESC, DENSE ) )",
    ),
    (
        "Neighbourhood Rank",
        "7. Ranking & Share",
        "0",
        "IF ( HASONEVALUE ( 'Dim Neighbourhood'[Neighbourhood] ), RANKX ( ALL ( 'Dim Neighbourhood'[Neighbourhood] ), [Service Requests], , DESC, DENSE ) )",
    ),
    (
        "Top Service Category",
        "7. Ranking & Share",
        "",
        "CONCATENATEX ( TOPN ( 1, VALUES ( 'Dim Service'[Service Category] ), [Service Requests] ), 'Dim Service'[Service Category], \", \" )",
    ),
    (
        "Top Neighbourhood",
        "7. Ranking & Share",
        "",
        "CONCATENATEX ( TOPN ( 1, CALCULATETABLE ( VALUES ( 'Dim Neighbourhood'[Neighbourhood] ), 'Dim Neighbourhood'[Is Unknown] = FALSE () ), [Service Requests] ), 'Dim Neighbourhood'[Neighbourhood], \", \" )",
    ),
    # ---------------------------------------------------------- Data quality
    ("DQ Checks Total", "8. Data Quality", "0", "COUNTROWS ( 'Data Quality' )"),
    (
        "DQ Checks Passed",
        "8. Data Quality",
        "0",
        "CALCULATE ( COUNTROWS ( 'Data Quality' ), 'Data Quality'[Passed] = TRUE () )",
    ),
    (
        "DQ Status",
        "8. Data Quality",
        "",
        """VAR CriticalFails = CALCULATE ( COUNTROWS ( 'Data Quality' ), 'Data Quality'[Passed] = FALSE (), 'Data Quality'[Severity] = "critical" )
VAR AnyFails = CALCULATE ( COUNTROWS ( 'Data Quality' ), 'Data Quality'[Passed] = FALSE () )
RETURN
    SWITCH ( TRUE (), CriticalFails > 0, "FAIL", AnyFails > 0, "WARN", "PASS" )""",
    ),
    (
        "Pipeline Built At (UTC)",
        "8. Data Quality",
        "",
        "LOOKUPVALUE ( 'Build Info'[Value], 'Build Info'[Key], \"built_at_utc\" )",
    ),
    (
        "Pipeline Version",
        "8. Data Quality",
        "",
        "LOOKUPVALUE ( 'Build Info'[Value], 'Build Info'[Key], \"pipeline_version\" )",
    ),
    (
        "Fact Rows (Build)",
        "8. Data Quality",
        "#,0",
        "VALUE ( LOOKUPVALUE ( 'Build Info'[Value], 'Build Info'[Key], \"rows.gold.fact_service_request\" ) )",
    ),
    # ---------------------------------------------------------------- Labels
    (
        "Selected Period Label",
        "9. Labels",
        "",
        f"""VAR MinD = MIN ( {D}[Date] )
VAR MaxD = MAX ( {D}[Date] )
RETURN
    FORMAT ( MinD, "d mmm yyyy" ) & " to " & FORMAT ( MaxD, "d mmm yyyy" )""",
    ),
    ("Data As Of Label", "9. Labels", "", '"Data as of " & FORMAT ( [Last Data Date], "d mmm yyyy" )'),
    ("Overview Title", "9. Labels", "", '"Edmonton 311 Service Requests  |  " & [Selected Period Label]'),
]

# Row-level security roles: (role name, table, DAX filter expression)
RLS_ROLES: list[tuple[str, str, str]] = [
    (
        "Ward Viewer - papastew (static example)",
        "Dim Neighbourhood",
        "'Dim Neighbourhood'[Ward] = \"papastew\"",
    ),
    (
        "Ward Viewer - dynamic",
        "Dim Neighbourhood",
        "'Dim Neighbourhood'[Ward] IN CALCULATETABLE ( VALUES ( 'Security Ward Users'[Ward] ), 'Security Ward Users'[User Email] = USERPRINCIPALNAME () )",
    ),
]
