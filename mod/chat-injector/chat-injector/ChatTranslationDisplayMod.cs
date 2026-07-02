using System;
using System.IO;
using System.Linq;
using System.Reflection;
using MelonLoader;
using UnityEngine;
using UnityEngine.UI;
using Il2CppAssets.Scripts.UI; // ChatBox

// TODO: Studio-/Spielname eintragen, siehe MelonLoader/Latest.log beim ersten Start
[assembly: MelonInfo(typeof(TD2ChatTranslationDisplay.ChatTranslationDisplayMod), "TD2 Chat Translation Display", "1.0.0", "Sebastian")]
[assembly: MelonGame(null, null)]

namespace TD2ChatTranslationDisplay
{
    public class ChatTranslationDisplayMod : MelonMod
    {
        // WICHTIG - Mehrinstanzen-Problem:
        // Wenn TD2 mehrfach gestartet wird (mehrere Prozesse aus demselben Installationsordner),
        // hätten alle Instanzen denselben festen Dateinamen "chat_translations_incoming.txt"
        // gepollt und damit gegenseitig ihre Übersetzungen angezeigt. Lösung: Jede TD2-Instanz
        // erzeugt beim Start eine eigene, neu benannte Log-Datei (das nutzt das Python-Tool
        // bereits, um pro Instanz einen eigenen Tab zu öffnen). Wir verwenden denselben
        // Log-Dateinamen als eindeutigen Sitzungs-Schlüssel für unsere eigene Eingabedatei -
        // dadurch bekommt jede Instanz automatisch ihren eigenen, isolierten Kanal.

        private static readonly string LogsDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            "Documents", "TTSK", "TrainDriver2", "Logs");

        private string _inputPath; // erst bekannt, sobald die eigene Session-Log-Datei gefunden wurde
        private DateTime _processStartTimeUtc;
        private bool _sessionResolved = false;
        private float _sessionResolveRetryTimer = 0f;
        private const float SessionResolveRetryIntervalSeconds = 1f;

        private static string GetUserDataDirectory()
        {
            string modsDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!;
            string gameDir = Path.GetDirectoryName(modsDir)!; // eine Ebene über "Mods" = TD2-Installationsordner
            string userDataDir = Path.Combine(gameDir, "MelonLoader", "UserData");
            Directory.CreateDirectory(userDataDir);
            return userDataDir;
        }

        private const float PollIntervalSeconds = 0.5f; // 2x pro Sekunde reicht für Chat-Tempo völlig aus
        private float _timeSinceLastPoll = 0f;

        // Farbe für die eingeblendeten Übersetzungen, damit sie sich optisch von normalen Chatnachrichten
        // abheben (Unity Text unterstützt Rich-Text-Tags wie <color=...> standardmäßig)
        private const string TranslationColorHex = "#33CCFF";

        private float _heartbeatTimer = 0f;

        public override void OnInitializeMelon()
        {
            // Prozessstart als Referenzzeitpunkt: nur Log-Dateien, die ab jetzt (mit kleiner
            // Toleranz) entstehen, gehören zu DIESER TD2-Instanz.
            _processStartTimeUtc = System.Diagnostics.Process.GetCurrentProcess().StartTime.ToUniversalTime();

            LoggerInstance.Msg("=== TD2 Chat Translation Display geladen ===");
            LoggerInstance.Msg("Warte auf eigene Session-Log-Datei in: " + LogsDirectory);
        }

        // Versucht, die zu dieser TD2-Instanz gehörende Log-Datei zu finden (die neueste Datei
        // mit "Log" im Namen, die nach dem eigenen Prozessstart erstellt wurde). Solange das
        // nicht gelingt (z.B. weil TD2 die Datei noch nicht angelegt hat), wird periodisch erneut
        // versucht - der Mod tut in der Zwischenzeit nichts anderes.
        private bool TryResolveSessionInputPath()
        {
            try
            {
                if (!Directory.Exists(LogsDirectory))
                    return false;

                // Kleine Toleranz nach hinten, falls TD2 die Log-Datei einen Sekundenbruchteil
                // vor dem MelonLoader-Start angelegt hat.
                DateTime cutoff = _processStartTimeUtc.AddSeconds(-5);

                var candidate = new DirectoryInfo(LogsDirectory)
                    .GetFiles("*", SearchOption.TopDirectoryOnly)
                    .Where(f => f.Name.Contains("Log") && f.CreationTimeUtc >= cutoff)
                    .OrderByDescending(f => f.CreationTimeUtc)
                    .FirstOrDefault();

                if (candidate == null)
                    return false;

                string sessionKey = Path.GetFileNameWithoutExtension(candidate.Name);
                string fileName = "chat_translations_incoming__" + sessionKey + ".txt";
                _inputPath = Path.Combine(GetUserDataDirectory(), fileName);

                LoggerInstance.Msg("Session-Log-Datei erkannt: " + candidate.Name);
                LoggerInstance.Msg("Beobachteter Pfad: " + _inputPath);
                return true;
            }
            catch (Exception ex)
            {
                LoggerInstance.Warning("Fehler beim Ermitteln der Session-Log-Datei: " + ex.Message);
                return false;
            }
        }

        public override void OnUpdate()
        {
            if (!_sessionResolved)
            {
                _sessionResolveRetryTimer += Time.deltaTime;
                if (_sessionResolveRetryTimer < SessionResolveRetryIntervalSeconds)
                    return;

                _sessionResolveRetryTimer = 0f;
                _sessionResolved = TryResolveSessionInputPath();
                if (!_sessionResolved)
                    return; // weiter warten, bis die eigene Log-Datei existiert
            }

            _timeSinceLastPoll += Time.deltaTime;
            if (_timeSinceLastPoll < PollIntervalSeconds)
                return;

            _timeSinceLastPoll = 0f;

            // Heartbeat alle ~5 Sekunden, damit wir sehen, dass OnUpdate() überhaupt läuft
            _heartbeatTimer += PollIntervalSeconds;
            if (_heartbeatTimer >= 5f)
            {
                _heartbeatTimer = 0f;
                LoggerInstance.Msg($"[Heartbeat] Polling aktiv. Datei existiert: {File.Exists(_inputPath)}. Pfad: {_inputPath}");
            }

            try
            {
                string[] newLines = ReadAndConsumeNewLines();
                if (newLines.Length > 0)
                {
                    LoggerInstance.Msg($"[Debug] {newLines.Length} neue Zeile(n) gefunden.");
                }

                foreach (string line in newLines)
                {
                    DisplayTranslatedLine(line);
                }
            }
            catch (Exception ex)
            {
                LoggerInstance.Error("Fehler beim Verarbeiten eingehender Übersetzungen: " + ex.Message);
            }
        }

        private string[] ReadAndConsumeNewLines()
        {
            if (!File.Exists(_inputPath))
                return Array.Empty<string>();

            // Datei lesen und sofort leeren, damit jede Zeile nur einmal angezeigt wird.
            // Kein Lock-Konflikt mit dem Python-Tool, solange dieses auch im "überschreiben"-Modus schreibt
            // (nicht anhängen) - siehe Hinweis am Ende der Antwort zur Python-Seite.
            string content;
            try
            {
                content = File.ReadAllText(_inputPath);
            }
            catch (IOException ex)
            {
                LoggerInstance.Warning("[Debug] Datei konnte nicht gelesen werden (evtl. gerade von anderem Prozess offen): " + ex.Message);
                return Array.Empty<string>();
            }

            if (string.IsNullOrWhiteSpace(content))
                return Array.Empty<string>();

            // Datei leeren, damit die Zeilen nicht erneut angezeigt werden
            try
            {
                File.WriteAllText(_inputPath, string.Empty);
            }
            catch (IOException)
            {
                // Falls Leeren fehlschlägt, lieber trotzdem anzeigen und beim nächsten Mal erneut versuchen
            }

            return content.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
        }

        private void DisplayTranslatedLine(string line)
        {
            var chatBox = ChatBox.Instance;
            if (chatBox == null)
            {
                LoggerInstance.Warning("[Debug] ChatBox.Instance ist null - Chat noch nicht bereit, Zeile wird verworfen: " + line);
                return;
            }

            var textComponent = chatBox.chatText;
            if (textComponent == null)
            {
                LoggerInstance.Warning("[Debug] chatBox.chatText ist null - kann nichts anzeigen.");
                return;
            }

            // Rich-Text-Farbe, damit die Zeile sich optisch von normalen Chatnachrichten abhebt.
            // Kein zusätzlicher Text-Präfix mehr nötig - das Python-Tool schickt den Sprachcode
            // (z.B. "[EN]", "[DE]") bereits als Teil von "line" mit.
            string formatted = $"<color={TranslationColorHex}>{line}</color>";

            try
            {
                // WICHTIG: Wir schreiben in _chatLog (den internen StringBuilder-Verlauf), nicht nur
                // in chatText.text. Grund: Das Spiel baut chatText.text bei jeder neuen echten
                // Chat-Nachricht komplett aus _chatLog neu auf - ein direktes Setzen von nur
                // chatText.text würde beim nächsten Chat-Event sofort wieder überschrieben.
                var chatLog = chatBox._chatLog;
                if (chatLog == null)
                {
                    LoggerInstance.Warning("[Debug] chatBox._chatLog ist null - kann Zeile nicht dauerhaft einfügen.");
                    return;
                }

                chatLog.Append("\n" + formatted);

                // chatText.text sofort synchron nachziehen, damit die Zeile ohne Verzögerung sichtbar wird
                // (nicht erst beim nächsten echten Chat-Event, das den Text ohnehin neu aus _chatLog baut)
                textComponent.text = chatLog.ToString();

                // WICHTIG: Das Spiel scrollt bei echten Chat-Nachrichten automatisch nach unten.
                // Das müssen wir hier händisch nachholen.
                var scrollRect = chatBox.chatTextScroll;
                if (scrollRect == null)
                {
                    LoggerInstance.Warning("[Debug] chatBox.chatTextScroll ist null - kann nicht scrollen.");
                }
                else
                {
                    float before = scrollRect.verticalNormalizedPosition;

                    // Layout-Rebuild erzwingen: Canvas.ForceUpdateCanvases() reicht bei
                    // ContentSizeFitter/VerticalLayoutGroup oft nicht aus, da die neue
                    // Content-Höhe erst nach einem expliziten Rebuild des Content-RectTransform
                    // bekannt ist.
                    if (scrollRect.content != null)
                    {
                        Canvas.ForceUpdateCanvases();
                        LayoutRebuilder.ForceRebuildLayoutImmediate(scrollRect.content);
                    }

                    scrollRect.verticalNormalizedPosition = 0f;
                    float after = scrollRect.verticalNormalizedPosition;

                    LoggerInstance.Msg($"[Debug] Scroll-Versuch. content vorhanden: {scrollRect.content != null}, " +
                                        $"verticalNormalizedPosition vorher: {before}, nachher (Soll 0): {after}");
                }
            }
            catch (Exception ex)
            {
                LoggerInstance.Error("[Debug] Exception beim Schreiben in _chatLog: " + ex);
            }
        }
    }
}
