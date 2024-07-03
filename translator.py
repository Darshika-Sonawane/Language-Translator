from kivy.app import App
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
import speech_recognition as sr
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
import PyPDF2
import requests
import webbrowser
from pydub import AudioSegment
from langdetect import detect
from googletrans import Translator as GoogleTranslator
import fitz  # PyMuPDF
from kivy.core.audio import SoundLoader
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
import pyaudio
import wave
import threading
import os


#doc translation
def extract_text_from_page(page):
    # Extract text from the page (ignoring images)
    return page.get_text("text")

def translate_pdf(pdf_path, target_language):
    translator = GoogleTranslator()

    # Open the PDF document
    document = fitz.open(pdf_path)

    # Translate each page and append to the translated_text list
    translated_text = []
    for page_num in range(document.page_count):
        page = document[page_num]
        text = extract_text_from_page(page)

        # Ignore if the page has no text
        if not text:
            continue

        try:
            # Translate the text using googletrans
            translation = translator.translate(text, dest=target_language)
            translated_text.append(translation.text)
        except Exception as e:
            print(f"Error translating page {page_num + 1}: {e}")

    # Join the translated text into a single string
    translated_text = "\n".join(translated_text)

    return translated_text


#audio file translation
def transcribe_audio(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
    return recognizer.recognize_google(audio_data)

def convert_to_wav(input_file, output_file):
    sound = AudioSegment.from_file(input_file)
    sound.export(output_file, format="wav")

def detect_language(text):
    return detect(text)

def translate_text(text, target_language):
    translator = GoogleTranslator()
    translated_text = translator.translate(text, dest=target_language)
    return translated_text.text


# Define different screens
class Welcome(Screen):
    # for splash screen
    def on_enter(self, *args):
        # Schedule transition to 'choice' screen after 3 seconds
        Clock.schedule_once(lambda dt: self.switch_to_choice(), 3.5)

    def switch_to_choice(self):
        self.manager.current = 'choice'


class Choice(Screen):
    pass

class text_translation(Screen):
    def translate_text(self):
        user_input = self.ids.user_input.text
        selected_language = self.ids.language_spinner.text

        if user_input and selected_language:
            translator = GoogleTranslator()
            translated_text = translator.translate(user_input, dest=selected_language).text

            # display the translation
            self.ids.translation_label.text = f"Translated Text: {translated_text}"

class doc_translation(Screen):
    def translate_document(self, selected_file):
        target_language_code = self.ids.language_spinner.text

        if selected_file and target_language_code:
            pdf_path = selected_file[0]
            target_language = target_language_code

            try:
                translated_text = translate_pdf(pdf_path, target_language)
                self.ids.translation_label.text = f"Translated Document:\n{translated_text}"
            except Exception as e:
                print(f"Error translating document: {e}")



class web_translation(Screen):
    def translate_webpage(self):
        # Get user input for the URL and target language
        original_url = self.ids.web_url.text
        target_language_code = self.ids.language_spinner.text

        # Google Translate base URL
        translate_url = 'https://translate.google.com/translate'

        # Set up parameters for translation
        params = {
            'sl': 'auto',  # auto-detect source language
            'tl': target_language_code,  # target language
            'u': original_url,  # URL to translate
        }

        # Make a GET request to Google Translate
        response = requests.get(translate_url, params=params)

        # Print the translated URL
        translated_url = response.url
        self.ids.translation_label.text = f"Translated URL: {translated_url}"

        # Open the translated webpage in the default web browser
        webbrowser.open(translated_url)

class audio_translation(Screen):
    def translate_audio(self, selected_file):
        audio_file = selected_file[0]
        target_language = self.ids.language_spinner.text

        if audio_file and target_language:
            if not audio_file.endswith('.wav'):
                # Convert audio file to WAV format
                converted_file = "converted_audio.wav"
                convert_to_wav(audio_file, converted_file)
                audio_file = converted_file

            try:
                # Transcribe audio
                recognizer = sr.Recognizer()
                with sr.AudioFile(audio_file) as source:
                    audio_data = recognizer.record(source)
                transcribed_text = recognizer.recognize_google(audio_data)

                # Translate transcribed text
                translated_text = translate_text(transcribed_text, target_language)

                # Display translated text
                self.ids.translation_label.text = f"Translated Text:\n{translated_text}"
            except Exception as e:
                print(f"Error translating audio: {e}")

def convert_to_wav(input_file, output_file):
    try:
        input_file_path = os.path.abspath(input_file)
        sound = AudioSegment.from_file(input_file_path)
        sound.export(output_file, format="wav")
        return True  # Conversion successful
    except Exception as e:
        print(f"Error converting audio file: {e}")
        return False  # Conversion failed

def translate_text(text, target_language):
    translator = GoogleTranslator()
    translated_text = translator.translate(text, dest=target_language)
    return translated_text.text

import threading

class speech_translation(Screen):
    def __init__(self, **kwargs):
        super(speech_translation, self).__init__(**kwargs)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.translator = GoogleTranslator()
        self.audio = None
        self.recording = False
        self.input_language = None
        self.target_language = None

    def start_recording(self):
        if not self.recording:
            if self.input_language is None:
                print("Please select an input language first.")
                return
            print("Starting recording...")
            self.ids.recording_label.text = "Recording... Speak now!"
            self.audio = None  # Reset audio variable before starting new recording
            self.recording = True
            self.record_audio()
        else:
            print("Recording already in progress...")

    def record_audio(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            self.audio = self.recognizer.listen(source, timeout=None)

        self.stop_recording()

    def stop_recording(self):
        if self.recording:
            print("Stopping recording...")
            self.recording = False
            self.ids.recording_label.text = "Recording stopped."
            self.process_audio()
        else:
            print("No recording in progress...")

    def process_audio(self):
        if self.audio:
            try:
                user_input = self.recognizer.recognize_google(self.audio)
                self.ids.user_input.text = user_input
            except sr.UnknownValueError:
                print("Google Web Speech API could not understand audio")
            except sr.RequestError as e:
                print(f"Could not request results from Google Web Speech API; {e}")

    def translate_speech(self):
        if self.audio:
            selected_language = self.ids.target_language_spinner.text
            if selected_language:
                try:
                    recognized_text = self.recognizer.recognize_google(self.audio)
                    translated_text = self.translator.translate(recognized_text, dest=selected_language).text
                    self.ids.translation_label.text = f"Translated Speech: {translated_text}"
                except sr.UnknownValueError:
                    print("Google Web Speech API could not understand audio")
                except sr.RequestError as e:
                    print(f"Could not request results from Google Web Speech API; {e}")
            else:
                print("Please select a target language.")
        else:
            print("No audio recorded to translate.")

    def on_input_language_spinner_select(self, spinner, text):
        self.input_language = text

    def on_target_language_spinner_select(self, spinner, text):
        self.target_language = text




class WindowManager(ScreenManager):
    pass

# Design .kv file
kv = Builder.load_file('translator.kv')
class Translator(App):
    def build(self):
        self.window = GridLayout()

        return kv

if __name__ == "__main__":
    Translator().run()