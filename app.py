import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import speech_recognition as sr
import pyttsx3
import os
import json
import threading
import datetime
import google.generativeai as genai
from PIL import Image, ImageTk
import customtkinter as ctk
import requests

# Configure Gemini API
API_KEY = "AIzaSyDY3dRhAfNPZy6Ze3SzAutB7m2JDe2xDus"
genai.configure(api_key=API_KEY)

# Otter Voice Notes API configuration
OTTER_API_KEY = "your_otter_api_key_here"
OTTER_API_URL = "https://api.otter.ai/v1/transcriptions"

class NotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Notes Taker")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Set up theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize speech engine
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.engine.setProperty('voice', self.voices[0].id)  # Default voice
        self.engine.setProperty('rate', 150)  # Speed

        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()

        # Initialize Gemini model
        self.gemini_model = genai.GenerativeModel('gemini-pro')

        # Variables
        self.current_file = None
        self.is_recording = False
        self.notes_data = []
        self.current_note_index = None
        self.image_names = []  # To keep references to images

        # Create UI
        self.create_ui()

        # Load notes if they exist
        self.load_notes()

    def create_ui(self):
        # Create main frame with padding
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create two panels
        left_panel = ctk.CTkFrame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Left panel content (Notes list)
        notes_header = ctk.CTkFrame(left_panel)
        notes_header.pack(fill=tk.X, pady=(0, 10))

        notes_label = ctk.CTkLabel(notes_header, text="My Notes", font=("Helvetica", 16, "bold"))
        notes_label.pack(side=tk.LEFT, padx=10, pady=10)

        add_btn = ctk.CTkButton(notes_header, text="+", width=30, command=self.new_note)
        add_btn.pack(side=tk.RIGHT, padx=10, pady=10)

        # Notes listbox with scrollbar
        list_frame = ctk.CTkFrame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.notes_listbox = tk.Listbox(list_frame, bg="#2b2b2b", fg="white",
                                         font=("Helvetica", 12), selectbackground="#1f538d",
                                         selectforeground="white", bd=0, highlightthickness=0)
        self.notes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notes_listbox.bind('<<ListboxSelect>>', self.on_note_select)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.notes_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.notes_listbox.config(yscrollcommand=scrollbar.set)

        # Right panel content (Editor)
        editor_header = ctk.CTkFrame(right_panel)
        editor_header.pack(fill=tk.X, pady=(0, 10))

        self.title_entry = ctk.CTkEntry(editor_header, placeholder_text="Note Title", font=("Helvetica", 16))
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)

        # Action buttons frame
        actions_frame = ctk.CTkFrame(right_panel)
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        # Create buttons with icons or clear labels
        save_btn = ctk.CTkButton(actions_frame, text="Save", command=self.save_current_note)
        save_btn.pack(side=tk.LEFT, padx=5, pady=5)

        delete_btn = ctk.CTkButton(actions_frame, text="Delete", fg_color="#d9534f", hover_color="#c9302c", command=self.delete_note)
        delete_btn.pack(side=tk.LEFT, padx=5, pady=5)

        voice_record_btn = ctk.CTkButton(actions_frame, text="Voice Input", command=self.toggle_recording)
        voice_record_btn.pack(side=tk.LEFT, padx=5, pady=5)

        voice_playback_btn = ctk.CTkButton(actions_frame, text="Read Note", command=self.speak_note)
        voice_playback_btn.pack(side=tk.LEFT, padx=5, pady=5)

        ai_generate_btn = ctk.CTkButton(actions_frame, text="AI Generate", command=self.show_ai_dialog)
        ai_generate_btn.pack(side=tk.LEFT, padx=5, pady=5)

        export_btn = ctk.CTkButton(actions_frame, text="Export", command=self.export_note)
        export_btn.pack(side=tk.LEFT, padx=5, pady=5)

        import_img_btn = ctk.CTkButton(actions_frame, text="Import Image", command=self.import_image)
        import_img_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Status indicator for recording
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = ctk.CTkLabel(actions_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT, padx=10, pady=5)

        # Editor area
        editor_frame = ctk.CTkFrame(right_panel)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        self.text_area = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD,
                                                  font=("Helvetica", 12), bg="#2b2b2b",
                                                  fg="white", insertbackground="white",
                                                  selectbackground="#1f538d", selectforeground="white",
                                                  padx=10, pady=10)
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Footer with metadata
        footer = ctk.CTkFrame(right_panel)
        footer.pack(fill=tk.X, pady=(10, 0))

        self.meta_label = ctk.CTkLabel(footer, text="", font=("Helvetica", 10))
        self.meta_label.pack(side=tk.LEFT, padx=10, pady=5)

    def new_note(self):
        """Create a new note"""
        # Save current note if exists
        if self.current_note_index is not None:
            self.save_current_note()

        # Reset fields
        self.title_entry.delete(0, tk.END)
        self.text_area.delete(1.0, tk.END)
        self.current_note_index = None
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.meta_label.configure(text=f"Created: {timestamp}")
        self.title_entry.focus()

    def on_note_select(self, event):
        """Handle note selection from listbox"""
        # Save current note if exists
        if self.current_note_index is not None:
            self.save_current_note()

        # Get selected note
        selection = self.notes_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        self.current_note_index = index
        note = self.notes_data[index]

        # Update UI with note data
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, note.get('title', 'Untitled'))

        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, note.get('content', ''))

        metadata = f"Created: {note.get('created_date', 'Unknown')}"
        if 'modified_date' in note:
            metadata += f" | Modified: {note.get('modified_date', '')}"
        self.meta_label.configure(text=metadata)

    def save_current_note(self):
        """Save the current note"""
        title = self.title_entry.get() or "Untitled Note"
        content = self.text_area.get(1.0, tk.END).strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        note = {
            'title': title,
            'content': content,
            'modified_date': timestamp
        }

        if self.current_note_index is None:
            # New note
            note['created_date'] = timestamp
            self.notes_data.append(note)
            self.notes_listbox.insert(tk.END, title)
            self.current_note_index = len(self.notes_data) - 1
        else:
            # Update existing note
            note['created_date'] = self.notes_data[self.current_note_index].get('created_date', timestamp)
            self.notes_data[self.current_note_index] = note
            self.notes_listbox.delete(self.current_note_index)
            self.notes_listbox.insert(self.current_note_index, title)

        # Save to file
        self.save_notes_to_file()

        # Update metadata display
        metadata = f"Created: {note['created_date']} | Modified: {note['modified_date']}"
        self.meta_label.configure(text=metadata)

        # Show brief save confirmation
        self.status_var.set("Saved!")
        self.root.after(2000, lambda: self.status_var.set("Ready"))

    def delete_note(self):
        """Delete the current note"""
        if self.current_note_index is None:
            return

        if messagebox.askyesno("Delete Note", "Are you sure you want to delete this note?"):
            # Remove from data and listbox
            self.notes_data.pop(self.current_note_index)
            self.notes_listbox.delete(self.current_note_index)

            # Save to file
            self.save_notes_to_file()

            # Clear editor
            self.title_entry.delete(0, tk.END)
            self.text_area.delete(1.0, tk.END)
            self.meta_label.configure(text="")
            self.current_note_index = None

            # Update status
            self.status_var.set("Note deleted!")
            self.root.after(2000, lambda: self.status_var.set("Ready"))

    def export_note(self):
        """Export current note as a text file"""
        if self.current_note_index is None:
            messagebox.showinfo("Export Note", "No note selected to export")
            return

        title = self.title_entry.get() or "Untitled Note"
        content = self.text_area.get(1.0, tk.END)

        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")],
            initialfile=title
        )

        if filename:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content)
            messagebox.showinfo("Export Successful", f"Note exported to {filename}")

    def toggle_recording(self):
        """Toggle voice recording on/off"""
        if self.is_recording:
            # Stop recording
            self.is_recording = False
            self.status_var.set("Processing speech...")

            # Start processing in a separate thread
            threading.Thread(target=self.process_speech).start()
        else:
            # Start recording
            self.is_recording = True
            self.status_var.set("Listening... (Click again to stop)")

    def process_speech(self):
        """Process recorded speech to text"""
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=10)

            # Save audio to a file
            audio_file = "temp_audio.wav"
            with open(audio_file, "wb") as f:
                f.write(audio.get_wav_data())

            # Upload audio to Otter Voice Notes API
            headers = {
                "Authorization": f"Bearer {OTTER_API_KEY}",
                "Content-Type": "audio/wav"
            }
            with open(audio_file, "rb") as f:
                response = requests.post(OTTER_API_URL, headers=headers, data=f)

            if response.status_code == 200:
                transcription = response.json().get('text', '')
                # Insert recognized text at cursor position
                self.text_area.insert(tk.INSERT, transcription + " ")
                # Reset status
                self.status_var.set("Speech recognized!")
                self.root.after(2000, lambda: self.status_var.set("Ready"))
            else:
                self.status_var.set("Error in transcription")

        except sr.RequestError:
            self.status_var.set("Could not request results; check your network connection")
        except sr.UnknownValueError:
            self.status_var.set("No speech detected")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
        finally:
            self.is_recording = False
            if os.path.exists(audio_file):
                os.remove(audio_file)

    def speak_note(self):
        """Convert current note text to speech"""
        text = self.text_area.get(1.0, tk.END).strip()
        if not text:
            messagebox.showinfo("Text to Speech", "No text to read")
            return

        # Start speaking in a separate thread
        self.status_var.set("Speaking...")
        threading.Thread(target=self._speak_text, args=(text,)).start()

    def _speak_text(self, text):
        """Internal method to speak text in a separate thread"""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        finally:
            # Reset status when done
            self.status_var.set("Ready")

    def show_ai_dialog(self):
        """Show dialog for AI text generation options"""
        # Create a dialog window
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("AI Text Generation")
        dialog.geometry("500x400")
        dialog.resizable(True, True)
        dialog.transient(self.root)  # Set to be on top of the main window
        dialog.grab_set()  # Modal dialog

        # Prompt frame
        prompt_frame = ctk.CTkFrame(dialog)
        prompt_frame.pack(fill=tk.X, padx=10, pady=10)

        prompt_label = ctk.CTkLabel(prompt_frame, text="Enter your prompt:")
        prompt_label.pack(anchor=tk.W, padx=5, pady=5)

        prompt_entry = ctk.CTkTextbox(prompt_frame, height=100)
        prompt_entry.pack(fill=tk.X, padx=5, pady=5)
        prompt_entry.insert("1.0", "Generate a note about ")

        # Options frame
        options_frame = ctk.CTkFrame(dialog)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        length_label = ctk.CTkLabel(options_frame, text="Output length:")
        length_label.pack(anchor=tk.W, padx=5, pady=5)

        length_var = tk.StringVar(value="medium")
        short_rb = ctk.CTkRadioButton(options_frame, text="Short", variable=length_var, value="short")
        medium_rb = ctk.CTkRadioButton(options_frame, text="Medium", variable=length_var, value="medium")
        long_rb = ctk.CTkRadioButton(options_frame, text="Long", variable=length_var, value="long")

        short_rb.pack(anchor=tk.W, padx=20, pady=2)
        medium_rb.pack(anchor=tk.W, padx=20, pady=2)
        long_rb.pack(anchor=tk.W, padx=20, pady=2)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        # Status label
        status_var = tk.StringVar(value="")
        status_label = ctk.CTkLabel(buttons_frame, textvariable=status_var)
        status_label.pack(pady=5)

        def generate_text():
            prompt = prompt_entry.get("1.0", tk.END).strip()
            if not prompt:
                status_var.set("Please enter a prompt")
                return

            length = length_var.get()
            if length == "short":
                max_tokens = 100
            elif length == "medium":
                max_tokens = 300
            else:
                max_tokens = 500

            status_var.set("Generating text...")

            # Run in a separate thread to keep UI responsive
            threading.Thread(target=_generate_and_insert, args=(prompt, max_tokens, status_var, dialog)).start()

        def _generate_and_insert(prompt, max_tokens, status_var, dialog):
            try:
                response = self.gemini_model.generate_content(prompt, generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": 0.7
                })

                generated_text = response.text

                # Insert at cursor position or at the end
                self.text_area.insert(tk.INSERT, generated_text + "\n\n")

                # Close dialog
                self.root.after(0, dialog.destroy)

            except Exception as e:
                self.root.after(0, lambda: status_var.set(f"Error: {str(e)}"))

        generate_btn = ctk.CTkButton(buttons_frame, text="Generate", command=generate_text)
        generate_btn.pack(side=tk.LEFT, padx=5, pady=10)

        cancel_btn = ctk.CTkButton(buttons_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5, pady=10)

    def import_image(self):
        """Import an image and insert it into the note"""
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")])
        if file_path:
            image = Image.open(file_path)
            image = image.resize((200, 200), Image.ANTIALIAS)
            photo = ImageTk.PhotoImage(image)

            # Insert image at cursor position
            self.text_area.image_create(tk.INSERT, image=photo)
            self.image_names.append(photo)  # Keep a reference to avoid garbage collection

    def load_notes(self):
        """Load notes from file"""
        try:
            # Get user data directory
            data_dir = os.path.join(os.path.expanduser("~"), "SmartNotesTaker")
            os.makedirs(data_dir, exist_ok=True)

            notes_file = os.path.join(data_dir, "notes.json")

            if os.path.exists(notes_file):
                with open(notes_file, 'r', encoding='utf-8') as file:
                    self.notes_data = json.load(file)

                # Populate listbox
                self.notes_listbox.delete(0, tk.END)
                for note in self.notes_data:
                    self.notes_listbox.insert(tk.END, note.get('title', 'Untitled'))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load notes: {str(e)}")
            self.notes_data = []

    def save_notes_to_file(self):
        """Save notes to file"""
        try:
            # Get user data directory
            data_dir = os.path.join(os.path.expanduser("~"), "SmartNotesTaker")
            os.makedirs(data_dir, exist_ok=True)

            notes_file = os.path.join(data_dir, "notes.json")

            with open(notes_file, 'w', encoding='utf-8') as file:
                json.dump(self.notes_data, file, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save notes: {str(e)}")

def main():
    root = ctk.CTk()
    app = NotesApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
