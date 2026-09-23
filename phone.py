import threading
import urllib.request
import io
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import CoreImage
from kivy.uix.image import Image as KivyImage
from kivy.core.window import Window

import yt_dlp

# Simulates an Android phone screen size when running on a computer
Window.size = (400, 700)

class VideoRow(BoxLayout):
    """A row layout built for phone touchscreens: Image on left, large Title/Channel on right"""
    def __init__(self, data, select_callback, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=140, padding=10, spacing=15, **kwargs)
        self.data = data
        self.select_callback = select_callback

        # 1. Video Thumbnail on the left
        self.img_widget = KivyImage(source="", size_hint_x=None, width=140, allow_stretch=True)
        self.add_widget(self.img_widget)

        # 2. Text Stack on the right (Title and Channel)
        text_stack = BoxLayout(orientation="vertical", spacing=5)
        
        # Large, clear text sizes using 'sp' (scale-independent pixels) for easy reading
        self.title_label = Label(
            text=data["title"], font_size="18sp", bold=True, 
            halign="left", valign="top", text_size=(220, None), shortem=True
        )
        self.channel_label = Label(
            text=data["uploader"], font_size="14sp", color=(0.7, 0.7, 0.7, 1),
            halign="left", valign="top", text_size=(220, None)
        )
        
        text_stack.add_widget(self.title_label)
        text_stack.add_widget(self.channel_label)
        self.add_widget(text_stack)

        # Load the thumbnail image in the background without freezing the screen
        if data["thumb"]:
            threading.Thread(target=self.fetch_thumbnail, daemon=True).start()

    def fetch_thumbnail(self):
        try:
            raw_data = urllib.request.urlopen(self.data["thumb"]).read()
            data_io = io.BytesIO(raw_data)
            ext = self.data["thumb"].split('.')[-1].split('?')
            if ext not in ['png', 'jpg', 'jpeg']: ext = 'jpg'
            
            core_img = CoreImage(data_io, ext=ext)
            self.img_widget.texture = core_img.texture
        except Exception as e:
            print(f"Image loading error: {e}")

    def on_touch_down(self, touch):
        # Triggers when a user taps this specific video card on their screen
        if self.collide_point(*touch.pos):
            self.select_callback(self.data)
            return True
        return super().on_touch_down(touch)


class AndroidDownloaderApp(App):
    def build(self):
        self.selected_url = None
        
        # Main vertical container for the mobile screen
        master_layout = BoxLayout(orientation="vertical", padding=15, spacing=15)

        # 1. Large Mobile Search Bar Row
        search_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=65, spacing=10)
        self.search_input = TextInput(
            hint_text="Search YouTube...", font_size="22sp", multiline=False, size_hint_x=0.75
        )
        search_btn = Button(text="Search", font_size="18sp", bold=True, size_hint_x=0.25)
        search_btn.bind(on_release=lambda x: self.start_search_thread())
        
        search_row.add_widget(self.search_input)
        search_row.add_widget(search_btn)
        master_layout.add_widget(search_row)

        # 2. Touch Scroll Results Feed (Swipe up/down smoothly)
        self.scroll_view = ScrollView(do_scroll_x=False, size_hint=(1, 1))
        self.results_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        self.results_box.bind(minimum_height=self.results_box.setter('height'))
        self.scroll_view.add_widget(self.results_box)
        master_layout.add_widget(self.scroll_view)

        # 3. Dynamic Text Format Switcher (Video vs Audio)
        self.format_frame = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=20)
        self.mode = "video"
        
        self.vid_btn = Button(text="Video (MP4)", font_size="16sp", background_color=(0.2, 0.6, 1, 1))
        self.aud_btn = Button(text="Audio (MP3)", font_size="16sp", background_color=(0.3, 0.3, 0.3, 1))
        
        self.vid_btn.bind(on_release=self.set_video_mode)
        self.aud_btn.bind(on_release=self.set_audio_mode)
        
        self.format_frame.add_widget(self.vid_btn)
        self.format_frame.add_widget(self.aud_btn)
        master_layout.add_widget(self.format_frame)

        # 4. Status Bar Information Text
        self.status_label = Label(text="Type something to search.", font_size="20sp", size_hint_y=None, height=45)
        master_layout.add_widget(self.status_label)

        # 5. Large Download Button (Designed wide for easy finger taps)
        self.download_btn = Button(text="Download Selection", font_size="24sp", bold=True, size_hint_y=None, height=75, disabled=True)
        self.download_btn.bind(on_release=lambda x: self.start_download_thread())
        master_layout.add_widget(self.download_btn)

        return master_layout

    def set_video_mode(self, instance):
        self.mode = "video"
        self.vid_btn.background_color = (0.2, 0.6, 1, 1)
        self.aud_btn.background_color = (0.3, 0.3, 0.3, 1)

    def set_audio_mode(self, instance):
        self.mode = "audio"
        self.vid_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.aud_btn.background_color = (0.2, 0.6, 1, 1)

    def start_search_thread(self):
        query = self.search_input.text.strip()
        if not query:
            self.status_label.text = "Please enter a search query!"
            return
        self.status_label.text = "Searching..."
        self.results_box.clear_widgets()
        threading.Thread(target=self.run_yt_search, args=(query,), daemon=True).start()

    def run_yt_search(self, query):
        ydl_opts = {'default_search': 'ytsearch', 'extract_flat': True, 'skip_download': True}
        try:
            search_query = f"ytsearch10:{query}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
            
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry: continue
                    video_data = {
                        "title": entry.get('title', 'Unknown Title'),
                        "uploader": entry.get('uploader', 'Unknown Channel'),
                        "url": f"https://youtube.com{entry.get('id')}",
                        "thumb": entry.get('thumbnail')
                    }
                    row = VideoRow(video_data, self.on_video_selected)
                    self.results_box.add_widget(row)
            
            self.status_label.text = "Tap a video to select it."
        except:
            self.status_label.text = "Search operation failed."

    def on_video_selected(self, data):
        self.selected_url = data["url"]
        self.download_btn.disabled = False
        self.status_label.text = f"Selected: {data['title']}"

    def start_download_thread(self):
        if not self.selected_url: return
        self.download_btn.disabled = True
        self.status_label.text = "Downloading media file..."
        threading.Thread(target=self.download_core, args=(self.selected_url,), daemon=True).start()

    def download_core(self, url):
        # Automatically saves files inside your Android phone's main Downloads directory folder location
        download_folder = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "."
        
        if self.mode == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            ydl_opts = {
                # 'best' requests a combined single video/audio track stream so it works on mobile devices smoothly
                'format': 'best',
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
            }
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.status_label.text = "Success! Check your phone Downloads."
        except Exception as e:
            self.status_label.text = "Download failed."
            print(e)
        finally:
            self.download_btn.disabled = False

if __name__ == '__main__':
    AndroidDownloaderApp().run()
