from email.mime import text
from math import dist
import os
import sys
import re
from xml.sax import handler
from PyQt6 import QtWidgets, QtGui, QtCore
from openai import OpenAI
import deepl
import requests
import configparser
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

current_version = "0.4.1"

# --- I18N & Settings (NEU) ---
APP_SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".td2_app_settings.json")

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
    "font_plus": {"de": "A+", "en": "A+", "pl": "A+"},
    "font_minus": {"de": "A−", "en": "A−", "pl": "A−"},
    "select_log_dir": {
        "de": "Log-Verzeichnis auswählen",
        "en": "Select Log Directory",
        "pl": "Wybierz katalog logów"
    },
    "update_available_title": {"de": "Update verfügbar", "en": "Update Available", "pl": "Dostępna aktualizacja"},
    "update_available_body": {
        "de": "Eine neue Version {ver} ist verfügbar. Herunterladen?",
        "en": "A new version {ver} is available. Download?",
        "pl": "Nowa wersja {ver} jest dostępna. Pobierzesz?"
    },
    "warning_driver_lt_100": {
        "de": "ACHTUNG: FAHRER {name} hat vermutlich weniger als 100 km gefahren – Vorsicht!",
        "en": "ATTENTION: DRIVER {name} may drove less than 100 KM, be careful!",
        "pl": "UWAGA: KIEROWCA {name} przejechał mniej niż 100 KM – ostrożnie!"
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
    """ Get absolute path to resource, works for dev und for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

config = configparser.ConfigParser()
config.read(resource_path('config.cfg'))
client = OpenAI(api_key=config['DEFAULT']['OPENAI_API_KEY'])
deepl_api_key = config['DEFAULT']['deepl_api_key']

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

def load_scenery_names(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return {line.strip() for line in file if line.strip()}

class LogHandler(QtCore.QObject):
    lines_translated = QtCore.pyqtSignal(list)
    play_warning_sound = QtCore.pyqtSignal()

    def __init__(self, log_file_path, language_var, service_var, ignore_list, fixed_translations, scenery_names, enable_driver_warning, ui_lang):
        super().__init__()
        self.log_file_path = log_file_path
        self.file = open(log_file_path, 'r', encoding='utf-8')
        self.language_var = language_var
        self.service_var = service_var
        self.ignore_list = ignore_list
        self.fixed_translations = fixed_translations
        self.scenery_names = scenery_names
        self.translator = Translator()
        self.deepl_translator = deepl.Translator(deepl_api_key)
        self.last_position = self.file.tell()
        self.stop_event = Event()
        self.openai_client = OpenAI(api_key=config['DEFAULT']['OPENAI_API_KEY'])
        self.warning_sound = QSoundEffect()
        self.warning_sound.setSource(QtCore.QUrl.fromLocalFile(resource_path("res/timer_alarm.wav")))
        self.warning_sound.setLoopCount(1)
        self.warning_sound.setVolume(0.8)
        self.play_warning_sound.connect(self.warning_sound.play)
        self.warned_drivers = set()
        self.enable_driver_warning = enable_driver_warning
        self.ui_lang = ui_lang  # NEU

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
        max_workers = 1 if (self.service_var() if callable(self.service_var) else self.service_var) == "Google Translate" else 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_line = {}
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

                # Warnlogik lokalisiert
                if driver_name and self.enable_driver_warning():
                    if (dist_val is None or (isinstance(dist_val, (int, float)) and dist_val < 100)) and driver_name not in self.warned_drivers:
                        warning = I18N["warning_driver_lt_100"].get(self.ui_lang, I18N["warning_driver_lt_100"]["en"]).format(name=driver_name)
                        translated_lines.append((warning, "warning"))
                        self.play_warning_sound.emit()
                        self.warned_drivers.add(driver_name)

                current_target_language = self.language_var() if callable(self.language_var) else self.language_var
                translation_service = self.service_var() if callable(self.service_var) else self.service_var
                self.target_language = current_target_language

                future = executor.submit(self.translate_message, message, translation_service)
                future_to_line[future] = (timestamp_user, tag)
            for future in future_to_line:
                timestamp_user, tag = future_to_line[future]
                translation = future.result()
                translation = re.sub(r'【[^】]*】', '', translation).strip()
                translated_lines.append((f"{timestamp_user}: {translation}", tag))
        return translated_lines

    def translate_message(self, text, translation_service):
        current_target_language = self.target_language
        text_lower = text.lower()

        if (
            text_lower in self.fixed_translations
            and current_target_language in self.fixed_translations[text_lower]
        ):
            return self.fixed_translations[text_lower][current_target_language]

        masked_text, mask_map = self._mask_scenery_names(text)

        if translation_service == "ChatGPT":
            translated = self.translate_with_chatgpt(masked_text)
        elif translation_service == "Google Translate":
            translated = self.translate_with_google(masked_text)
        elif translation_service == "Deepl":
            translated = self.translate_with_deepl(masked_text)
        else:
            translated = masked_text

        return self._unmask_scenery_names(translated, mask_map)

    def _mask_scenery_names(self, text):
        mask_map = {}
        masked_text = text
        for name in sorted(self.scenery_names, key=len, reverse=True):
            pattern = r'\b' + re.escape(name) + r'\b'
            mask = f"__SCENERY_{hash(name)}__"
            if re.search(pattern, masked_text):
                masked_text = re.sub(pattern, mask, masked_text)
                mask_map[mask] = name
        return masked_text, mask_map

    def _unmask_scenery_names(self, text, mask_map):
        for mask, name in mask_map.items():
            text = text.replace(mask, name)
        return text

    def translate_with_chatgpt(self, text):
        try:
            thread = self.openai_client.beta.threads.create()
            self.openai_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=(
                    f"Translate the following Sentence to {self.target_language}. "
                    f"Only provide the translation without any explanations or additional text. "
                    f"If there are parts that cannot be translated (e.g., names, emojis), leave those unchanged: {text}"
                )
            )

            run = self.openai_client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id="asst_dxWUY2bN5TSwZXi09Q7HKITj",
                instructions=(
                    "You are a translator. Translate the text to the requested language only. "
                    "Do not explain anything. Keep names and symbols unchanged."
                )
            )

            if run.status == 'completed':
                messages = self.openai_client.beta.threads.messages.list(thread_id=thread.id)
                message_data = messages.data
                if message_data:
                    for message in reversed(message_data):
                        if message.role == "assistant" and message.content:
                            return message.content[0].text.value.strip()
                    return "No assistant message found"
                return "No messages found"
            else:
                return f"Run not completed. Status: {run.status}"

        except Exception as e:
            return f"[ChatGPT Error] {str(e)}"

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

    def translate_with_deepl(self, text):
        target_lang_code = self.get_deepl_language_code(self.target_language)
        if not target_lang_code:
            return f"Target language '{self.target_language}' not supported by Deepl"
        try:
            result = self.deepl_translator.translate_text(text, target_lang=target_lang_code)
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

        # --- UI-Sprache laden/abfragen (NEU) ---
        self.app_settings = load_app_settings()
        self.ui_lang = self.app_settings.get("ui_language")
        if self.ui_lang not in ("de", "en", "pl"):
            self.ui_lang = self._ask_ui_language()
            self.app_settings["ui_language"] = self.ui_lang
            save_app_settings(self.app_settings)
        self._t = lambda key, **kw: I18N[key][self.ui_lang].format(**kw)

        self.setWindowTitle(self._t("window_title", ver=current_version))
        self.overlay_window = None
        self.overlay_font_size = 10

        icon_path = resource_path(os.path.join('res', 'Favicon.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.ignore_list = load_ignore_list(resource_path(os.path.join('res', 'ignore_list.csv')))
        self.fixed_translations = load_fixed_translations(resource_path(os.path.join('res', 'fixed_translations.csv')))
        self.scenery_names = load_scenery_names(resource_path(os.path.join('res', 'Scenery_Names.csv')))

        self.language_var = "English"
        self.service_var = "Deepl"
        self.is_dark_mode = True
        self.enable_driver_warning = True

        self.handlers = []
        self.opened_logs = set()
        self.latest_log_time = None
        self.directory_path = ""
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
        # Dialogtitel/Label neutral auf Deutsch anzeigen; du kannst hier auch Englisch wählen
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

        # Top frame
        top_layout = QtWidgets.QHBoxLayout()
        img_path = resource_path(os.path.join('res', 'image.png'))
        if os.path.exists(img_path):
            img = Image.open(img_path).resize((80, 40), Image.LANCZOS)
            qt_img = ImageQt.ImageQt(img)
            pixmap = QtGui.QPixmap.fromImage(qt_img)
            img_label = QtWidgets.QLabel()
            img_label.setPixmap(pixmap)
            top_layout.addWidget(img_label)

        file_layout = QtWidgets.QHBoxLayout()
        file_label = QtWidgets.QLabel(self._t("logs_path"))
        self.file_entry = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton(self._t("browse"))
        browse_btn.clicked.connect(self.browse_directory)
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_entry)
        file_layout.addWidget(browse_btn)
        top_layout.addLayout(file_layout)
        main_layout.addLayout(top_layout)

        # Frame2
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
        service_values = ["ChatGPT", "Google Translate", "Deepl"]
        self.service_combobox = QtWidgets.QComboBox()
        self.service_combobox.addItems(service_values)
        self.service_combobox.setCurrentText(self.service_var)
        self.service_combobox.currentTextChanged.connect(lambda val: setattr(self, "service_var", val))
        frame2.addWidget(self.service_combobox)
        main_layout.addLayout(frame2)

        # Frame3
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
        self.warning_checkbox.setChecked(True)
        self.warning_checkbox.stateChanged.connect(lambda state: setattr(self, "enable_driver_warning", state == QtCore.Qt.CheckState.Checked))
        frame3.addWidget(self.warning_checkbox)

        main_layout.addLayout(frame3)

        # Tabs
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_selected_tab)
        main_layout.addWidget(self.tab_widget)

    def browse_directory(self):
        dialog = QtWidgets.QFileDialog(self)
        directory_path = dialog.getExistingDirectory(
            self,
            self._t("select_log_dir"),
            os.path.expanduser("~/Documents/TTSK/TrainDriver2/Logs")
        )
        if directory_path:
            self.directory_path = directory_path
            self.file_entry.setText(directory_path)
            newest = self.find_newest_log_file(directory_path)
            if newest:
                self.open_log_in_new_tab(newest)
                self.latest_log_time = os.path.getctime(newest)
            self.record_all_logs()
            self.monitor_new_logs()

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
            scenery_names=self.scenery_names,
            enable_driver_warning=lambda: self.warning_checkbox.isChecked(),
            ui_lang=self.ui_lang  # NEU
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
        # Dark Mode immer aktiv
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
            QCheckBox {{ background-color: {bg_color}; color: {fg_color}; }}
        """)

    def process_lines(self, handler, text_area, lines):
        thread = QtCore.QThread()
        worker = TranslationWorker(handler, lines)
        worker.moveToThread(thread)

        def on_finished(result):
            self.display_translations(text_area, result)
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
        reply = QtWidgets.QMessageBox.question(
            self,
            self._t("update_available_title"),
            self._t("update_available_body", ver=latest_version)
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            os.startfile(download_url)

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
        if not self.overlay_window or not self.overlay_window.isVisible():
            return
        self.overlay_font_size = max(6, self.overlay_font_size + delta)
        self.overlay_window.change_font_size(delta)

    def display_translations(self, text_area, translated_lines):
        max_lines = 50
        cursor = text_area.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        insert_start = cursor.position()

        for line, line_type in translated_lines:
            fmt = QtGui.QTextCharFormat()
            if line_type == "fahrdienstleiter":
                fmt.setForeground(QtGui.QColor("#DF7676"))
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            elif line_type == "translated":
                fmt.setForeground(QtGui.QColor("orange"))
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            elif line_type == "swdr":
                fmt.setForeground(QtGui.QColor("green"))
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            elif line_type == "warning":
                fmt.setForeground(QtGui.QColor("red"))
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            else:
                fmt.setForeground(QtGui.QColor("white"))

            cursor.insertText(line + "\n", fmt)
            text_area.setTextCursor(cursor)
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
    main_win = App()
    main_win.show()
    sys.exit(app.exec())
