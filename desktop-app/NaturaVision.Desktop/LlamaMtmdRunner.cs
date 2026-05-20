using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace NaturaVision.Desktop;

public sealed record RunnerSettings(
    string LlamaCliPath,
    string ModelPath,
    string ProjectorPath,
    string ImagePath,
    int ImageTokens,
    int MaxNewTokens,
    int GpuLayers);

public sealed record InferenceResult(
    string RawLabelId,
    string PublicLabelId,
    string RawText,
    string StandardError,
    TimeSpan Elapsed);

public sealed class LlamaMtmdRunner
{
    private static readonly Regex LabelRegex = new(
        "\"label_id\"\\s*:\\s*\"(?<label>[^\"]+)\"",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private readonly TaxonomyCatalog _catalog;

    public LlamaMtmdRunner(TaxonomyCatalog catalog)
    {
        _catalog = catalog;
    }

    public async Task<InferenceResult> ClassifyAsync(RunnerSettings settings, CancellationToken cancellationToken = default)
    {
        Validate(settings);

        var stopwatch = Stopwatch.StartNew();
        using var process = new Process();
        process.StartInfo = BuildStartInfo(settings);

        process.Start();
        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        stopwatch.Stop();

        var stdout = await stdoutTask;
        var stderr = await stderrTask;
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"llama-mtmd-cli exited with code {process.ExitCode}.{Environment.NewLine}{stderr}");
        }

        var rawText = ExtractLikelyModelText(stdout);
        var rawLabel = ExtractLabelId(rawText) ?? ExtractLabelId(stdout) ?? ExtractLabelId(stderr) ?? "unknown";
        var publicLabel = _catalog.CollapseToPublic(rawLabel);

        return new InferenceResult(
            RawLabelId: rawLabel,
            PublicLabelId: publicLabel,
            RawText: rawText,
            StandardError: stderr,
            Elapsed: stopwatch.Elapsed);
    }

    private ProcessStartInfo BuildStartInfo(RunnerSettings settings)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = settings.LlamaCliPath,
            WorkingDirectory = Path.GetDirectoryName(settings.LlamaCliPath) ?? AppContext.BaseDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        Add(startInfo, "-m", settings.ModelPath);
        Add(startInfo, "--mmproj", settings.ProjectorPath);
        Add(startInfo, "--image", settings.ImagePath);
        Add(startInfo, "-sys", _catalog.SystemPrompt);
        Add(startInfo, "-p", "<__media__>Classify the organism using the fixed taxonomy. Return JSON only. If no known label fits, return the best matching UNK_* label.");
        Add(startInfo, "-n", settings.MaxNewTokens.ToString());
        Add(startInfo, "-c", "4096");
        Add(startInfo, "-fa", "on");
        Add(startInfo, "--temp", "0");
        Add(startInfo, "--top-k", "1");
        Add(startInfo, "--top-p", "1");
        Add(startInfo, "--min-p", "0");
        Add(startInfo, "--repeat-penalty", "1");
        Add(startInfo, "--presence-penalty", "0");
        Add(startInfo, "--frequency-penalty", "0");
        Add(startInfo, "--seed", "42");
        startInfo.ArgumentList.Add("--no-warmup");
        Add(startInfo, "--image-min-tokens", settings.ImageTokens.ToString());
        Add(startInfo, "--image-max-tokens", settings.ImageTokens.ToString());
        Add(startInfo, "--json-schema-file", WriteJsonSchemaFile());
        Add(startInfo, "-ngl", settings.GpuLayers.ToString());
        if (settings.GpuLayers == 0)
        {
            startInfo.ArgumentList.Add("--no-mmproj-offload");
        }

        return startInfo;
    }

    private static void Add(ProcessStartInfo startInfo, string name, string value)
    {
        startInfo.ArgumentList.Add(name);
        startInfo.ArgumentList.Add(value);
    }

    private string WriteJsonSchemaFile()
    {
        var schemaPath = Path.Combine(Path.GetTempPath(), "naturavision-desktop-label-schema.json");
        File.WriteAllText(schemaPath, _catalog.JsonSchema, Encoding.UTF8);
        return schemaPath;
    }

    private static void Validate(RunnerSettings settings)
    {
        if (!File.Exists(settings.LlamaCliPath))
        {
            throw new FileNotFoundException("llama-mtmd-cli.exe was not found.", settings.LlamaCliPath);
        }
        if (!File.Exists(settings.ModelPath))
        {
            throw new FileNotFoundException("Model GGUF was not found.", settings.ModelPath);
        }
        if (!File.Exists(settings.ProjectorPath))
        {
            throw new FileNotFoundException("Projector GGUF was not found.", settings.ProjectorPath);
        }
        if (!File.Exists(settings.ImagePath))
        {
            throw new FileNotFoundException("Image was not found.", settings.ImagePath);
        }
    }

    private static string? ExtractLabelId(string text)
    {
        var matches = LabelRegex.Matches(text);
        return matches.Count == 0 ? null : matches[^1].Groups["label"].Value.Trim();
    }

    private static string ExtractLikelyModelText(string stdout)
    {
        var jsonStart = stdout.IndexOf("{", StringComparison.Ordinal);
        if (jsonStart >= 0)
        {
            return stdout[jsonStart..].Trim();
        }
        return stdout.Trim();
    }
}
