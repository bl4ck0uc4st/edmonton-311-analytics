"""Render the Power BI semantic model assets from scripts/powerbi_model_spec.py.

Run from the repository root:

    python scripts/build_powerbi_assets.py

Outputs (all committed to the repo so reviewers can read them without Power BI):
    powerbi/power_query/*.pq   powerbi/dax/measures.dax   powerbi/tmdl/model.tmdl   docs/data_dictionary.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from powerbi_model_spec import (  # noqa: E402
    MEASURES,
    RELATIONSHIPS,
    RELEASE_BASE_URL,
    RLS_ROLES,
    TABLES,
)

PQ_DIR = ROOT / "powerbi" / "power_query"
DAX_DIR = ROOT / "powerbi" / "dax"
TMDL_DIR = ROOT / "powerbi" / "tmdl"
DOCS_DIR = ROOT / "docs"

MEASURE_TABLE = "_Measures"

PARAMETERS_PQ = {
    "DataSourceMode": '"GitHub Release" meta [IsParameterQuery=true, List={"GitHub Release", "Local Folder"}, DefaultValue="GitHub Release", Type="Text", IsParameterQueryRequired=true]',
    "GitHubReleaseBaseUrl": f'"{RELEASE_BASE_URL}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
    "LocalExportFolder": '"C:\\Projects\\edmonton-311-analytics\\data\\exports" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
}

LOADER_PQ = """let
    // Loads one exported table from either the GitHub Release (default, refreshable from
    // anywhere) or a local folder produced by `yeg311 export`. Parquet keeps the DuckDB
    // types (dates, timestamps, booleans, integers) so very little re-typing is needed.
    LoadExport = (tableName as text) as table =>
        let
            fileName = tableName & ".parquet",
            folder = Text.TrimEnd(LocalExportFolder, {"\\", "/"}),
            binary =
                if DataSourceMode = "Local Folder" then
                    File.Contents(folder & "\\" & fileName)
                else
                    Web.Contents(GitHubReleaseBaseUrl, [RelativePath = fileName]),
            parquet = Parquet.Document(binary)
        in
            parquet
in
    LoadExport"""


def table_pq(t: dict) -> str:
    renames = ",\n        ".join(f'{{"{src}", "{friendly}"}}' for src, friendly, *_ in t["columns"])
    types = ",\n        ".join(f'{{"{friendly}", {m_type}}}' for _src, friendly, m_type, *_ in t["columns"])
    return f"""let
    Source = fnLoadExport("{t["export"]}"),
    Renamed = Table.RenameColumns(Source, {{
        {renames}
    }}),
    Typed = Table.TransformColumnTypes(Renamed, {{
        {types}
    }})
in
    Typed"""


def measures_pq() -> str:
    return """let
    // Empty table that hosts every measure (keeps the field list tidy). Hide the column.
    Source = #table(type table [#"Measures" = text], {})
in
    Source"""


def security_pq() -> str:
    return """let
    // Email -> ward mapping used by the dynamic RLS role. Replace with your own table
    // (Excel/SharePoint list/database). Sample file: powerbi/rls/security_ward_users.csv
    Source = Csv.Document(File.Contents(Text.TrimEnd(LocalExportFolder, {"\\", "/"}) & "\\..\\..\\powerbi\\rls\\security_ward_users.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Renamed = Table.RenameColumns(Promoted, {{"user_email", "User Email"}, {"ward", "Ward"}}),
    Typed = Table.TransformColumnTypes(Renamed, {{"User Email", type text}, {"Ward", type text}})
in
    Typed"""


def write_power_query() -> None:
    PQ_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in PARAMETERS_PQ.items():
        (PQ_DIR / f"Parameter - {name}.pq").write_text(body + "\n", encoding="utf-8")
    (PQ_DIR / "fnLoadExport.pq").write_text(LOADER_PQ + "\n", encoding="utf-8")
    for t in TABLES:
        (PQ_DIR / f"{t['name']}.pq").write_text(table_pq(t) + "\n", encoding="utf-8")
    (PQ_DIR / f"{MEASURE_TABLE}.pq").write_text(measures_pq() + "\n", encoding="utf-8")
    (PQ_DIR / "Security Ward Users.pq").write_text(security_pq() + "\n", encoding="utf-8")


def write_measures_dax() -> None:
    DAX_DIR.mkdir(parents=True, exist_ok=True)
    out = [
        "// Edmonton 311 Analytics - DAX measures",
        "// Generated from scripts/powerbi_model_spec.py. Create each measure on the '_Measures' table.",
        "// Lines starting with '// Folder:' and '// Format:' are the display folder and format string to set.",
        "",
    ]
    current_folder = None
    for name, folder, fmt, dax in MEASURES:
        if folder != current_folder:
            out.append(f"// {'=' * 76}")
            out.append(f"// {folder}")
            out.append(f"// {'=' * 76}")
            current_folder = folder
        out.append(f"// Folder: {folder}")
        out.append(f"// Format: {fmt or '(none)'}")
        out.append(f"{name} =")
        out.append(dax)
        out.append("")
    (DAX_DIR / "measures.dax").write_text("\n".join(out), encoding="utf-8")


def _tmdl_lines_for_expression(indent: int, text: str) -> list[str]:
    pad = "\t" * indent
    return [pad + line if line else "" for line in text.splitlines()]


def write_tmdl() -> None:
    TMDL_DIR.mkdir(parents=True, exist_ok=True)
    L: list[str] = []
    L.append("createOrReplace")
    L.append("")
    # ---- parameters & loader as model expressions
    for name, body in PARAMETERS_PQ.items():
        L.append(f"\texpression {name} = {body}")
        L.append("")
    L.append("\texpression fnLoadExport =")
    L.extend(_tmdl_lines_for_expression(3, LOADER_PQ))
    L.append("")

    # ---- tables
    for t in TABLES:
        L.append(f"\t/// {t['description']}")
        L.append(f"\ttable '{t['name']}'")
        if t.get("is_date_table"):
            L.append("\t\tdataCategory: Time")
        for _src, friendly, _m_type, tmdl_type, description, opts in t["columns"]:
            if description:
                L.append(f"\t\t/// {description}")
            L.append(f"\t\tcolumn '{friendly}'")
            L.append(f"\t\t\tdataType: {tmdl_type}")
            if opts.get("key") and t.get("is_date_table") and friendly == "Date":
                L.append("\t\t\tisKey")
            if opts.get("hidden"):
                L.append("\t\t\tisHidden")
            if opts.get("format"):
                L.append(f"\t\t\tformatString: {opts['format']}")
            if opts.get("category"):
                L.append(f"\t\t\tdataCategory: {opts['category']}")
            summarize = opts.get("summarize", "none")
            L.append(f"\t\t\tsummarizeBy: {summarize}")
            if opts.get("sort_by"):
                L.append(f"\t\t\tsortByColumn: '{opts['sort_by']}'")
            L.append(f"\t\t\tsourceColumn: {friendly}")
            L.append("")
        L.append(f"\t\tpartition '{t['name']}' = m")
        L.append("\t\t\tmode: import")
        L.append("\t\t\tsource =")
        L.extend(_tmdl_lines_for_expression(4, table_pq(t)))
        L.append("")

    # ---- measures table
    L.append(f"\ttable '{MEASURE_TABLE}'")
    L.append("\t\tcolumn 'Measures'")
    L.append("\t\t\tdataType: string")
    L.append("\t\t\tisHidden")
    L.append("\t\t\tsummarizeBy: none")
    L.append("\t\t\tsourceColumn: Measures")
    L.append("")
    for name, folder, fmt, dax in MEASURES:
        if "\n" in dax:
            L.append(f"\t\tmeasure '{name}' =")
            L.extend(_tmdl_lines_for_expression(4, dax))
        else:
            L.append(f"\t\tmeasure '{name}' = {dax}")
        if fmt:
            L.append(f"\t\t\tformatString: {fmt}")
        L.append(f"\t\t\tdisplayFolder: {folder}")
        L.append("")
    L.append(f"\t\tpartition '{MEASURE_TABLE}' = m")
    L.append("\t\t\tmode: import")
    L.append("\t\t\tsource =")
    L.extend(_tmdl_lines_for_expression(4, measures_pq()))
    L.append("")

    # ---- security table (dynamic RLS)
    L.append("\ttable 'Security Ward Users'")
    L.append("\t\tisHidden")
    for friendly in ("User Email", "Ward"):
        L.append(f"\t\tcolumn '{friendly}'")
        L.append("\t\t\tdataType: string")
        L.append("\t\t\tsummarizeBy: none")
        L.append(f"\t\t\tsourceColumn: {friendly}")
        L.append("")
    L.append("\t\tpartition 'Security Ward Users' = m")
    L.append("\t\t\tmode: import")
    L.append("\t\t\tsource =")
    L.extend(_tmdl_lines_for_expression(4, security_pq()))
    L.append("")

    # ---- relationships
    for i, r in enumerate(RELATIONSHIPS, start=1):
        (ft, fc), (tt, tc) = r["from"], r["to"]
        L.append(f"\trelationship rel_{i:02d}_{ft.replace(' ', '')}_{fc.replace(' ', '')}")
        if not r["active"]:
            L.append("\t\tisActive: false")
        L.append(f"\t\tfromColumn: '{ft}'.'{fc}'")
        L.append(f"\t\ttoColumn: '{tt}'.'{tc}'")
        L.append("")

    # ---- roles
    for role, table, dax in RLS_ROLES:
        L.append(f"\trole '{role}'")
        L.append("\t\tmodelPermission: read")
        L.append("")
        L.append(f"\t\ttablePermission '{table}' = {dax}")
        L.append("")

    (TMDL_DIR / "model.tmdl").write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")


def write_data_dictionary() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = [
        "# Data dictionary",
        "",
        "Generated from `scripts/powerbi_model_spec.py`. Each table below is exported by `yeg311 export` to",
        "`data/exports/<export>.parquet` (dimensions also as CSV) and loaded into Power BI under the friendly name.",
        "",
        "Grain and keys follow Kimball conventions: integer surrogate keys on every dimension, an explicit",
        "`Unknown` member (key `-1`) for missing neighbourhoods, and no fact row is ever dropped because of a",
        "missing dimension value.",
        "",
    ]
    for t in TABLES:
        out.append(f"## {t['name']}  (`{t['export']}`)")
        out.append("")
        out.append(t["description"])
        out.append("")
        out.append("| Source column | Power BI column | Type | Description |")
        out.append("|---|---|---|---|")
        for src, friendly, _m, tmdl_type, description, opts in t["columns"]:
            flags = " (hidden)" if opts.get("hidden") else ""
            out.append(f"| `{src}` | {friendly}{flags} | {tmdl_type} | {description} |")
        out.append("")
    out.append("## Relationships")
    out.append("")
    out.append("| From | To | Active |")
    out.append("|---|---|---|")
    for r in RELATIONSHIPS:
        (ft, fc), (tt, tc) = r["from"], r["to"]
        out.append(f"| `{ft}[{fc}]` | `{tt}[{tc}]` | {'yes' if r['active'] else 'no (USERELATIONSHIP)'} |")
    out.append("")
    out.append("## Measures")
    out.append("")
    out.append("| Measure | Folder | Format |")
    out.append("|---|---|---|")
    for name, folder, fmt, _dax in MEASURES:
        out.append(f"| {name} | {folder} | `{fmt or '-'}` |")
    out.append("")
    out.append("Full DAX for every measure: [`powerbi/dax/measures.dax`](../powerbi/dax/measures.dax).")
    out.append("")
    (DOCS_DIR / "data_dictionary.md").write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    write_power_query()
    write_measures_dax()
    write_tmdl()
    write_data_dictionary()
    print(
        f"Rendered {len(TABLES)} tables, {len(MEASURES)} measures, {len(RELATIONSHIPS)} relationships, {len(RLS_ROLES)} roles."
    )


if __name__ == "__main__":
    main()
