using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace NaturaVision.Desktop;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        DesktopStartupLog.Write("Application startup entered.");

        var window = new MainWindow();
        window.SourceInitialized += (_, _) => DesktopStartupLog.Write("MainWindow SourceInitialized.");
        window.Loaded += (_, _) => DesktopStartupLog.Write("MainWindow Loaded.");
        window.ContentRendered += (_, _) => DesktopStartupLog.Write("MainWindow ContentRendered.");
        MainWindow = window;
        window.Show();
        DesktopStartupLog.Write($"MainWindow Show called. IsVisible={window.IsVisible}, IsLoaded={window.IsLoaded}, WindowState={window.WindowState}.");
    }

    private static void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        DesktopStartupLog.Write("Unhandled exception: " + e.Exception);
    }
}

internal static class DesktopStartupLog
{
    private static readonly string LogPath = Path.Combine(Path.GetTempPath(), "naturavision-desktop.log");

    public static void Write(string message)
    {
        try
        {
            File.AppendAllText(LogPath, $"[{DateTime.Now:O}] {message}{Environment.NewLine}");
        }
        catch
        {
            // Startup logging must never prevent the UI from opening.
        }
    }
}
