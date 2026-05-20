using Microsoft.Win32;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows.Controls;
using System.Windows;
using System.Windows.Media.Imaging;

namespace NaturaVision.Desktop;

public partial class MainWindow : Window
{
    private readonly TaxonomyCatalog _catalog;
    private readonly TaxonomyMediaCatalog _mediaCatalog;
    private readonly LlamaMtmdRunner _runner;
    private string? _selectedImagePath;

    public MainWindow()
    {
        DesktopStartupLog.Write("MainWindow constructor entered.");
        InitializeComponent();
        DesktopStartupLog.Write("MainWindow InitializeComponent completed.");

        var repoRoot = AppPaths.FindRepositoryRoot();
        var labelsPath = repoRoot is null
            ? Path.Combine(AppContext.BaseDirectory, "data", "v2", "labels.json")
            : Path.Combine(repoRoot, "data", "v2", "labels.json");
        var mediaPath = repoRoot is null
            ? Path.Combine(AppContext.BaseDirectory, "data", "taxonomy_media")
            : Path.Combine(repoRoot, "data", "taxonomy_media");

        _catalog = TaxonomyCatalog.Load(labelsPath);
        _mediaCatalog = TaxonomyMediaCatalog.Load(mediaPath);
        _runner = new LlamaMtmdRunner(_catalog);

        TaxonomyListView.ItemsSource = _catalog.PublicSpecies;
        LlamaBinTextBox.Text = AppPaths.FirstExistingDirectory(
            @"C:\tmp\llama-b9245-bin-win-cuda-13.1-x64",
            @"C:\tmp\llama-b9222-bin-win-cpu-x64",
            AppContext.BaseDirectory);
        ModelPathTextBox.Text = AppPaths.FirstExistingFile(
            @"D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q4_k_m-fixed.gguf",
            @"D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q4_k_m.gguf",
            @"D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-q3_k_s-fixed.gguf");
        ProjectorPathTextBox.Text = AppPaths.FirstExistingFile(
            @"D:\NaturaVisionPortable\wsl_recovery\gguf\forest-taxa-qwen35-4b-mmproj-f16.gguf");
        TestJsonlTextBox.Text = AppPaths.FirstExistingFile(
            @"D:\NaturaVisionPortable\portable_dataset\test.jsonl");

        AppendLog($"Katalog: {_catalog.PublicSpecies.Count} pozycji");
        DesktopStartupLog.Write("MainWindow constructor completed.");
    }

    private void ChooseImageButton_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Choose an organism image",
            Filter = "Image files (*.jpg;*.jpeg;*.png;*.webp)|*.jpg;*.jpeg;*.png;*.webp|All files (*.*)|*.*",
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        SetSelectedImage(dialog.FileName);
    }

    private async void ClassifyButton_Click(object sender, RoutedEventArgs e)
    {
        if (_selectedImagePath is null)
        {
            MessageBox.Show(this, "Najpierw wybierz obraz.", "NaturaVision", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        await RunSingleClassificationAsync(_selectedImagePath);
    }

    private async void CaptureScreenButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetBusy(true, "Zrzut ekranu...");
            AppendLog("Zaznacz obszar ekranu.");

            var baselineHash = TryGetClipboardImageHash();
            Process.Start(new ProcessStartInfo("ms-screenclip:") { UseShellExecute = true });

            for (var attempt = 0; attempt < 80; attempt++)
            {
                await Task.Delay(250);
                var image = TryGetClipboardImage();
                if (image is null)
                {
                    continue;
                }

                var hash = HashBitmap(image);
                if (baselineHash is not null && hash == baselineHash)
                {
                    continue;
                }

                var imagePath = SaveSnip(image);
                SetSelectedImage(imagePath);
                AppendLog($"Zapisano zrzut: {imagePath}");
                return;
            }

            MessageBox.Show(
                this,
                "Nie zapisano nowego zrzutu. Sprobuj ponownie.",
                "Zrzut ekranu",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            AppendLog("ERROR: " + ex);
            MessageBox.Show(this, ex.Message, "Zrzut ekranu", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SetBusy(false, "Ready");
        }
    }

    private void BrowseLlamaButton_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Choose llama-mtmd-cli.exe",
            Filter = "llama-mtmd-cli.exe|llama-mtmd-cli.exe|Executable files (*.exe)|*.exe|All files (*.*)|*.*",
            FileName = "llama-mtmd-cli.exe",
        };
        if (dialog.ShowDialog(this) == true)
        {
            LlamaBinTextBox.Text = Path.GetDirectoryName(dialog.FileName) ?? dialog.FileName;
        }
    }

    private void BrowseModelButton_Click(object sender, RoutedEventArgs e)
    {
        var path = ChooseFile("Wybierz model", "Pliki modelu (*.gguf)|*.gguf|Wszystkie pliki (*.*)|*.*");
        if (path is not null)
        {
            ModelPathTextBox.Text = path;
        }
    }

    private void BrowseProjectorButton_Click(object sender, RoutedEventArgs e)
    {
        var path = ChooseFile("Wybierz projektor", "Pliki modelu (*.gguf)|*.gguf|Wszystkie pliki (*.*)|*.*");
        if (path is not null)
        {
            ProjectorPathTextBox.Text = path;
        }
    }

    private void BrowseTestJsonlButton_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Choose test JSONL",
            Filter = "JSONL files (*.jsonl)|*.jsonl|All files (*.*)|*.*",
        };
        if (dialog.ShowDialog(this) == true)
        {
            TestJsonlTextBox.Text = dialog.FileName;
        }
    }

    private async void RunSuiteButton_Click(object sender, RoutedEventArgs e)
    {
        RunnerSettings settings;
        try
        {
            settings = ReadRunnerSettings();
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "Invalid settings", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (!int.TryParse(TestCountTextBox.Text, out var count) || count < 1)
        {
            count = 3;
        }

        try
        {
            SetBusy(true, "Test...");
            var examples = TestSuiteLoader.Load(TestJsonlTextBox.Text, count, _catalog);
            if (examples.Count == 0)
            {
                throw new InvalidOperationException("No test examples were loaded.");
            }

            var correct = 0;
            AppendLog($"Test: {examples.Count} przyklady");
            for (var index = 0; index < examples.Count; index++)
            {
                var example = examples[index];
                StatusText.Text = $"Test {index + 1}/{examples.Count}";
                AppendLog($"[{index + 1}/{examples.Count}] oczekiwano={example.ExpectedLabelId}");
                var result = await _runner.ClassifyAsync(settings with { ImagePath = example.ImagePath });
                if (result.PublicLabelId == example.ExpectedLabelId)
                {
                    correct++;
                }
                AppendLog($"[{index + 1}/{examples.Count}] wynik={result.PublicLabelId}");
            }

            var accuracy = (double)correct / examples.Count;
            PredictionLabelText.Text = $"Test: {correct}/{examples.Count}";
            PredictionDetailsText.Text = $"Skutecznosc: {accuracy:P1}";
            ClearPredictionMedia();
            PredictionExpander.IsExpanded = true;
            LogExpander.IsExpanded = true;
            AppendLog($"Test zakonczony: {accuracy:P3}");
        }
        catch (Exception ex)
        {
            AppendLog("ERROR: " + ex);
            MessageBox.Show(this, ex.Message, "Test suite failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SetBusy(false, "Ready");
        }
    }

    private async Task RunSingleClassificationAsync(string imagePath)
    {
        RunnerSettings settings;
        try
        {
            settings = ReadRunnerSettings() with { ImagePath = imagePath };
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "Invalid settings", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        try
        {
            SetBusy(true, "Rozpoznawanie...");
            AppendLog($"Obraz: {imagePath}");
            var result = await _runner.ClassifyAsync(settings);
            var species = _catalog.LookupPublic(result.PublicLabelId);
            PredictionLabelText.Text = $"{species.LabelId}: {species.PolishName}";
            PredictionDetailsText.Text = $"{species.ScientificName} | {species.EnglishName} | kingdom: {species.Kingdom}";
            ShowPredictionMedia(species);
            PredictionExpander.IsExpanded = true;
            AppendLog($"Wynik: {result.PublicLabelId}");
        }
        catch (Exception ex)
        {
            AppendLog("ERROR: " + ex);
            MessageBox.Show(this, ex.Message, "Classification failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SetBusy(false, "Ready");
        }
    }

    private RunnerSettings ReadRunnerSettings()
    {
        var llamaExe = Path.Combine(LlamaBinTextBox.Text.Trim(), "llama-mtmd-cli.exe");
        var modelPath = ModelPathTextBox.Text.Trim();
        var projectorPath = ProjectorPathTextBox.Text.Trim();

        if (!File.Exists(llamaExe))
        {
            throw new FileNotFoundException("llama-mtmd-cli.exe was not found.", llamaExe);
        }
        if (!File.Exists(modelPath))
        {
            throw new FileNotFoundException("Nie znaleziono modelu.", modelPath);
        }
        if (!File.Exists(projectorPath))
        {
            throw new FileNotFoundException("Nie znaleziono projektora.", projectorPath);
        }

        return new RunnerSettings(
            LlamaCliPath: llamaExe,
            ModelPath: modelPath,
            ProjectorPath: projectorPath,
            ImagePath: _selectedImagePath ?? string.Empty,
            ImageTokens: ParsePositiveInt(ImageTokensTextBox.Text, 32),
            MaxNewTokens: ParsePositiveInt(MaxTokensTextBox.Text, 24),
            GpuLayers: ParseNonNegativeInt(GpuLayersTextBox.Text, 0));
    }

    private void SetSelectedImage(string imagePath)
    {
        _selectedImagePath = imagePath;
        SelectedImageText.Text = imagePath;
        PreviewPlaceholder.Visibility = Visibility.Collapsed;

        var bitmap = new BitmapImage();
        bitmap.BeginInit();
        bitmap.UriSource = new Uri(imagePath, UriKind.Absolute);
        bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.EndInit();
        PreviewImage.Source = bitmap;
    }

    private void ShowPredictionMedia(SpeciesInfo species)
    {
        var media = _mediaCatalog.Lookup(species.LabelId);
        PredictionMediaPanel.Visibility = Visibility.Visible;
        PredictionDescriptionText.Text = BuildShortDescription(species, media);
        PredictionSourceText.Text = string.IsNullOrWhiteSpace(media?.SourceUrl)
            ? "Zrodlo: lokalny katalog gatunkow"
            : $"Zrodlo: {media.SourceUrl}";

        if (!string.IsNullOrWhiteSpace(media?.ResolvedImagePath))
        {
            PredictionSpeciesImage.Source = LoadBitmap(media.ResolvedImagePath);
            PredictionSpeciesImagePlaceholder.Visibility = Visibility.Collapsed;
        }
        else
        {
            PredictionSpeciesImage.Source = null;
            PredictionSpeciesImagePlaceholder.Visibility = Visibility.Visible;
        }
    }

    private void ClearPredictionMedia()
    {
        PredictionMediaPanel.Visibility = Visibility.Collapsed;
        PredictionSpeciesImage.Source = null;
        PredictionSpeciesImagePlaceholder.Visibility = Visibility.Visible;
        PredictionDescriptionText.Text = "Opis pojawi sie po rozpoznaniu.";
        PredictionSourceText.Text = string.Empty;
    }

    private void TaxonomyListView_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (TaxonomyListView.SelectedItem is not SpeciesInfo species)
        {
            return;
        }

        var media = _mediaCatalog.Lookup(species.LabelId);
        TaxonomyTitleText.Text = $"{species.LabelId}: {species.PolishName}";
        TaxonomyDescriptionText.Text = media?.Description
            ?? $"Brak opisu dla {species.ScientificName}.";
        TaxonomySourceText.Text = string.IsNullOrWhiteSpace(media?.SourceUrl) ? string.Empty : $"Zrodlo: {media.SourceUrl}";

        if (!string.IsNullOrWhiteSpace(media?.ResolvedImagePath))
        {
            TaxonomyImage.Source = LoadBitmap(media.ResolvedImagePath);
            TaxonomyImagePlaceholder.Visibility = Visibility.Collapsed;
        }
        else
        {
            TaxonomyImage.Source = null;
            TaxonomyImagePlaceholder.Visibility = Visibility.Visible;
        }
    }

    private static string BuildShortDescription(SpeciesInfo species, TaxonomyMedia? media)
    {
        var description = CompactText(media?.Description);
        if (string.IsNullOrWhiteSpace(description))
        {
            return $"Brak opisu z Wikipedii dla {species.ScientificName}.";
        }

        const int maxLength = 520;
        return description.Length <= maxLength
            ? description
            : description[..(maxLength - 3)] + "...";
    }

    private static string CompactText(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return string.Empty;
        }

        return string.Join(
            " ",
            text.Split(new[] { ' ', '\r', '\n', '\t' }, StringSplitOptions.RemoveEmptyEntries));
    }

    private static string? ChooseFile(string title, string filter)
    {
        var dialog = new OpenFileDialog
        {
            Title = title,
            Filter = filter,
        };
        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    private static int ParsePositiveInt(string text, int fallback)
    {
        return int.TryParse(text, out var value) && value > 0 ? value : fallback;
    }

    private static int ParseNonNegativeInt(string text, int fallback)
    {
        return int.TryParse(text, out var value) && value >= 0 ? value : fallback;
    }

    private void SetBusy(bool busy, string status)
    {
        StatusText.Text = status;
        ChooseImageButton.IsEnabled = !busy;
        CaptureScreenButton.IsEnabled = !busy;
        ClassifyButton.IsEnabled = !busy;
        RunSuiteButton.IsEnabled = !busy;
    }

    private void AppendLog(string text)
    {
        LogTextBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {text}{Environment.NewLine}");
        LogTextBox.ScrollToEnd();
    }

    private static BitmapSource? TryGetClipboardImage()
    {
        try
        {
            return Clipboard.ContainsImage() ? Clipboard.GetImage() : null;
        }
        catch
        {
            return null;
        }
    }

    private static string? TryGetClipboardImageHash()
    {
        var image = TryGetClipboardImage();
        return image is null ? null : HashBitmap(image);
    }

    private static string HashBitmap(BitmapSource image)
    {
        using var stream = new MemoryStream();
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        encoder.Save(stream);
        return Convert.ToHexString(SHA256.HashData(stream.ToArray()));
    }

    private static string SaveSnip(BitmapSource image)
    {
        var directory = Path.Combine(Path.GetTempPath(), "NaturaVisionSnips");
        Directory.CreateDirectory(directory);
        var path = Path.Combine(directory, $"snip-{DateTime.Now:yyyyMMdd-HHmmss}.png");
        using var stream = File.Create(path);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        encoder.Save(stream);
        return path;
    }

    private static BitmapImage LoadBitmap(string path)
    {
        var bitmap = new BitmapImage();
        bitmap.BeginInit();
        bitmap.UriSource = new Uri(path, UriKind.Absolute);
        bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.EndInit();
        return bitmap;
    }
}
