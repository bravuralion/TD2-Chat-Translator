# nuitka-project: --onefile
# nuitka-project: --windows-console-mode=disable
# nuitka-project: --enable-plugin=pyqt6
# nuitka-project: --include-package-data=py3langid
# nuitka-project: --include-data-dir=res=res
# nuitka-project: --windows-icon-from-ico=res/Favicon.ico
# nuitka-project: --output-filename=TD2-Translator.exe
# nuitka-project: --output-dir=dist
# nuitka-project: --include-windows-runtime-dlls=yes

from email.mime import text
from math import dist
import os
import sys
import re
from xml.sax import handler
from PyQt6 import QtWidgets, QtGui, QtCore
import requests
from queue import Queue
from threading import Thread, Event
from PIL import Image, ImageQt
import httpcore
setattr(httpcore, 'SyncHTTPTransport', 'AsyncHTTPProxy')
from googletrans import Translator
from pynput import keyboard as pynput_keyboard
import csv
import time
from packaging import version
from concurrent.futures import ThreadPoolExecutor, thread
import json
from PyQt6.QtMultimedia import QSoundEffect
import py3langid as langid


langid.set_languages(['de', 'en', 'pl'])
_LANGID_TO_DEEPL_SOURCE = {"de": "DE", "en": "EN", "pl": "PL"}

current_version = "0.5.0"


APP_SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".td2_app_settings.json")

DEFAULT_CHAT_COLORS = {
    "fahrdienstleiter": "#DF7676",
    "translated": "#FFA500",
    "swdr": "#008000",
    "warning": "#FF0000",
    "default": "#FFFFFF",
}

I18N = {
    "language_names": {"de": "Deutsch", "en": "English", "pl": "Polski"},
    "select_ui_language_title": {"de": "Sprache wählen", "en": "Choose language", "pl": "Wybierz język"},
    "select_ui_language_label": {"de": "Interface-Sprache:", "en": "Interface language:", "pl": "Język interfejsu:"},

    "window_title": {
        "de": "Train Driver 2 Übersetzer {ver}",
        "en": "Train Driver 2 Translator  {ver}",
        "pl": "Train Driver 2 – Pomocnik Tłumaczeń {ver}"
    },
    "logs_path": {"de": "TD2 Logs Pfad:", "en": "TD2 Logs Path:", "pl": "Ścieżka do logów TD2:"},
    "browse": {"de": "Durchsuchen", "en": "Browse", "pl": "Przeglądaj"},
    "target_language": {"de": "Zielsprache:", "en": "Target Language:", "pl": "Język docelowy:"},
    "service": {"de": "Übersetzungsdienst:", "en": "Translation Service:", "pl": "Usługa tłumaczenia:"},
    "close_tab": {"de": "Tab schließen", "en": "Close Selected Tab", "pl": "Zamknij wybraną kartę"},
    "toggle_overlay": {"de": "Overlay umschalten", "en": "Toggle Overlay", "pl": "Przełącz overlay"},
    "driver_warnings": {"de": "Fahrerwarnungen", "en": "Driver Warnings", "pl": "Ostrzeżenia dla kierowców"},
    "chat_colors_label": {"de": "Farben:", "en": "Colors:", "pl": "Kolory:"},
    "color_fahrdienstleiter": {"de": "Fahrdienstleiter", "en": "Dispatcher", "pl": "Dyżurny ruchu"},
    "color_translated": {"de": "Spieler-Chat", "en": "Player Chat", "pl": "Czat gracza"},
    "color_swdr": {"de": "SWDR/System", "en": "SWDR/System", "pl": "SWDR/System"},
    "color_warning": {"de": "Warnungen", "en": "Warnings", "pl": "Ostrzeżenia"},
    "choose_color_title": {"de": "Farbe wählen", "en": "Choose Color", "pl": "Wybierz kolor"},
    "font_plus": {"de": "A+", "en": "A+", "pl": "A+"},
    "font_minus": {"de": "A−", "en": "A−", "pl": "A−"},
    "select_log_dir": {
        "de": "Log-Verzeichnis auswählen",
        "en": "Select Log Directory",
        "pl": "Wybierz katalog logów"
    },
    "update_available_title": {"de": "Update verfügbar", "en": "Update Available", "pl": "Dostępna aktualizacja"},
    "update_available_body": {
        "de": "Eine neue Version {ver} ist verfügbar. Der Download startet nach dem Bestätigen.",
        "en": "A new version {ver} is available. Download will start after confirmation.",
        "pl": "Nowa wersja {ver} jest dostępna. Pobieranie rozpocznie się po potwierdzeniu."
    },
    "warning_driver_lt_100": {
        "de": "ACHTUNG: FAHRER {name} hat vermutlich weniger als 100 km gefahren – Vorsicht!",
        "en": "ATTENTION: DRIVER {name} may drove less than 100 KM, be careful!",
        "pl": "UWAGA: KIEROWCA {name} przejechał mniej niż 100 KM – ostrożnie!"
    },

    "game_install_dir": {
        "de": "TD2-Ordner:",
        "en": "TD2 Folder:",
        "pl": "Folder TD2:"
    },
    "game_install_dir_tooltip": {
        "de": "TD2-Installationsordner (für die Ingame-Chat-Ausgabe des Mods)",
        "en": "TD2 install directory (for the mod's ingame chat output)",
        "pl": "Katalog instalacji TD2 (dla czatu w grze przez moda)"
    },
    "select_game_dir": {
        "de": "TD2-Installationsordner auswählen",
        "en": "Select TD2 Install Directory",
        "pl": "Wybierz katalog instalacji TD2"
    },
    "game_dir_warning_title": {"de": "Hinweis", "en": "Notice", "pl": "Informacja"},
    "game_dir_warning_body": {
        "de": "In diesem Ordner wurde kein 'MelonLoader'-Unterordner gefunden. "
              "Bitte prüfe, ob du wirklich den TD2-Installationsordner ausgewählt hast.",
        "en": "No 'MelonLoader' subfolder was found in this directory. "
              "Please check whether you really selected the TD2 install directory.",
        "pl": "W tym katalogu nie znaleziono podkatalogu 'MelonLoader'. "
              "Sprawdź, czy wybrano właściwy katalog instalacji TD2."
    },

    "own_username": {
        "de": "Benutzername:",
        "en": "Username:",
        "pl": "Nazwa użytk.:"
    },
    "own_username_tooltip": {
        "de": "Eigener Benutzername/ID (optional) - damit eigene Nachrichten nicht übersetzt werden",
        "en": "Your own username/ID (optional) - so your own messages won't be translated",
        "pl": "Twoja nazwa użytkownika/ID (opcjonalnie) - aby własne wiadomości nie były tłumaczone"
    },
    "own_username_placeholder": {
        "de": "leer lassen, um alle Nachrichten zu übersetzen",
        "en": "leave empty to translate all messages",
        "pl": "pozostaw puste, aby tłumaczyć wszystkie wiadomości"
    },

    "game_chat_write_error_title": {
        "de": "Ingame-Chat-Ausgabe fehlgeschlagen",
        "en": "Ingame Chat Output Failed",
        "pl": "Błąd zapisu czatu w grze"
    },
    "game_chat_write_error_body": {
        "de": "Konnte keine Übersetzung in die Ingame-Chat-Datei schreiben.\n\n"
              "Fehler: {error}\n\n"
              "Häufigster Grund: Dein TD2-Ordner liegt unter 'Program Files', wo Windows "
              "Schreibzugriff ohne Administratorrechte oft verweigert. Starte das Tool als "
              "Administrator, oder installiere TD2 außerhalb von 'Program Files'.\n\n"
              "(Dieser Hinweis erscheint nur einmal pro Sitzung.)",
        "en": "Could not write a translation to the ingame chat file.\n\n"
              "Error: {error}\n\n"
              "Most common cause: Your TD2 folder is under 'Program Files', where Windows "
              "often denies write access without administrator rights. Try running this tool "
              "as administrator, or install TD2 outside of 'Program Files'.\n\n"
              "(This notice only appears once per session.)",
        "pl": "Nie udało się zapisać tłumaczenia do pliku czatu w grze.\n\n"
              "Błąd: {error}\n\n"
              "Najczęstsza przyczyna: Twój folder TD2 znajduje się w 'Program Files', gdzie "
              "Windows często odmawia zapisu bez praw administratora. Uruchom to narzędzie "
              "jako administrator albo zainstaluj TD2 poza 'Program Files'.\n\n"
              "(Ten komunikat pojawia się tylko raz na sesję.)"
    }
}

def load_app_settings():
    try:
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_app_settings(data: dict):
    try:
        with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def resource_path(relative_path):
    try:
        # Nuitka (standalone/onefile): __compiled__ ist ein von Nuitka
        # injiziertes Modul-Global, existiert nur im kompilierten Build.
        if __compiled__.onefile:  # noqa: F821
            # Bei --onefile zeigt __compiled__.containing_dir auf den Ordner
            # der .exe-Datei selbst (z.B. dist\), NICHT auf das Temp-
            # Verzeichnis, in das Nuitka zur Laufzeit entpackt - und genau
            # dorthin gehoeren die per --include-data-dir mitgelieferten
            # Ressourcen (res\...). __file__ zeigt dagegen korrekt auf die
            # entpackte Kopie dieses Moduls im Temp-Verzeichnis.
            base_path = os.path.dirname(os.path.abspath(__file__))
        else:
            # Standalone (nicht onefile): hier liegen die Ressourcen
            # tatsaechlich direkt neben der .exe, containing_dir stimmt.
            base_path = __compiled__.containing_dir  # noqa: F821
    except NameError:
        # PyInstaller-Fallback (frueherer Build-Weg) bzw. normaler Skriptlauf.
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def find_td2_logs_dir():
    home = os.path.expanduser("~")
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")

    candidates = [
        os.path.join(home, "Documents", "TTSK", "TrainDriver2", "Logs"),
        os.path.join(home, "Dokumente", "TTSK", "TrainDriver2", "Logs"),
    ]
    if onedrive:
        candidates.append(os.path.join(onedrive, "Documents", "TTSK", "TrainDriver2", "Logs"))
        candidates.append(os.path.join(onedrive, "Dokumente", "TTSK", "TrainDriver2", "Logs"))
    candidates.append(os.path.join(home, "OneDrive", "Documents", "TTSK", "TrainDriver2", "Logs"))
    candidates.append(os.path.join(home, "OneDrive", "Dokumente", "TTSK", "TrainDriver2", "Logs"))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]

try:
    from local_config import API_BASE_URL, APP_TOKEN
except ImportError as exc:
    raise ImportError(
        "local_config.py fehlt. Bitte local_config.sample.py im selben "
        "Ordner zu local_config.py kopieren und mit den echten Werten "
        "ausfuellen, bevor du das Programm startest oder baust."
    ) from exc

ENABLE_GAME_CHAT_INTEGRATION = False

class TranslationWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(list)
    def __init__(self, handler, lines):
        super().__init__()
        self.handler = handler
        self.lines = lines
        self.cancelled = False

    def run(self):
        if self.cancelled:
            return
        results = self.handler.translate_lines(self.lines)
        if not self.cancelled:
            self.finished.emit(results)

def load_ignore_list(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return {line.strip() for line in file}

def load_fixed_translations(filepath):
    fixed_translations = {}
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            text0 = row['text'].strip().lower()
            language = row['language'].strip()
            translation = row['translation'].strip()
            if text0 not in fixed_translations:
                fixed_translations[text0] = {}
            fixed_translations[text0][language] = translation
    return fixed_translations

class LogHandler(QtCore.QObject):
    lines_translated = QtCore.pyqtSignal(list)
    play_warning_sound = QtCore.pyqtSignal()

    def __init__(self, log_file_path, language_var, service_var, ignore_list, fixed_translations, enable_driver_warning, ui_lang, own_username):
        super().__init__()
        self.log_file_path = log_file_path
        self.file = open(log_file_path, 'r', encoding='utf-8')
        self.language_var = language_var
        self.service_var = service_var
        self.ignore_list = ignore_list
        self.fixed_translations = fixed_translations
        self.translator = Translator()
        self.last_position = self.file.tell()
        self.stop_event = Event()
        self.warning_sound = QSoundEffect()
        self.warning_sound.setSource(QtCore.QUrl.fromLocalFile(resource_path("res/timer_alarm.wav")))
        self.warning_sound.setLoopCount(1)
        self.warning_sound.setVolume(0.8)
        self.play_warning_sound.connect(self.warning_sound.play)
        self.warned_drivers = set()
        self.enable_driver_warning = enable_driver_warning
        self.ui_lang = ui_lang
        self.own_username = own_username

    @staticmethod
    def extract_sender_candidates(timestamp_user):
        match = re.search(r'([^\s@]+)@([^\s:]+)', timestamp_user)
        if not match:
            return []
        return [match.group(1), match.group(2)]

    def get_driver_distance(self, name):
        try:
            url = f"https://stacjownik.spythere.eu/api/getDriverInfo?name={name}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                d = data.get("_sum", {}).get("currentDistance")
                if isinstance(d, (int, float)):
                    return d
            return None
        except Exception:
            return None

    @staticmethod
    def contains_time(line):
        return re.search(r'\(\d{2}:\d{2}:\d{2}\)', line) is not None

    @staticmethod
    def clean_chat_message(line):
        chat_message = re.search(r'ChatMessage: (.*)', line)
        if chat_message:
            return re.sub(r'<.*?>', '', chat_message.group(1))
        return ""

    def check_new_lines(self):
        if self.stop_event.is_set() or not self.file:
            return
        self.file.seek(self.last_position)
        lines = []
        while True:
            line = self.file.readline()
            if not line:
                break
            if "ChatMessage:" in line and self.contains_time(line):
                clean_line = self.clean_chat_message(line)
                if clean_line:
                    lines.append(clean_line)
        if lines:
            self.last_position = self.file.tell()
            self.lines_translated.emit(lines)

    def translate_lines(self, lines):
        translated_lines = []
        items = []

        current_target_language = self.language_var() if callable(self.language_var) else self.language_var
        translation_service = self.service_var() if callable(self.service_var) else self.service_var
        self.target_language = current_target_language

        for line in lines:
            match_fd = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) ([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż].*?@[^: ]+)(: | )(.*)$', line)
            match_player = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) (\d+@[^: ]+)(: | )(.*)$', line)
            match_swdr = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) \[(.*? \((.*?)\))\] (.*)$', line)
            if match_fd:
                timestamp_user, message = match_fd.group(1) + "(" + match_fd.group(2) + ") " + match_fd.group(3), match_fd.group(5).strip()
                tag = "fahrdienstleiter"
            elif match_player:
                timestamp_user, message = match_player.group(1) + "(" + match_player.group(2) + ") " + match_player.group(3), match_player.group(5).strip()
                tag = "translated"
            elif match_swdr:
                timestamp_user, message = match_swdr.group(1) + "(" + match_swdr.group(2) + ") [" + match_swdr.group(3) + "]", match_swdr.group(5).strip()
                tag = "swdr"
            else:
                continue
            if message in self.ignore_list:
                continue


            own_username_value = self.own_username() if callable(self.own_username) else self.own_username
            if own_username_value:
                own_username_normalized = own_username_value.strip().casefold()
                sender_candidates = self.extract_sender_candidates(timestamp_user)
                if any(c.strip().casefold() == own_username_normalized for c in sender_candidates):
                    continue

            driver_name = None
            dist_val = None
            username_match = re.search(r'@([^\s:]+)', timestamp_user)
            if username_match:
                driver_name = username_match.group(1)
                if not hasattr(self, "_driver_cache"):
                    self._driver_cache = {}
                if driver_name not in self._driver_cache:
                    self._driver_cache[driver_name] = self.get_driver_distance(driver_name)
                dist_val = self._driver_cache.get(driver_name)


            if driver_name and self.enable_driver_warning():
                if (dist_val is None or (isinstance(dist_val, (int, float)) and dist_val < 100)) and driver_name not in self.warned_drivers:
                    warning = I18N["warning_driver_lt_100"].get(self.ui_lang, I18N["warning_driver_lt_100"]["en"]).format(name=driver_name)
                    translated_lines.append((warning, "warning", True))
                    self.play_warning_sound.emit()
                    self.warned_drivers.add(driver_name)

            text_lower = message.lower()
            fixed = None
            if (
                text_lower in self.fixed_translations
                and current_target_language in self.fixed_translations[text_lower]
            ):
                fixed = self.fixed_translations[text_lower][current_target_language]

            items.append({
                "timestamp_user": timestamp_user,
                "tag": tag,
                "message": message,
                "fixed": fixed,
            })

        pending = [it for it in items if it["fixed"] is None]

        if pending:
            if translation_service == "Deepl":
                target_lang_code = self.get_deepl_language_code(current_target_language)

                groups = {}
                for it in pending:
                    it["source_lang"] = self._detect_source_lang(it["message"])
                    groups.setdefault(it["source_lang"], []).append(it)

                for source_lang, group_items in groups.items():
                    results = self._translate_deepl_batch(
                        [it["message"] for it in group_items], target_lang_code, source_lang
                    )
                    for it, result in zip(group_items, results):
                        it["translated"] = result
            else:
                # Google Translate: seriell (max_workers=1), da die inoffizielle
                # Bibliothek bei paralleler Nutzung leicht ins Rate-Limiting läuft.
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future_map = {
                        executor.submit(self.translate_with_google, it["message"]): it
                        for it in pending
                    }
                    for future in future_map:
                        future_map[future]["translated"] = future.result()

        for it in items:
            translation = it["fixed"] if it["fixed"] is not None else it.get("translated", it["message"])
            translation = re.sub(r'【[^】]*】', '', translation).strip()
            is_unchanged = translation.strip().casefold() == it["message"].strip().casefold()
            translated_lines.append((f"{it['timestamp_user']}: {translation}", it["tag"], is_unchanged))

        return translated_lines

    @staticmethod
    def _detect_source_lang(text):
        try:
            lang_code, _confidence = langid.classify(text)
        except Exception:
            return "EN"
        return _LANGID_TO_DEEPL_SOURCE.get(lang_code, "EN")

    def _translate_deepl_batch(self, texts, target_lang_code, source_lang_code):
        if not target_lang_code:
            return [f"Target language '{self.target_language}' not supported by Deepl" for _ in texts]

        results = []
        chunk_size = 25  # bleibt unter dem serverseitigen max_batch_size
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i + chunk_size]
            try:
                resp = requests.post(
                    API_BASE_URL,
                    json={
                        "target_lang": target_lang_code,
                        "source_lang": source_lang_code,
                        "texts": chunk,
                    },
                    headers={"X-App-Token": APP_TOKEN, "Content-Type": "application/json"},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                translations = data.get("translations", [])
                if len(translations) != len(chunk):
                    raise ValueError("Unexpected response from translation server")
                results.extend(translations)
            except Exception as e:
                results.extend([f"[Translation Error] {e}"] * len(chunk))
        return results

    def translate_with_google(self, text):
        try:
            result = self.translator.translate(text, dest=self.target_language)
            if hasattr(result, "__await__"):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                result = loop.run_until_complete(result)
            return result.text
        except Exception as e:
            return str(e)

    @staticmethod
    def get_deepl_language_code(language):
        language_codes = {
            "Bulgarian": "BG",
            "Czech": "CS",
            "Danish": "DA",
            "German": "DE",
            "Greek": "EL",
            "English": "EN-GB",
            "American English": "EN-US",
            "Spanish": "ES",
            "Estonian": "ET",
            "Finnish": "FI",
            "French": "FR",
            "Hungarian": "HU",
            "Italian": "IT",
            "Japanese": "JA",
            "Lithuanian": "LT",
            "Latvian": "LV",
            "Dutch": "NL",
            "Polish": "PL",
            "Portuguese": "PT-PT",
            "Brazilian Portuguese": "PT-BR",
            "Romanian": "RO",
            "Russian": "RU",
            "Slovak": "SK",
            "Slovenian": "SL",
            "Swedish": "SV",
            "Chinese": "ZH"
        }
        return language_codes.get(language, None)


    @staticmethod
    def get_short_language_code(language):
        short_codes = {
            "English": "EN",
            "American English": "EN",
            "German": "DE",
            "Polish": "PL",
            "French": "FR",
            "Spanish": "ES",
            "Italian": "IT",
            "Dutch": "NL",
            "Portuguese": "PT",
            "Brazilian Portuguese": "PT",
            "Greek": "EL",
            "Swedish": "SV",
            "Danish": "DA",
            "Finnish": "FI",
            "Norwegian": "NO",
            "Czech": "CS",
            "Slovak": "SK",
            "Hungarian": "HU",
            "Romanian": "RO",
            "Bulgarian": "BG",
            "Croatian": "HR",
            "Serbian": "SR",
            "Slovenian": "SL",
            "Estonian": "ET",
            "Latvian": "LV",
            "Lithuanian": "LT",
            "Maltese": "MT",
            "Russian": "RU"
        }
        return short_codes.get(language, language[:2].upper())

class OverlayWindow(QtWidgets.QWidget):
    SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".td2_overlay_settings.json")

    def __init__(self, parent=None, dark_mode=True, font_size=10):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Window
        )
        self.setWindowOpacity(0.95)
        self.resize(400, 200)
        self.setMinimumSize(200, 100)
        self.font_size = font_size
        self.text_edit = QtWidgets.QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.setFont(QtGui.QFont("Helvetica", self.font_size, QtGui.QFont.Weight.Bold))
        self.text_edit.setStyleSheet(
            f"background-color: {'#3E3E3E' if dark_mode else '#FFFFFF'};"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
        self._drag_pos = None

        self.size_grip = QtWidgets.QSizeGrip(self)
        layout.addWidget(self.size_grip, 0, QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignRight)

        self.load_overlay_settings()

    def load_overlay_settings(self):
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pos = data.get("pos")
                    size = data.get("size")
                    if pos:
                        self.move(pos[0], pos[1])
                    if size:
                        self.resize(size[0], size[1])
        except Exception:
            pass

    def save_overlay_settings(self):
        try:
            data = {
                "pos": [self.x(), self.y()],
                "size": [self.width(), self.height()]
            }
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def moveEvent(self, event):
        self.save_overlay_settings()
        super().moveEvent(event)

    def resizeEvent(self, event):
        self.save_overlay_settings()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def change_font_size(self, delta):
        self.font_size = max(6, self.font_size + delta)
        self.text_edit.setFont(QtGui.QFont("Helvetica", self.font_size, QtGui.QFont.Weight.Bold))

class App(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()


        self.app_settings = load_app_settings()
        self.ui_lang = self.app_settings.get("ui_language")
        if self.ui_lang not in ("de", "en", "pl"):
            self.ui_lang = self._ask_ui_language()
            self.app_settings["ui_language"] = self.ui_lang
            save_app_settings(self.app_settings)
        self._t = lambda key, **kw: I18N[key][self.ui_lang].format(**kw)

        self.setWindowTitle(self._t("window_title", ver=current_version))
        self.overlay_window = None
        self.overlay_font_size = self.app_settings.get("overlay_font_size", 10)

        icon_path = resource_path(os.path.join('res', 'Favicon.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.ignore_list = load_ignore_list(resource_path(os.path.join('res', 'ignore_list.csv')))
        self.fixed_translations = load_fixed_translations(resource_path(os.path.join('res', 'fixed_translations.csv')))

        self.language_var = "English"
        self.service_var = "Deepl"
        self.is_dark_mode = True
        self.enable_driver_warning = True

        self.handlers = []
        self.opened_logs = set()
        self.latest_log_time = None
        self.directory_path = self.app_settings.get("logs_directory", "")
        if not self.directory_path:
            auto_detected = find_td2_logs_dir()
            if os.path.isdir(auto_detected):
                self.directory_path = auto_detected

        self.game_install_dir = self.app_settings.get("game_install_dir", "")

        self.own_username = self.app_settings.get("own_username", "")

        saved_colors = self.app_settings.get("chat_colors", {})
        self.chat_colors = dict(DEFAULT_CHAT_COLORS)
        self.chat_colors.update(saved_colors)
        self.known_logs = {}
        self.tab_widget = None
        self.init_ui()
        self.apply_theme()
        self.global_hotkey_listener = pynput_keyboard.Listener(on_press=self._on_global_key)
        self.global_hotkey_listener.start()
        f10_shortcut = QtGui.QShortcut(QtGui.QKeySequence("F10"), self)
        f10_shortcut.activated.connect(self.toggle_overlay)
        self._overlay_sync_state = {}
        self.start_update_check()

    def _ask_ui_language(self) -> str:
        items = [I18N["language_names"]["de"], I18N["language_names"]["en"], I18N["language_names"]["pl"]]
        reverse = {
            I18N["language_names"]["de"]: "de",
            I18N["language_names"]["en"]: "en",
            I18N["language_names"]["pl"]: "pl",
        }

        choice, ok = QtWidgets.QInputDialog.getItem(
            self,
            I18N["select_ui_language_title"]["en"],
            I18N["select_ui_language_label"]["en"],
            items,
            0,
            False
        )
        if ok and choice in reverse:
            return reverse[choice]
        return "en"

    def _on_global_key(self, key):
        try:
            if key == pynput_keyboard.Key.f10:
                QtCore.QTimer.singleShot(0, self.toggle_overlay)
        except Exception:
            pass

    def init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)


        top_layout = QtWidgets.QHBoxLayout()
        img_path = resource_path(os.path.join('res', 'image.png'))
        if os.path.exists(img_path):
            img = Image.open(img_path).resize((80, 40), Image.LANCZOS)
            qt_img = ImageQt.ImageQt(img)
            pixmap = QtGui.QPixmap.fromImage(qt_img)
            img_label = QtWidgets.QLabel()
            img_label.setPixmap(pixmap)
            top_layout.addWidget(img_label)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)


        file_label = QtWidgets.QLabel(self._t("logs_path"))
        self.file_entry = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton(self._t("browse"))
        browse_btn.clicked.connect(self.browse_directory)
        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.file_entry)
        file_row.addWidget(browse_btn)
        form_layout.addRow(file_label, file_row)


        if ENABLE_GAME_CHAT_INTEGRATION:
            game_dir_label = QtWidgets.QLabel(self._t("game_install_dir"))
            game_dir_label.setToolTip(self._t("game_install_dir_tooltip"))
            self.game_dir_entry = QtWidgets.QLineEdit()
            self.game_dir_entry.setText(self.game_install_dir)
            self.game_dir_entry.setToolTip(self._t("game_install_dir_tooltip"))
            game_dir_browse_btn = QtWidgets.QPushButton(self._t("browse"))
            game_dir_browse_btn.clicked.connect(self.browse_game_directory)
            game_dir_row = QtWidgets.QHBoxLayout()
            game_dir_row.addWidget(self.game_dir_entry)
            game_dir_row.addWidget(game_dir_browse_btn)
            form_layout.addRow(game_dir_label, game_dir_row)


        own_username_label = QtWidgets.QLabel(self._t("own_username"))
        own_username_label.setToolTip(self._t("own_username_tooltip"))
        self.own_username_entry = QtWidgets.QLineEdit()
        self.own_username_entry.setText(self.own_username)
        self.own_username_entry.setPlaceholderText(self._t("own_username_placeholder"))
        self.own_username_entry.setToolTip(self._t("own_username_tooltip"))
        self.own_username_entry.editingFinished.connect(self.save_own_username)
        form_layout.addRow(own_username_label, self.own_username_entry)

        top_layout.addLayout(form_layout)
        main_layout.addLayout(top_layout)


        frame2 = QtWidgets.QHBoxLayout()
        frame2.addWidget(QtWidgets.QLabel(self._t("target_language")))
        language_values = ["English", "American English", "German", "Polish", "French", "Spanish", "Italian", "Dutch",
                           "Portuguese", "Brazilian Portuguese", "Greek", "Swedish", "Danish", "Finnish", "Norwegian",
                           "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Croatian", "Serbian", "Slovenian",
                           "Estonian", "Latvian", "Lithuanian", "Maltese", "Russian"]
        self.language_combobox = QtWidgets.QComboBox()
        self.language_combobox.addItems(language_values)
        self.language_combobox.setCurrentText(self.language_var)
        self.language_combobox.currentTextChanged.connect(lambda val: setattr(self, "language_var", val))
        frame2.addWidget(self.language_combobox)

        frame2.addWidget(QtWidgets.QLabel(self._t("service")))
        service_values = ["Google Translate", "Deepl"]
        self.service_combobox = QtWidgets.QComboBox()
        self.service_combobox.addItems(service_values)
        self.service_combobox.setCurrentText(self.service_var)
        self.service_combobox.currentTextChanged.connect(lambda val: setattr(self, "service_var", val))
        frame2.addWidget(self.service_combobox)
        main_layout.addLayout(frame2)


        frame3 = QtWidgets.QHBoxLayout()
        close_tab_btn = QtWidgets.QPushButton(self._t("close_tab"))
        close_tab_btn.clicked.connect(self.close_selected_tab)
        frame3.addWidget(close_tab_btn)
        overlay_btn = QtWidgets.QPushButton(self._t("toggle_overlay"))
        overlay_btn.clicked.connect(self.toggle_overlay)
        frame3.addWidget(overlay_btn)
        aplus_btn = QtWidgets.QPushButton(self._t("font_plus"))
        aplus_btn.clicked.connect(lambda: self.change_overlay_font_size(1))
        frame3.addWidget(aplus_btn)
        aminus_btn = QtWidgets.QPushButton(self._t("font_minus"))
        aminus_btn.clicked.connect(lambda: self.change_overlay_font_size(-1))
        frame3.addWidget(aminus_btn)
        self.warning_checkbox = QtWidgets.QCheckBox(self._t("driver_warnings"))
        self.warning_checkbox.stateChanged.connect(lambda state: setattr(self, "enable_driver_warning", state == QtCore.Qt.CheckState.Checked))
        frame3.addWidget(self.warning_checkbox)

        main_layout.addLayout(frame3)

        frame_colors = QtWidgets.QHBoxLayout()
        frame_colors.addWidget(QtWidgets.QLabel(self._t("chat_colors_label")))

        self.color_buttons = {}
        color_keys_and_labels = [
            ("fahrdienstleiter", "color_fahrdienstleiter"),
            ("translated", "color_translated"),
            ("swdr", "color_swdr"),
            ("warning", "color_warning"),
        ]
        for color_key, label_key in color_keys_and_labels:
            frame_colors.addWidget(QtWidgets.QLabel(self._t(label_key)))
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(28, 20)
            btn.setStyleSheet(f"background-color: {self.chat_colors[color_key]}; border: 1px solid #888;")
            btn.clicked.connect(lambda checked, k=color_key: self.pick_chat_color(k))
            self.color_buttons[color_key] = btn
            frame_colors.addWidget(btn)

        frame_colors.addStretch()
        main_layout.addLayout(frame_colors)


        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_selected_tab)
        main_layout.addWidget(self.tab_widget)

        if self.directory_path and os.path.isdir(self.directory_path):
            if not self._activate_log_directory(self.directory_path, save=False):
                self.directory_path = ""

    def _activate_log_directory(self, directory_path, save=True):
        if not directory_path or not os.path.isdir(directory_path):
            return False

        self.directory_path = directory_path
        self.file_entry.setText(directory_path)

        if save:
            self.app_settings["logs_directory"] = directory_path
            save_app_settings(self.app_settings)

        newest = self.find_newest_log_file(directory_path)
        if newest:
            self.open_log_in_new_tab(newest)
            self.latest_log_time = os.path.getctime(newest)

        self.record_all_logs()
        self.monitor_new_logs()
        return True

    def browse_directory(self):
        dialog = QtWidgets.QFileDialog(self)
        directory_path = dialog.getExistingDirectory(
            self,
            self._t("select_log_dir"),
            self.directory_path or find_td2_logs_dir()
        )
        if directory_path:
            self._activate_log_directory(directory_path)

    def browse_game_directory(self):
        dialog = QtWidgets.QFileDialog(self)
        directory_path = dialog.getExistingDirectory(
            self,
            self._t("select_game_dir"),
            self.game_install_dir or os.path.expanduser("~")
        )
        if directory_path:
            if not os.path.isdir(os.path.join(directory_path, "MelonLoader")):
                QtWidgets.QMessageBox.warning(
                    self,
                    self._t("game_dir_warning_title"),
                    self._t("game_dir_warning_body")
                )
            self.game_install_dir = directory_path
            self.game_dir_entry.setText(directory_path)
            self.app_settings["game_install_dir"] = directory_path
            save_app_settings(self.app_settings)

    def save_own_username(self):
        value = self.own_username_entry.text().strip()
        self.own_username = value
        self.app_settings["own_username"] = value
        save_app_settings(self.app_settings)

    def pick_chat_color(self, color_key):
        current = QtGui.QColor(self.chat_colors.get(color_key, "#FFFFFF"))
        chosen = QtWidgets.QColorDialog.getColor(current, self, self._t("choose_color_title"))
        if not chosen.isValid():
            return
        hex_color = chosen.name()
        self.chat_colors[color_key] = hex_color
        self.color_buttons[color_key].setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")
        self.app_settings["chat_colors"] = self.chat_colors
        save_app_settings(self.app_settings)

    def get_game_chat_file_path(self, log_file_path):
        if not ENABLE_GAME_CHAT_INTEGRATION:
            return None
        if not self.game_install_dir or not os.path.isdir(self.game_install_dir):
            return None
        user_data_dir = os.path.join(self.game_install_dir, "MelonLoader", "UserData")
        os.makedirs(user_data_dir, exist_ok=True)
        session_key = os.path.splitext(os.path.basename(log_file_path))[0]
        return os.path.join(user_data_dir, f"chat_translations_incoming__{session_key}.txt")

    def write_to_game_chat(self, text, log_file_path):
        try:
            path = self.get_game_chat_file_path(log_file_path)
            if not path:
                return
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception as e:
            self._report_game_chat_write_error(e)

    def _report_game_chat_write_error(self, exception):
        if getattr(self, "_game_chat_write_error_shown", False):
            return
        self._game_chat_write_error_shown = True
        QtCore.QMetaObject.invokeMethod(
            self, "_show_game_chat_write_error", QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, str(exception))
        )

    @QtCore.pyqtSlot(str)
    def _show_game_chat_write_error(self, error_text):
        QtWidgets.QMessageBox.warning(
            self,
            self._t("game_chat_write_error_title"),
            self._t("game_chat_write_error_body", error=error_text)
        )

    def record_all_logs(self):
        if not self.directory_path:
            return
        log_files = [os.path.join(self.directory_path, f) for f in os.listdir(self.directory_path)
                     if os.path.isfile(os.path.join(self.directory_path, f)) and "Log" in f]
        for lf in log_files:
            self.known_logs[lf] = os.path.getmtime(lf)

    def find_newest_log_file(self, directory_path):
        log_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path)
                     if os.path.isfile(os.path.join(directory_path, f)) and "Log" in f]
        if not log_files:
            return None
        return max(log_files, key=os.path.getctime)

    def open_log_in_new_tab(self, log_file_path):
        if log_file_path in self.opened_logs:
            return
        self.opened_logs.add(log_file_path)
        text_area = QtWidgets.QTextEdit()
        text_area.setReadOnly(True)
        text_area.setFont(QtGui.QFont("Helvetica", 10))
        idx = self.tab_widget.addTab(text_area, os.path.basename(log_file_path))
        handler = LogHandler(
            log_file_path=log_file_path,
            language_var=lambda: self.language_var,
            service_var=lambda: self.service_var,
            ignore_list=self.ignore_list,
            fixed_translations=self.fixed_translations,
            enable_driver_warning=lambda: self.warning_checkbox.isChecked(),
            ui_lang=self.ui_lang,
            own_username=lambda: self.own_username
        )
        handler.setParent(self)
        handler.lines_translated.connect(lambda lines: self.process_lines(handler, text_area, lines))
        handler.file.seek(0, os.SEEK_END)
        latest_message = None
        while True:
            line = handler.file.readline()
            if not line:
                break
            if "ChatMessage:" in line and handler.contains_time(line):
                clean_line = handler.clean_chat_message(line)
                if clean_line:
                    latest_message = clean_line
        if latest_message:
            handler.lines_translated.emit([latest_message])
        handler.last_position = handler.file.tell()
        timer = QtCore.QTimer(self)
        timer.timeout.connect(handler.check_new_lines)
        timer.start(5000)
        self.handlers.append((handler, text_area, timer, idx))

    def monitor_new_logs(self):
        if self.directory_path:
            log_files = [os.path.join(self.directory_path, f) for f in os.listdir(self.directory_path)
                         if os.path.isfile(os.path.join(self.directory_path, f)) and "Log" in f]
        else:
            log_files = []
        for lf in log_files:
            mtime = os.path.getmtime(lf)
            if lf not in self.opened_logs:
                old_mtime = self.known_logs.get(lf, None)
                if old_mtime is not None and mtime > old_mtime:
                    self.open_log_in_new_tab(lf)
            self.known_logs[lf] = mtime

        QtCore.QTimer.singleShot(10000, self.monitor_new_logs)

    def apply_theme(self):

        bg_color = "#2E2E2E"
        fg_color = "#FFFFFF"
        text_area_bg = "#3E3E3E"
        text_area_fg = "#FFFFFF"
        button_bg = "#4E4E4E"
        button_fg = "#FFFFFF"

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; color: {fg_color}; }}
            QLineEdit, QTextEdit, QComboBox {{ background-color: {text_area_bg}; color: {text_area_fg}; }}
            QPushButton {{ background-color: {button_bg}; color: {button_fg}; }}
        """)

    def process_lines(self, handler, text_area, lines):
        thread = QtCore.QThread()
        worker = TranslationWorker(handler, lines)
        worker.moveToThread(thread)

        def on_finished(result):
            self.display_translations(handler, text_area, result)
            thread.quit()
            thread.wait()
            thread.deleteLater()
            worker.deleteLater()
            if hasattr(handler, "active_threads"):
                handler.active_threads = [
                    t for t in handler.active_threads if t[0] is not thread
                ]

        worker.finished.connect(on_finished)
        thread.started.connect(worker.run)
        thread.start()

        if not hasattr(handler, "active_threads"):
            handler.active_threads = []
        handler.active_threads.append((thread, worker))

    def close_selected_tab(self, idx=None):
        if idx is None:
            idx = self.tab_widget.currentIndex()
        if idx == -1 or idx >= len(self.handlers):
            return

        handler, text_area, timer, tab_idx = self.handlers[idx]
        handler.stop_event.set()

        if handler.file:
            handler.file.close()
        timer.stop()

        if hasattr(handler, "active_threads"):
            for thread, worker in handler.active_threads:
                try:
                    if hasattr(worker, "cancelled"):
                        worker.cancelled = True
                    if isinstance(thread, QtCore.QThread) and QtCore.QThread.isRunning(thread):
                        thread.quit()
                        thread.wait()
                except RuntimeError:
                    continue
            handler.active_threads.clear()

        self.tab_widget.removeTab(idx)
        del self.handlers[idx]

    def start_update_check(self):
        t = QtCore.QThread(self)
        worker = QtCore.QObject()
        t.started.connect(lambda: self._do_update_check(t))
        t.start()

    def _do_update_check(self, thread):
        try:
            resp = requests.get(
                "https://api.github.com/repos/bravuralion/TD2-Chat-Translator/releases/latest",
                timeout=3
            )
            resp.raise_for_status()
            latest_release = resp.json()
            latest_version = latest_release.get('tag_name', current_version)
            if version.parse(latest_version) > version.parse(current_version):
                QtCore.QMetaObject.invokeMethod(
                    self, "_prompt_update", QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, latest_version),
                    QtCore.Q_ARG(str, latest_release['assets'][0]['browser_download_url'])
                )
        except Exception:
            pass
        finally:
            thread.quit()
            thread.wait()

    @QtCore.pyqtSlot(str, str)
    def _prompt_update(self, latest_version, download_url):
        QtWidgets.QMessageBox.information(
            self,
            self._t("update_available_title"),
            self._t("update_available_body", ver=latest_version)
        )
        self._open_update_url(download_url)


        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    def _open_update_url(self, download_url):
        try:
            if hasattr(os, "startfile"):
                os.startfile(download_url)
                return
        except Exception:
            pass

        try:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(download_url))
        except Exception:
            pass

    def closeEvent(self, event):
        for handler, text_area, timer, tab_idx in self.handlers:
            handler.stop_event.set()
            if handler.file:
                handler.file.close()
            timer.stop()

            if hasattr(handler, "active_threads"):
                for thread, worker in handler.active_threads:
                    if isinstance(thread, QtCore.QThread) and thread.isRunning():
                        thread.quit()
                        thread.wait()
                handler.active_threads.clear()

        if self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None

    def toggle_overlay(self):
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.close()
            self.overlay_window = None
        else:
            self.overlay_window = OverlayWindow(dark_mode=self.is_dark_mode, font_size=self.overlay_font_size)
            self.overlay_window.show()
            current_tab = self.tab_widget.currentIndex()
            if current_tab != -1:
                handler, text_area, timer, tab_idx = self.handlers[current_tab]
                self.start_overlay_sync(text_area)

    def start_overlay_sync(self, source_text_widget):
        if not self.overlay_window or not self.overlay_window.isVisible():
            return

        src_cur = source_text_widget.textCursor()
        src_cur.movePosition(QtGui.QTextCursor.MoveOperation.Start)
        src_cur.movePosition(QtGui.QTextCursor.MoveOperation.End, QtGui.QTextCursor.MoveMode.KeepAnchor)
        fragment = QtGui.QTextDocumentFragment(src_cur)

        self.overlay_window.text_edit.clear()
        ov_cur = self.overlay_window.text_edit.textCursor()
        ov_cur.insertFragment(fragment)
        self.overlay_window.text_edit.setTextCursor(ov_cur)
        self.overlay_window.text_edit.ensureCursorVisible()

        self._overlay_sync_state[source_text_widget] = {
            "last_blocks": source_text_widget.document().blockCount()
        }

    def change_overlay_font_size(self, delta):
        self.overlay_font_size = max(6, self.overlay_font_size + delta)
        self.app_settings["overlay_font_size"] = self.overlay_font_size
        save_app_settings(self.app_settings)
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.change_font_size(delta)

    def display_translations(self, handler, text_area, translated_lines):
        max_lines = 50
        cursor = text_area.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        insert_start = cursor.position()

        for line, line_type, skip_game_chat in translated_lines:
            fmt = QtGui.QTextCharFormat()
            color_key = line_type if line_type in self.chat_colors else "default"
            fmt.setForeground(QtGui.QColor(self.chat_colors[color_key]))
            if line_type != "default" and line_type in ("fahrdienstleiter", "translated", "swdr", "warning"):
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)

            cursor.insertText(line + "\n", fmt)
            text_area.setTextCursor(cursor)


            if line_type != "warning" and not skip_game_chat:
                lang_code = LogHandler.get_short_language_code(self.language_var)
                self.write_to_game_chat(f"[{lang_code}] {line}", handler.log_file_path)

        text_area.ensureCursorVisible()

        if self.overlay_window and self.overlay_window.isVisible():
            ins_cur = QtGui.QTextCursor(text_area.document())
            ins_cur.setPosition(insert_start)
            ins_cur.setPosition(cursor.position(), QtGui.QTextCursor.MoveMode.KeepAnchor)
            fragment = QtGui.QTextDocumentFragment(ins_cur)

            ov = self.overlay_window.text_edit
            ov_cur = ov.textCursor()
            ov_cur.movePosition(QtGui.QTextCursor.MoveOperation.End)
            ov_cur.insertFragment(fragment)
            ov.setTextCursor(ov_cur)
            ov.ensureCursorVisible()

        doc = text_area.document()
        if doc.blockCount() > max_lines:
            cursor = text_area.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            for _ in range(doc.blockCount() - max_lines):
                cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            text_area.setTextCursor(cursor)
            text_area.ensureCursorVisible()
            if self.overlay_window and self.overlay_window.isVisible():
                self.start_overlay_sync(text_area)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("fusion")
    main_win = App()
    main_win.show()
    sys.exit(app.exec())