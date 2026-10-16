let
    Source = fnLoadExport("dim_service"),
    Renamed = Table.RenameColumns(Source, {
        {"service_key", "Service Key"},
        {"service_area", "Service Area"},
        {"service_category", "Service Category"},
        {"service_description", "Service Description"},
        {"service_group", "Service Group"},
        {"area_category", "Area / Category"},
        {"sla_target_days", "SLA Target Days"},
        {"sla_basis", "SLA Basis"},
        {"is_informational", "Is Informational"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Service Key", Int64.Type},
        {"Service Area", type text},
        {"Service Category", type text},
        {"Service Description", type text},
        {"Service Group", type text},
        {"Area / Category", type text},
        {"SLA Target Days", Int64.Type},
        {"SLA Basis", type text},
        {"Is Informational", type logical}
    })
in
    Typed
