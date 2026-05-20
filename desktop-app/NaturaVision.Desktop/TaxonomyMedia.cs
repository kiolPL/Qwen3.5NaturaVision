using System.Text.Json.Serialization;

namespace NaturaVision.Desktop;

public sealed class TaxonomyMedia
{
    [JsonPropertyName("label_id")]
    public string LabelId { get; init; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; init; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("source_url")]
    public string SourceUrl { get; init; } = string.Empty;

    [JsonPropertyName("image_file")]
    public string ImageFile { get; init; } = string.Empty;

    [JsonIgnore]
    public string? ResolvedImagePath { get; set; }
}
