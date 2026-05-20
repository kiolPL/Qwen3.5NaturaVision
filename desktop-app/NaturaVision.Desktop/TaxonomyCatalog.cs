using System.IO;
using System.Text.Json;

namespace NaturaVision.Desktop;

public sealed class TaxonomyCatalog
{
    private readonly Dictionary<string, SpeciesInfo> _byPublicLabel;
    private readonly Dictionary<string, string> _collapseToPublic;

    private TaxonomyCatalog(
        IReadOnlyList<SpeciesInfo> publicSpecies,
        IReadOnlySet<string> allowedModelLabels,
        Dictionary<string, string> collapseToPublic,
        string systemPrompt)
    {
        PublicSpecies = publicSpecies;
        AllowedModelLabels = allowedModelLabels;
        _collapseToPublic = collapseToPublic;
        _byPublicLabel = publicSpecies.ToDictionary(species => species.LabelId, StringComparer.OrdinalIgnoreCase);
        SystemPrompt = systemPrompt;
        JsonSchema = BuildJsonSchema(allowedModelLabels);
    }

    public IReadOnlyList<SpeciesInfo> PublicSpecies { get; }

    public IReadOnlySet<string> AllowedModelLabels { get; }

    public string SystemPrompt { get; }

    public string JsonSchema { get; }

    public static TaxonomyCatalog Load(string labelsPath)
    {
        if (!File.Exists(labelsPath))
        {
            throw new FileNotFoundException("labels.json was not found.", labelsPath);
        }

        using var document = JsonDocument.Parse(File.ReadAllText(labelsPath));
        var root = document.RootElement;
        var byId = root.GetProperty("by_id");
        var allSpecies = new Dictionary<string, SpeciesInfo>(StringComparer.OrdinalIgnoreCase);
        foreach (var property in byId.EnumerateObject())
        {
            var value = property.Value;
            allSpecies[property.Name] = new SpeciesInfo(
                LabelId: value.GetProperty("label_id").GetString() ?? property.Name,
                Kingdom: value.GetProperty("kingdom").GetString() ?? "unknown",
                ScientificName: value.GetProperty("scientific_name").GetString() ?? "unknown",
                PolishName: value.GetProperty("polish_name").GetString() ?? "unknown",
                EnglishName: value.GetProperty("english_name").GetString() ?? "unknown");
        }

        var collapse = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (root.TryGetProperty("collapse_to_public", out var collapseJson))
        {
            foreach (var property in collapseJson.EnumerateObject())
            {
                collapse[property.Name] = property.Value.GetString() ?? "unknown";
            }
        }

        var allowed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (root.TryGetProperty("supported_labels", out var supportedLabels))
        {
            foreach (var label in supportedLabels.EnumerateArray())
            {
                AddIfPresent(allowed, label.GetString());
            }
        }
        var promptLabelIds = new List<string>();
        if (root.TryGetProperty("training_supported_labels", out var trainingLabels))
        {
            foreach (var label in trainingLabels.EnumerateArray())
            {
                var labelId = label.GetString();
                AddIfPresent(allowed, labelId);
                if (!string.IsNullOrWhiteSpace(labelId))
                {
                    promptLabelIds.Add(labelId);
                }
            }
        }
        allowed.Add("unknown");
        if (promptLabelIds.Count == 0)
        {
            promptLabelIds.AddRange(allowed);
        }

        var publicLabelIds = root.GetProperty("supported_labels")
            .EnumerateArray()
            .Select(label => label.GetString())
            .Where(label => !string.IsNullOrWhiteSpace(label))
            .Cast<string>();
        var publicSpecies = publicLabelIds
            .Select(label => allSpecies.GetValueOrDefault(label))
            .Where(species => species is not null)
            .Cast<SpeciesInfo>()
            .ToList();

        return new TaxonomyCatalog(
            publicSpecies,
            allowed,
            collapse,
            BuildSystemPrompt(promptLabelIds, allSpecies));
    }

    public string CollapseToPublic(string labelId)
    {
        if (!AllowedModelLabels.Contains(labelId))
        {
            return "unknown";
        }
        return _collapseToPublic.GetValueOrDefault(labelId, labelId);
    }

    public SpeciesInfo LookupPublic(string labelId)
    {
        var publicLabel = CollapseToPublic(labelId);
        return _byPublicLabel.GetValueOrDefault(publicLabel)
            ?? _byPublicLabel.GetValueOrDefault("unknown")
            ?? new SpeciesInfo("unknown", "unknown", "unknown", "unknown", "unknown");
    }

    private static void AddIfPresent(HashSet<string> labels, string? label)
    {
        if (!string.IsNullOrWhiteSpace(label))
        {
            labels.Add(label);
        }
    }

    private static string BuildSystemPrompt(
        IEnumerable<string> promptLabelIds,
        IReadOnlyDictionary<string, SpeciesInfo> allSpecies)
    {
        var lines = promptLabelIds
            .Where(labelId => allSpecies.ContainsKey(labelId))
            .Select(labelId =>
            {
                var item = allSpecies[labelId];
                return labelId.StartsWith("UNK_", StringComparison.OrdinalIgnoreCase)
                    ? $"- {item.LabelId} = {item.EnglishName} (collapse to public unknown outside training)"
                    : $"- {item.LabelId} = {item.ScientificName}";
            });

        return string.Join(Environment.NewLine, new[]
        {
            "You classify exactly one forest organism from a fixed taxonomy.",
            "Return JSON only with the single key label_id.",
            "Choose exactly one allowed label_id from the list below.",
            "If the organism is outside the supported taxonomy or the image is ambiguous, choose the best matching UNK_* label.",
            "Do not output thinking, explanations, markdown, or <think> blocks.",
            "Do not invent labels, synonyms, or alternate JSON keys.",
            "Allowed labels:",
        }.Concat(lines));
    }

    private static string BuildJsonSchema(IReadOnlySet<string> allowedLabels)
    {
        var schema = new
        {
            type = "object",
            properties = new
            {
                label_id = new
                {
                    type = "string",
                    @enum = allowedLabels.OrderBy(label => label, StringComparer.OrdinalIgnoreCase).ToArray(),
                },
            },
            required = new[] { "label_id" },
            additionalProperties = false,
        };
        return JsonSerializer.Serialize(schema);
    }
}
