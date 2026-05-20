using System.IO;
using System.Text.Json;

namespace NaturaVision.Desktop;

public sealed class TaxonomyMediaCatalog
{
    private readonly Dictionary<string, TaxonomyMedia> _byLabel;

    private TaxonomyMediaCatalog(Dictionary<string, TaxonomyMedia> byLabel)
    {
        _byLabel = byLabel;
    }

    public static TaxonomyMediaCatalog Load(string mediaDirectory)
    {
        var byLabel = new Dictionary<string, TaxonomyMedia>(StringComparer.OrdinalIgnoreCase);
        if (!Directory.Exists(mediaDirectory))
        {
            return new TaxonomyMediaCatalog(byLabel);
        }

        foreach (var jsonPath in Directory.EnumerateFiles(mediaDirectory, "*.json"))
        {
            try
            {
                var media = JsonSerializer.Deserialize<TaxonomyMedia>(File.ReadAllText(jsonPath));
                if (media is null || string.IsNullOrWhiteSpace(media.LabelId))
                {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(media.ImageFile))
                {
                    var imagePath = Path.Combine(mediaDirectory, media.ImageFile);
                    media.ResolvedImagePath = File.Exists(imagePath) ? imagePath : null;
                }
                byLabel[media.LabelId] = media;
            }
            catch
            {
                // A single stale metadata file should not break the whole app.
            }
        }

        return new TaxonomyMediaCatalog(byLabel);
    }

    public TaxonomyMedia? Lookup(string labelId)
    {
        return _byLabel.GetValueOrDefault(labelId);
    }
}
