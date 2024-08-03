import os
import sys
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import openai
import deepl
import requests
import configparser
from queue import Queue
from threading import Thread, Event
from PIL import Image, ImageTk
from googletrans import Translator
import csv

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev und for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

config = configparser.ConfigParser()
config.read(resource_path('config.cfg'))
openai.api_key = config['DEFAULT']['OPENAI_API_KEY']
deepl_api_key = config['DEFAULT']['deepl_api_key']
current_version = "0.1.4"

def load_ignore_list(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return {line.strip() for line in file}

def load_fixed_translations(filepath):
    fixed_translations = {}
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            text = row['text']
            language = row['language']
            translation = row['translation']
            if text not in fixed_translations:
                fixed_translations[text] = {}
            fixed_translations[text][language] = translation
    return fixed_translations

class LogHandler:
    def __init__(self, file_path, text_widget, target_language, queue, stop_event, show_original, ignore_list, service_var, fixed_translations):
        self.file_path = file_path
        self.file = open(file_path, 'r', encoding='utf-8')
        self.text_widget = text_widget
        self.target_language = target_language
        self.queue = queue
        self.stop_event = stop_event
        self.last_position = self.file.tell()
        self.show_original = show_original
        self.ignore_list = ignore_list
        self.service_var = service_var
        self.fixed_translations = fixed_translations
        self.translator = Translator()
        self.deepl_translator = deepl.Translator(deepl_api_key)

    def check_new_lines(self):
        if self.stop_event.is_set():
            return
        
        self.file.seek(self.last_position)
        lines = []
        while (line := self.file.readline()):
            if "ChatMessage:" in line and self.contains_time(line):
                clean_line = self.clean_chat_message(line)
                if clean_line:
                    lines.append(clean_line)

        if lines:
            self.last_position = self.file.tell()
            self.queue.put(lines)

        if not self.stop_event.is_set():
            self.text_widget.after(5000, self.check_new_lines)

    @staticmethod
    def contains_time(line):
        return re.search(r'\(\d{2}:\d{2}:\d{2}\)', line) is not None

    @staticmethod
    def clean_chat_message(line):
        chat_message = re.search(r'ChatMessage: (.*)', line)
        if chat_message:
            return re.sub(r'<.*?>', '', chat_message.group(1))
        return ""

    def translate_lines(self, lines):
        translated_lines = []
        for line in lines:
            # Match for player messages
            match_player = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) (.*?@[^: ]+)(: | )(.*)$', line)
            # Match for SWDR messages
            match_swdr = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) \[(.*? \((.*?)\))\] (.*)$', line)
            if match_player:
                timestamp_user, message = match_player.group(1) + "(" + match_player.group(2) + ") " + match_player.group(3), match_player.group(5).strip()
                tag = "translated"
            elif match_swdr:
                timestamp_user, message = match_swdr.group(1) + "(" + match_swdr.group(2) + ") [" + match_swdr.group(3) + "]", match_swdr.group(5).strip()
                tag = "swdr"
            else:
                continue

            if message in self.ignore_list:
                continue

            translation_service = self.service_var.get()
            translation = self.translate_message(message, translation_service)
            if self.show_original.get():
                translated_lines.append((f"Original: {timestamp_user}: {message}", "original"))
            translated_lines.append((f"Translated: {timestamp_user}: {translation}", tag))
        return translated_lines


    def translate_message(self, text, translation_service):

        fixed_translation = self.get_fixed_translation(text)
        if fixed_translation:
            return fixed_translation

        if translation_service == "ChatGPT":
            return self.translate_with_chatgpt(text)
        elif translation_service == "Google Translate":
            return self.translate_with_google(text)
        elif translation_service == "Deepl":
            return self.translate_with_deepl(text)

    def get_fixed_translation(self, text):
        print(f"Debug: {self.target_language}")
        for fixed_text, translations in self.fixed_translations.items():
            if fixed_text.lower() == text.lower() and self.target_language in translations:
                return translations[self.target_language]
        return None

    def translate_with_chatgpt(self, text):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are a translator. Translate the following text to {self.target_language} without any additional explanations.The Source can be in multiple languages. if you cannot translate a text, try to translate word by word."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            return str(e)

    def translate_with_google(self, text):
        try:
            translation = self.translator.translate(text, dest=self.target_language)
            return translation.text
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
            "English": "EN-GB",  # Default to British English
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
            "Portuguese": "PT-PT",  # Default to European Portuguese
            "Brazilian Portuguese": "PT-BR",
            "Romanian": "RO",
            "Russian": "RU",
            "Slovak": "SK",
            "Slovenian": "SL",
            "Swedish": "SV",
            "Chinese": "ZH"
        }
        return language_codes.get(language, None)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Train Driver 2 Translation Helper")
        icon_path = resource_path(os.path.join('res', 'Favicon.ico'))
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        self.log_file_path = ""
        self.ignore_list = load_ignore_list(resource_path(os.path.join('res', 'ignore_list.csv')))
        self.fixed_translations = load_fixed_translations(resource_path(os.path.join('res', 'fixed_translations.csv')))

        self.target_language = "en"
        self.handler = None
        self.queue = Queue()
        self.stop_event = Event()

        self.create_widgets()
        self.check_for_updates()

        Thread(target=self.process_queue, daemon=True).start()

    def create_widgets(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = tk.Frame(main_frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        img = Image.open(resource_path(os.path.join('res', 'image.png'))).resize((80, 40), Image.LANCZOS)
        self.img_tk = ImageTk.PhotoImage(img)
        tk.Label(top_frame, image=self.img_tk).pack(side=tk.RIGHT)

        frame1 = tk.Frame(top_frame)
        frame1.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(frame1, text="TD2 Logs Path:").pack(side=tk.LEFT)
        self.file_entry = tk.Entry(frame1, width=50)
        self.file_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(frame1, text="Browse", command=self.browse_directory).pack(side=tk.LEFT)

        frame2 = tk.Frame(main_frame)
        frame2.pack(pady=5, fill=tk.X)

        tk.Label(frame2, text="Target Language:").pack(side=tk.LEFT)
        self.language_var = tk.StringVar(self.root, "English")
        tk.OptionMenu(frame2, self.language_var, "English", "American English", "German", "Polish", "French", "Spanish", "Italian", "Dutch", "Portuguese", "Brazilian Portuguese", "Greek", "Swedish", "Danish", "Finnish", "Norwegian", "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Croatian", "Serbian", "Slovenian", "Estonian", "Latvian", "Lithuanian", "Maltese", "Russian").pack(side=tk.LEFT, padx=5)

        self.show_original = tk.BooleanVar()
        tk.Checkbutton(frame2, text="Show Original", variable=self.show_original).pack(side=tk.LEFT, padx=5)

        tk.Label(frame2, text="Translation Service:").pack(side=tk.LEFT, padx=5)
        self.service_var = tk.StringVar(self.root, "ChatGPT")
        tk.OptionMenu(frame2, self.service_var, "ChatGPT", "Google Translate", "Deepl").pack(side=tk.LEFT, padx=5)

        frame3 = tk.Frame(main_frame)
        frame3.pack(pady=5, fill=tk.X)
        tk.Button(frame3, text="Start Translation", command=self.start_translation).pack(side=tk.LEFT, padx=5)
        tk.Button(frame3, text="Restart Translation", command=self.restart_translation).pack(side=tk.LEFT, padx=5)
        tk.Button(frame3, text="Export Chat", command=self.export_chat).pack(side=tk.LEFT, padx=5)

        self.text_area = tk.Text(main_frame, wrap=tk.WORD, height=20, width=80)
        self.text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.text_area.tag_config('translated', foreground='green', font=("Helvetica", 10, "bold"))
        self.text_area.tag_config('swdr', foreground='red', font=("Helvetica", 10, "bold"))


    def browse_directory(self):
        directory_path = filedialog.askdirectory(initialdir=os.path.expanduser("~/Documents/TTSK/TrainDriver2/Logs"), title="Select Log Directory")
        if directory_path:
            self.log_file_path = self.find_latest_log_file(directory_path)
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, directory_path)

    @staticmethod
    def find_latest_log_file(directory_path):
        log_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        return max(log_files, key=os.path.getctime) if log_files else None

    def start_translation(self):
        if not self.log_file_path:
            messagebox.showwarning("Warning", "Please select a log directory.")
            return

        if self.handler:
            self.stop_event.set()
            self.handler.file.close()

        self.target_language = self.language_var.get()
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, "Translation started\n", "translated")

        self.stop_event = Event()
        self.handler = LogHandler(self.log_file_path, self.text_area, self.target_language, self.queue, self.stop_event, self.show_original, self.ignore_list, self.service_var, self.fixed_translations)

        self.handler.file.seek(0, os.SEEK_END)
        latest_message = None
        while (line := self.handler.file.readline()):
            if "ChatMessage:" in line and self.handler.contains_time(line):
                clean_line = self.handler.clean_chat_message(line)
                if clean_line:
                    latest_message = clean_line

        if latest_message:
            self.queue.put([latest_message])

        self.handler.last_position = self.handler.file.tell()
        self.handler.check_new_lines()

    def restart_translation(self):
        self.stop_event.set()
        if self.handler:
            self.handler.file.close()
        self.start_translation()

    def export_chat(self):
        desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        file_path = filedialog.asksaveasfilename(initialdir=desktop_path, defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(self.text_area.get(1.0, tk.END))
            messagebox.showinfo("Export Chat", "Chat exported successfully!")

    def check_for_updates(self):
        try:
            response = requests.get("https://api.github.com/repos/bravuralion/TD2-Chat-Translator/releases/latest")
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release['tag_name']
            if latest_version > current_version:
                if messagebox.askyesno("Update Available", f"A new version {latest_version} is available. Do you want to download it?"):
                    download_url = latest_release['assets'][0]['browser_download_url']
                    os.system(f"start {download_url}")
        except Exception as e:
            print(f"Error checking for updates: {e}")

    def on_closing(self):
        self.stop_event.set()
        if self.handler:
            self.handler.file.close()
        self.root.destroy()

    def process_queue(self):
        while True:
            lines = self.queue.get()
            if self.handler:
                translated_lines = self.handler.translate_lines(lines)
                for line, line_type in translated_lines:
                    tag = "translated" if line_type == "translated" else "swdr" if line_type == "swdr" else None
                    self.text_area.insert(tk.END, f"{line}\n", tag)
                    self.text_area.see(tk.END)
            self.queue.task_done()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
