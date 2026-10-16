let
    Source = fnLoadExport("fact_backlog_snapshot"),
    Renamed = Table.RenameColumns(Source, {
        {"date_key", "Date Key"},
        {"service_key", "Service Key"},
        {"open_requests", "Open Requests"},
        {"open_over_30_days", "Open Over 30 Days"},
        {"open_over_90_days", "Open Over 90 Days"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Date Key", Int64.Type},
        {"Service Key", Int64.Type},
        {"Open Requests", Int64.Type},
        {"Open Over 30 Days", Int64.Type},
        {"Open Over 90 Days", Int64.Type}
    })
in
    Typed
