import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
from deep_translator import GoogleTranslator, exceptions
from queue import Queue
from threading import Thread, Event

class LogHandler:
    def __init__(self, file_path, text_widget, target_language, queue, stop_event, show_original):
        self.file_path = file_path
        self.file = open(file_path, 'r', encoding='utf-8')
        self.text_widget = text_widget
        self.target_language = target_language
        self.queue = queue
        self.translator = GoogleTranslator(source='auto', target=target_language)
        self.stop_event = stop_event
        self.last_position = self.file.tell()
        self.show_original = show_original

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
            parts = clean_text.split(':', 1)
            if len(parts) > 1:
                return clean_text
        return ""

    def translate_lines(self, lines):
        translated_lines = []
        for line in lines:
            print(f"Processing line for translation: {line}")
            match = re.search(r'^(.*?)\((\d{2}:\d{2}:\d{2})\) (.*?): (.*)$', line)
            if match:
                timestamp_user = match.group(1) + "(" + match.group(2) + ") " + match.group(3)
                message = match.group(4)
                try:
                    print(f"Translating message: {message.strip()}")
                    translation = self.translator.translate(message.strip())
                    print(f"Received translation: {translation}")
                    if self.show_original:
                        translated_lines.append((f"Original: {timestamp_user}: {message.strip()}", "original"))
                    translated_lines.append((f"Translated: {timestamp_user}: {translation}", "translated"))
                except exceptions.NotValidPayload as e:
                    print(f"Error: NotValidPayload - {e}")
                except exceptions.TranslationNotFound as e:
                    print(f"Error: TranslationNotFound - {e}")
                except exceptions.TooManyRequests as e:
                    print(f"Error: TooManyRequests - {e}")
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print(f"Regex did not match for line: {line}")
        return translated_lines

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Train Driver 2 Translation Helper")

        self.log_file_path = ""
        self.target_language = "en"
        self.handler = None
        self.queue = Queue()
        self.stop_event = Event()
        self.show_original = tk.BooleanVar(value=True)

        self.create_widgets()

        self.thread = Thread(target=self.process_queue)
        self.thread.daemon = True
        self.thread.start()

    def create_widgets(self):
        # Log Directory Path Frame
        frame1 = tk.Frame(self.root)
        frame1.pack(pady=5, padx=10, fill=tk.X)

        self.file_label = tk.Label(frame1, text="Log Directory Path:")
        self.file_label.pack(side=tk.LEFT)

        self.file_entry = tk.Entry(frame1, width=50)
        self.file_entry.pack(side=tk.LEFT, padx=5)

        self.browse_button = tk.Button(frame1, text="Browse", command=self.browse_directory)
        self.browse_button.pack(side=tk.LEFT)

        # Target Language Frame
        frame2 = tk.Frame(self.root)
        frame2.pack(pady=5, padx=10, fill=tk.X)

        self.language_label = tk.Label(frame2, text="Target Language:")
        self.language_label.pack(side=tk.LEFT)

        self.language_var = tk.StringVar(self.root)
        self.language_var.set("en")
        self.language_menu = tk.OptionMenu(frame2, self.language_var, "en", "de", "pl")
        self.language_menu.pack(side=tk.LEFT, padx=5)

        # Show Original Checkbutton
        self.show_original_checkbutton = tk.Checkbutton(frame2, text="Show Original", variable=self.show_original)
        self.show_original_checkbutton.pack(side=tk.LEFT, padx=5)

        # Buttons Frame
        frame3 = tk.Frame(self.root)
        frame3.pack(pady=5, padx=10, fill=tk.X)

        self.start_button = tk.Button(frame3, text="Start Translation", command=self.start_translation)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.restart_button = tk.Button(frame3, text="Restart Translation", command=self.restart_translation)
        self.restart_button.pack(side=tk.LEFT, padx=5)

        # Text Area for Chat Messages
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=20, width=80)
        self.text_area.pack(pady=10, padx=10)
        self.text_area.tag_config('translated', foreground='green', font=("Helvetica", 10, "bold"))
        self.text_area.tag_config('original', foreground='black')

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

        self.target_language = self.language_var.get()
        self.text_area.delete(1.0, tk.END)

        if self.handler:
            self.stop_event.set()
            self.stop_event = Event()  # Reset stop event for the new handler

        self.handler = LogHandler(self.log_file_path, self.text_area, self.target_language, self.queue, self.stop_event, self.show_original.get())
        self.handler.check_new_lines()

        print(f"Started translation for file: {self.log_file_path}")

    def restart_translation(self):
        self.start_translation()

    def on_closing(self):
        self.stop_event.set()
        self.root.destroy()

    def process_queue(self):
        while True:
            lines = self.queue.get()
            print(f"Processing batch of lines: {lines}")
            if self.handler:
                self.handler.show_original = self.show_original.get()  # Update show_original setting
                translated_lines = self.handler.translate_lines(lines)
                for line, tag in translated_lines:
                    print(f"Inserting line into text area: {line}")
                    self.text_area.insert(tk.END, f"{line}\n", tag)
                    self.text_area.see(tk.END)
            self.queue.task_done()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
