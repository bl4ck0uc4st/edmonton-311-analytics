let
    // Empty table that hosts every measure (keeps the field list tidy). Hide the column.
    Source = #table(type table [#"Measures" = text], {})
in
    Source
