let
    Source = fnLoadExport("quality_results"),
    Renamed = Table.RenameColumns(Source, {
        {"run_at_utc", "Run At (UTC)"},
        {"check_name", "Check"},
        {"description", "Description"},
        {"severity", "Severity"},
        {"value", "Value"},
        {"threshold", "Threshold"},
        {"unit", "Unit"},
        {"passed", "Passed"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Run At (UTC)", type text},
        {"Check", type text},
        {"Description", type text},
        {"Severity", type text},
        {"Value", type number},
        {"Threshold", type number},
        {"Unit", type text},
        {"Passed", type logical}
    })
in
    Typed
