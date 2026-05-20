using System.IO;
using System.Text.Json;

namespace NaturaVision.Desktop;

public sealed record TestExample(string ImagePath, string ExpectedLabelId);

public static class TestSuiteLoader
{
    public static IReadOnlyList<TestExample> Load(string jsonlPath, int count, TaxonomyCatalog catalog)
    {
        if (!File.Exists(jsonlPath))
        {
            throw new FileNotFoundException("Test JSONL was not found.", jsonlPath);
        }

        var examples = new List<TestExample>();
        var datasetRoot = Path.GetDirectoryName(jsonlPath) ?? Environment.CurrentDirectory;
        foreach (var line in File.ReadLines(jsonlPath))
        {
            if (examples.Count >= count)
            {
                break;
            }
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            using var document = JsonDocument.Parse(line);
            var root = document.RootElement;
            var imageRef = root.GetProperty("images")[0].GetString();
            if (string.IsNullOrWhiteSpace(imageRef))
            {
                continue;
            }

            var expected = ExtractAssistantLabel(root) ?? "unknown";
            var imagePath = Path.IsPathRooted(imageRef)
                ? imageRef
                : Path.GetFullPath(Path.Combine(datasetRoot, imageRef));
            examples.Add(new TestExample(imagePath, catalog.CollapseToPublic(expected)));
        }

        return examples;
    }

    private static string? ExtractAssistantLabel(JsonElement root)
    {
        foreach (var message in root.GetProperty("messages").EnumerateArray())
        {
            if (!message.TryGetProperty("role", out var role) ||
                !string.Equals(role.GetString(), "assistant", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var content = message.GetProperty("content").GetString();
            if (string.IsNullOrWhiteSpace(content))
            {
                return null;
            }

            using var contentDocument = JsonDocument.Parse(content);
            return contentDocument.RootElement.GetProperty("label_id").GetString();
        }

        return null;
    }
}
