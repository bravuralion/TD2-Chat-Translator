import os
import sys
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
import openai
from queue import Queue
from threading import Thread, Event
import configparser
from PIL import Image, ImageTk

openai.api_key = "sk-svcacct-"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def load_ignore_list(filepath):
    ignore_list = set()
    with open(filepath, 'r', encoding='utf-8') as file:
        for line in file:
            ignore_list.add(line.strip())
    return ignore_list

class LogHandler:
    def __init__(self, file_path, text_widget, target_language, queue, stop_event, show_original, ignore_list):
        self.file_path = file_path
        self.file = open(file_path, 'r', encoding='utf-8')
        self.text_widget = text_widget
        self.target_language = target_language
        self.queue = queue
        self.stop_event = stop_event
        self.last_position = self.file.tell()
        self.show_original = show_original
        self.ignore_list = ignore_list

    def check_new_lines(self):
        if self.stop_event.is_set():
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
                    print(f"Detected new chat message: {clean_line}")
                    lines.append(clean_line)

        if lines:
            self.last_position = self.file.tell()
            print(f"Batch of chat messages to be translated: {lines}")
            self.queue.put(lines)

        if not self.stop_event.is_set():
            self.text_widget.after(5000, self.check_new_lines)

    def contains_time(self, line):
        return re.search(r'\(\d{2}:\d{2}:\d{2}\)', line) is not None

    def clean_chat_message(self, line):
        chat_message = re.search(r'ChatMessage: (.*)', line)
        if chat_message:
            clean_text = re.sub(r'<.*?>', '', chat_message.group(1))
            return clean_text
        return ""

    def translate_lines(self, lines):
        translated_lines = []
        show_original = self.show_original.get()
        for line in lines:
            print(f"Processing line for translation: {line}")
            match = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) (.*?@.*?)[: ] (.*)$', line)
            if match:
                timestamp_user = match.group(1) + "(" + match.group(2) + ") " + match.group(3)
                message = match.group(4).strip()
                if message in self.ignore_list:
                    print(f"Ignored message: {message}")
                    continue
                try:
                    print(f"Translating message: {message}")
                    translation = self.translate_with_chatgpt(message)
                    print(f"Received translation: {translation}")
                    if show_original:
                        translated_lines.append((f"Original: {timestamp_user}: {message}", "original"))
                    translated_lines.append((f"Translated: {timestamp_user}: {translation}", "translated"))
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print(f"Regex did not match for line: {line}")
        return translated_lines

    def translate_with_chatgpt(self, text):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are a translator. Translate the following text to {self.target_language} without any additional explanations."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            print(f"Error while translating with ChatGPT: {e}")
            return text

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Train Driver 2 Translation Helper")
        # Set the icon for the window
        icon_path = resource_path("Favicon.ico")  # Replace with your icon path
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        else:
            print(f"Icon file not found: {icon_path}")
        self.log_file_path = ""
        self.ignore_list = load_ignore_list(resource_path('ignore_list.csv'))
        self.target_language = "en"
        self.handler = None
        self.queue = Queue()
        self.stop_event = Event()

        self.create_widgets()

        self.thread = Thread(target=self.process_queue)
        self.thread.daemon = True
        self.thread.start()

    def create_widgets(self):
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top frame for image
        top_frame = tk.Frame(main_frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # Image
        img_path = "image.png"  # Replace with your image path
        img = Image.open(resource_path("image.png"))
        img = img.resize((80, 40), Image.LANCZOS)
        self.img_tk = ImageTk.PhotoImage(img)
        img_label = tk.Label(top_frame, image=self.img_tk)
        img_label.pack(side=tk.RIGHT)

        # Log Directory Path Frame
        frame1 = tk.Frame(top_frame)
        frame1.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.file_label = tk.Label(frame1, text="Log Directory Path:")
        self.file_label.pack(side=tk.LEFT)

        self.file_entry = tk.Entry(frame1, width=50)
        self.file_entry.pack(side=tk.LEFT, padx=5)

        self.browse_button = tk.Button(frame1, text="Browse", command=self.browse_directory)
        self.browse_button.pack(side=tk.LEFT)

        # Target Language Frame
        frame2 = tk.Frame(main_frame)
        frame2.pack(pady=5, fill=tk.X)

        self.language_label = tk.Label(frame2, text="Target Language:")
        self.language_label.pack(side=tk.LEFT)

        self.language_var = tk.StringVar(self.root)
        self.language_var.set("English")  # Default language is English
        self.language_menu = tk.OptionMenu(frame2, self.language_var, "English", "German", "Polish", "French", "Spanish", "Italian", "Dutch", "Portuguese", "Greek", "Swedish", "Danish", "Finnish", "Norwegian", "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Croatian", "Serbian", "Slovenian", "Estonian", "Latvian", "Lithuanian", "Maltese", "Russian")
        self.language_menu.pack(side=tk.LEFT, padx=5)

        self.show_original = tk.BooleanVar()
        self.show_original_check = tk.Checkbutton(frame2, text="Show Original", variable=self.show_original)
        self.show_original_check.pack(side=tk.LEFT, padx=5)

        # Buttons Frame
        frame3 = tk.Frame(main_frame)
        frame3.pack(pady=5, fill=tk.X)

        self.start_button = tk.Button(frame3, text="Start Translation", command=self.start_translation)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.restart_button = tk.Button(frame3, text="Restart Translation", command=self.restart_translation)
        self.restart_button.pack(side=tk.LEFT, padx=5)

        # Text Area for Chat Messages
        self.text_area = tk.Text(main_frame, wrap=tk.WORD, height=20, width=80)
        self.text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.text_area.tag_config('translated', foreground='green', font=("Helvetica", 10, "bold"))

    def browse_directory(self):
        directory_path = filedialog.askdirectory(initialdir=os.path.expanduser("~/Documents/TTSK/TrainDriver2/Logs"),
                                                 title="Select Log Directory")
        if directory_path:
            self.log_file_path = self.find_latest_log_file(directory_path)
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, directory_path)
            print(f"Selected directory: {directory_path}")
            print(f"Latest log file: {self.log_file_path}")

    def find_latest_log_file(self, directory_path):
        log_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        if not log_files:
            return None
        latest_file = max(log_files, key=os.path.getctime)
        return latest_file

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
        self.handler = LogHandler(self.log_file_path, self.text_area, self.target_language, self.queue, self.stop_event, self.show_original, self.ignore_list)
        
        # Nur die neueste letzte Nachricht übersetzen
        self.handler.file.seek(0, os.SEEK_END)
        latest_message = None
        while True:
            line = self.handler.file.readline()
            if not line:
                break
            if "ChatMessage:" in line and self.handler.contains_time(line):
                clean_line = self.handler.clean_chat_message(line)
                if clean_line:
                    latest_message = clean_line

        if latest_message:
            print(f"Latest chat message to be translated: {latest_message}")
            self.queue.put([latest_message])  # Nur die letzte Nachricht in die Warteschlange legen

        self.handler.last_position = self.handler.file.tell()
        self.handler.check_new_lines()

        print(f"Started translation for file: {self.log_file_path}")

    def restart_translation(self):
        self.stop_event.set()
        if self.handler:
            self.handler.file.close()
        self.start_translation()

    def on_closing(self):
        self.stop_event.set()
        if self.handler:
            self.handler.file.close()
        self.root.destroy()

    def process_queue(self):
        while True:
            lines = self.queue.get()
            print(f"Processing batch of lines: {lines}")
            if self.handler:
                translated_lines = self.handler.translate_lines(lines)
                for line, line_type in translated_lines:
                    print(f"Inserting line into text area: {line}")
                    if line_type == "translated":
                        self.text_area.insert(tk.END, f"{line}\n", "translated")
                    else:
                        self.text_area.insert(tk.END, f"{line}\n")
                    self.text_area.see(tk.END)
            self.queue.task_done()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
