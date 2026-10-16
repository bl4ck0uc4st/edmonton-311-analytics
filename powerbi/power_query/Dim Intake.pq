let
    Source = fnLoadExport("dim_intake"),
    Renamed = Table.RenameColumns(Source, {
        {"intake_key", "Intake Key"},
        {"interaction_channel", "Channel"},
        {"referral_type", "Referral Type"},
        {"channel_group", "Channel Group"},
        {"request_type", "Request Type"},
        {"is_service_request", "Is Service Request"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Intake Key", Int64.Type},
        {"Channel", type text},
        {"Referral Type", type text},
        {"Channel Group", type text},
        {"Request Type", type text},
        {"Is Service Request", type logical}
    })
in
    Typed
