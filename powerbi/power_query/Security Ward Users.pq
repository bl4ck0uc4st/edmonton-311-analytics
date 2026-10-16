let
    // Email -> ward mapping used by the dynamic RLS role. Replace with your own table
    // (Excel/SharePoint list/database). Sample file: powerbi/rls/security_ward_users.csv
    Source = Csv.Document(File.Contents(Text.TrimEnd(LocalExportFolder, {"\", "/"}) & "\..\..\powerbi\rls\security_ward_users.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Renamed = Table.RenameColumns(Promoted, {{"user_email", "User Email"}, {"ward", "Ward"}}),
    Typed = Table.TransformColumnTypes(Renamed, {{"User Email", type text}, {"Ward", type text}})
in
    Typed
