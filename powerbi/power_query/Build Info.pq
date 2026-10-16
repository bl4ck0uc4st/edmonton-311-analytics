let
    Source = fnLoadExport("build_info"),
    Renamed = Table.RenameColumns(Source, {
        {"key", "Key"},
        {"value", "Value"}
    }),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Key", type text},
        {"Value", type text}
    })
in
    Typed
