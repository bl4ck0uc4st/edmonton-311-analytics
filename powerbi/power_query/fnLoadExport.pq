let
    // Loads one exported table from either the GitHub Release (default, refreshable from
    // anywhere) or a local folder produced by `yeg311 export`. Parquet keeps the DuckDB
    // types (dates, timestamps, booleans, integers) so very little re-typing is needed.
    LoadExport = (tableName as text) as table =>
        let
            fileName = tableName & ".parquet",
            folder = Text.TrimEnd(LocalExportFolder, {"\", "/"}),
            binary =
                if DataSourceMode = "Local Folder" then
                    File.Contents(folder & "\" & fileName)
                else
                    Web.Contents(GitHubReleaseBaseUrl, [RelativePath = fileName]),
            parquet = Parquet.Document(binary)
        in
            parquet
in
    LoadExport
