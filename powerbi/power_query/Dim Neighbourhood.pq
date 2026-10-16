let
    Source = fnLoadExport("dim_neighbourhood"),
    Renamed = Table.RenameColumns(Source, {
        {"neighbourhood_key", "Neighbourhood Key"},
        {"neighbourhood_id", "Neighbourhood ID"},
        {"neighbourhood_name", "Neighbourhood"},
        {"neighbourhood_name_source", "Neighbourhood (Source)"},
        {"ward", "Ward"},
        {"nbhd_latitude", "Latitude"},
        {"nbhd_longitude", "Longitude"},
        {"ward_latitude", "Ward Latitude"},
        {"ward_longitude", "Ward Longitude"},
        {"is_unknown_member", "Is Unknown"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Neighbourhood Key", Int64.Type},
        {"Neighbourhood ID", Int64.Type},
        {"Neighbourhood", type text},
        {"Neighbourhood (Source)", type text},
        {"Ward", type text},
        {"Latitude", type number},
        {"Longitude", type number},
        {"Ward Latitude", type number},
        {"Ward Longitude", type number},
        {"Is Unknown", type logical}
    })
in
    Typed
