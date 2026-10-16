let
    Source = fnLoadExport("dim_status"),
    Renamed = Table.RenameColumns(Source, {
        {"status_key", "Status Key"},
        {"request_status", "Status"},
        {"status_detail", "Status Detail"},
        {"is_closed_status", "Is Closed"},
        {"outcome_group", "Outcome Group"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Status Key", Int64.Type},
        {"Status", type text},
        {"Status Detail", type text},
        {"Is Closed", type logical},
        {"Outcome Group", type text}
    })
in
    Typed
