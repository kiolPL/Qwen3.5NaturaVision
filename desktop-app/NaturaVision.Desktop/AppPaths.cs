using System.IO;

namespace NaturaVision.Desktop;

internal static class AppPaths
{
    public static string? FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var labelsPath = Path.Combine(directory.FullName, "data", "v2", "labels.json");
            if (File.Exists(labelsPath))
            {
                return directory.FullName;
            }
            directory = directory.Parent;
        }
        return null;
    }

    public static string FirstExistingFile(params string[] candidates)
    {
        return candidates.FirstOrDefault(File.Exists) ?? candidates.FirstOrDefault() ?? string.Empty;
    }

    public static string FirstExistingDirectory(params string[] candidates)
    {
        return candidates.FirstOrDefault(Directory.Exists) ?? candidates.FirstOrDefault() ?? string.Empty;
    }
}
