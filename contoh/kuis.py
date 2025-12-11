import pygame
import wx
import os
import sys # <-- Tambahkan ini untuk potensi penggunaan di masa depan (frozen app)
import random

# --- NVDA Controller Client (opsional, jika diperlukan) ---
try:
    import nvdaController
    NVDA_AVAILABLE = True
    try:
        if not nvdaController.isInstRunning():
            print("NVDA tidak berjalan. Fitur ucapan NVDA kustom tidak akan aktif.")
            NVDA_AVAILABLE = False
    except Exception as e:
        print(f"Error saat inisialisasi NVDA Controller: {e}")
        NVDA_AVAILABLE = False

except ImportError:
    NVDA_AVAILABLE = False
    print("nvda-controller-client tidak terinstal. Fitur ucapan NVDA kustom tidak akan aktif.")
# --- Akhir NVDA Controller Client ---

def get_application_path():
    """
    Mendapatkan path dasar aplikasi. Berguna jika script dijalankan sebagai
    file .py biasa atau sebagai executable yang di-freeze (misalnya oleh PyInstaller).
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Jika dijalankan sebagai bundle PyInstaller, _MEIPASS adalah path ke folder sementara
        # tempat file diekstrak. Resource harus ada di sini.
        application_path = sys._MEIPASS
    else:
        # Jika dijalankan sebagai script .py biasa
        application_path = os.path.dirname(os.path.realpath(__file__)) # Menggunakan realpath untuk resolve symlinks
    return application_path

class QuizApp(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(650, 550))
        self.panel = wx.Panel(self, style=wx.TAB_TRAVERSAL)
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.vbox)

        self.correct_sound = None
        self.wrong_sound = None
        self.checking_sound = None
        self.game_over_sound = None
        self.music_playing = False
        self.checking_sound_duration_ms = 0
        self.game_over_sound_duration_ms = 0
        self.timer = None
        self.quiz_dir = "" # Akan diisi di bawah
        self.audio_problem = False

        try:
            # --- MODIFIKASI UTAMA ADA DI SINI ---
            # Menggunakan fungsi get_application_path untuk menentukan root path
            application_root_path = get_application_path()
            self.quiz_dir = os.path.join(application_root_path, "sounds")
            # --- AKHIR MODIFIKASI UTAMA ---

            print(f"Mencari folder sounds di: {self.quiz_dir}") # Untuk debugging

            if not os.path.isdir(self.quiz_dir):
                wx.LogError(f"Folder 'sounds' tidak ditemukan di: {self.quiz_dir}\n"
                            "Pastikan folder 'sounds' berada di direktori yang sama dengan script kuis.\n"
                            "Kuis akan berjalan tanpa suara.")
                self.audio_problem = True
            else:
                self.audio_problem = False # Awalnya set false, akan diubah jika ada masalah lain

            # Inisialisasi Pygame mixer hanya jika folder sounds ada (atau kita putuskan untuk tetap init)
            if not self.audio_problem: # Atau bisa juga inisialisasi mixer di luar kondisi ini
                try:
                    pygame.mixer.init()
                except pygame.error as e:
                    wx.LogError(f"Gagal menginisialisasi Pygame mixer: {e}\nKuis akan berjalan tanpa suara.")
                    self.audio_problem = True

            if not self.audio_problem:
                try:
                    sound_files = {
                        "correct": "jawaban benar.mp3",
                        "wrong": "jawaban salah.mp3",
                        "checking": "memeriksa jawaban.mp3",
                        "intro": "test.mp3",
                        "game_over": "permainan selesai.mp3"
                    }
                    missing_files = []
                    loaded_sounds = {} # Untuk menyimpan objek Sound yang berhasil dimuat

                    for key, filename in sound_files.items():
                        filepath = os.path.join(self.quiz_dir, filename)
                        if not os.path.exists(filepath):
                            missing_files.append(filename)
                        else:
                            # Coba muat suara di sini untuk menangkap error per file
                            try:
                                loaded_sounds[key] = pygame.mixer.Sound(filepath)
                            except pygame.error as e:
                                wx.LogError(f"Error saat memuat file suara '{filename}': {e}")
                                missing_files.append(f"{filename} (gagal dimuat)")


                    if missing_files:
                        wx.LogError(f"File suara berikut hilang atau gagal dimuat dari folder '{self.quiz_dir}':\n"
                                    f"{', '.join(missing_files)}\nKuis akan berjalan tanpa beberapa suara efek/intro.")
                        # Tidak perlu set self.audio_problem = True di sini secara global
                        # karena kita akan cek keberadaan sound object sebelum memainkannya.

                    # Assign sound objects if they were loaded
                    self.correct_sound = loaded_sounds.get("correct")
                    self.wrong_sound = loaded_sounds.get("wrong")
                    self.checking_sound = loaded_sounds.get("checking")
                    self.game_over_sound = loaded_sounds.get("game_over")
                    intro_sound_obj_for_length_check = loaded_sounds.get("intro") # Hanya untuk cek panjang, musik akan diload dengan music.load

                    if self.checking_sound:
                        self.checking_sound_duration_ms = int(self.checking_sound.get_length() * 1000)
                    if self.game_over_sound:
                        self.game_over_sound_duration_ms = int(self.game_over_sound.get_length() * 1000)

                    self.timer = wx.Timer(self)
                    self.Bind(wx.EVT_TIMER, self.on_music_finished, self.timer)

                    # Cek apakah file intro ada sebelum mencoba memuatnya sebagai musik
                    intro_filepath = os.path.join(self.quiz_dir, sound_files["intro"])
                    if os.path.exists(intro_filepath) and intro_sound_obj_for_length_check: # Pastikan juga bisa di-load sebagai Sound
                        self.load_and_play_music(sound_files["intro"], intro_sound_obj_for_length_check)
                    else:
                        if not os.path.exists(intro_filepath):
                            wx.LogError(f"File musik intro '{sound_files['intro']}' tidak ditemukan. Lanjut tanpa musik intro.")
                        # Jika intro_sound_obj_for_length_check None, error sudah dicatat sebelumnya
                        wx.CallAfter(self.display_welcome_message)

                except pygame.error as e: # Error umum saat memuat Sound() atau operasi mixer
                    wx.LogError(f"Error terkait Pygame Sound: {e}\nBeberapa suara mungkin tidak berfungsi.")
                    # self.audio_problem bisa diset di sini jika error dianggap fatal untuk semua suara
                    wx.CallAfter(self.display_welcome_message)
            else: # Jika folder 'sounds' tidak ada atau mixer init gagal
                wx.CallAfter(self.display_welcome_message)

        except Exception as e:
            wx.LogError(f"Terjadi error tak terduga saat inisialisasi: {e}")
            self.audio_problem = True # Anggap masalah audio jika ada error besar
            wx.CallAfter(self.display_welcome_message)


        self.all_questions = [
            {"question": "Di Android, fitur aksesibilitas utama yang membacakan layar untuk tunanetra disebut?", "choices": ["TalkBack", "Voice Assistant", "Screen Reader Pro", "Audio Guide"], "answer": "TalkBack"},
            {"question": "Gestur umum di TalkBack untuk pindah ke item berikutnya di layar adalah?", "choices": ["Geser ke kanan dengan satu jari", "Ketuk dua kali dengan satu jari", "Geser ke atas dengan dua jari", "Tekan tombol volume atas"], "answer": "Geser ke kanan dengan satu jari"},
            {"question": "Untuk mengaktifkan item yang sedang difokus oleh TalkBack, gestur apa yang digunakan?", "choices": ["Ketuk dua kali di mana saja pada layar", "Tekan lama item tersebut", "Geser ke atas lalu ke bawah", "Goyangkan perangkat"], "answer": "Ketuk dua kali di mana saja pada layar"},
            {"question": "Bagaimana cara membuka menu konteks lokal TalkBack (menu tindakan untuk item yang fokus)?", "choices": ["Geser ke bawah lalu ke kanan dengan satu jari", "Geser ke kiri lalu ke atas dengan satu jari", "Ketuk tiga kali dengan satu jari", "Tekan tombol kembali dua kali"], "answer": "Geser ke bawah lalu ke kanan dengan satu jari"},
            {"question": "Screen reader bawaan pada sistem operasi Windows disebut?", "choices": ["Narrator", "Windows Reader", "JAWS Lite", "Microsoft Voice"], "answer": "Narrator"},
            {"question": "Tombol pintas (shortcut) umum untuk menghidupkan atau mematikan Narrator di Windows adalah?", "choices": ["Windows Key + Ctrl + Enter", "Alt + F4", "Ctrl + Shift + N", "Windows Key + U"], "answer": "Windows Key + Ctrl + Enter"},
            {"question": "Di Narrator, tombol apa yang sering disebut sebagai 'Tombol Narrator' (modifier key)?", "choices": ["Caps Lock atau Insert", "Shift", "Ctrl", "Alt"], "answer": "Caps Lock atau Insert"},
            {"question": "Untuk membaca baris teks saat ini menggunakan Narrator, kombinasi tombol apa yang umum digunakan (dengan Tombol Narrator)?", "choices": ["Tombol Narrator + Panah Atas", "Tombol Narrator + Spasi", "Tombol Narrator + L", "Tombol Narrator + R"], "answer": "Tombol Narrator + Panah Atas"},
            {"question": "Apa fungsi 'Label Kustom' di pengaturan aksesibilitas TalkBack?", "choices": ["Memberi nama pada tombol atau ikon yang tidak berlabel jelas", "Mengubah suara TalkBack", "Menyesuaikan kecepatan bicara", "Mengganti tema warna"], "answer": "Memberi nama pada tombol atau ikon yang tidak berlabel jelas"},
            {"question": "Di TalkBack, bagaimana cara menggulir daftar (scroll) ke atas atau ke bawah?", "choices": ["Geser dengan dua jari ke atas atau ke bawah", "Geser dengan satu jari dari tepi layar", "Gunakan menu konteks global", "Ketuk tepi atas atau bawah layar"], "answer": "Geser dengan dua jari ke atas atau ke bawah"},
            {"question": "Fitur 'Pintasan Aksesibilitas' di Android memungkinkan pengguna untuk?", "choices": ["Cepat menghidupkan/mematikan layanan aksesibilitas seperti TalkBack", "Membuat shortcut aplikasi di layar utama", "Mengatur volume media", "Mengunci layar dengan cepat"], "answer": "Cepat menghidupkan/mematikan layanan aksesibilitas seperti TalkBack"},
            {"question": "Apa itu 'Mode Pindai' (Scan Mode) di Narrator Windows?", "choices": ["Mode navigasi yang memungkinkan perpindahan antar elemen dengan panah atas/bawah dan spasi untuk aktivasi", "Mode untuk memindai virus", "Mode untuk mencari file", "Mode untuk mengatur kontras layar"], "answer": "Mode navigasi yang memungkinkan perpindahan antar elemen dengan panah atas/bawah dan spasi untuk aktivasi"},
            {"question": "Di Windows, bagaimana cara membuka Pengaturan Aksesibilitas (Ease of Access Center) dengan cepat?", "choices": ["Windows Key + U", "Ctrl + Alt + Delete", "Windows Key + I lalu cari 'Aksesibilitas'", "Klik kanan pada Start Menu"], "answer": "Windows Key + U"},
            {"question": "Jika Anda menggunakan NVDA di Windows, tombol modifier default NVDA adalah?", "choices": ["Insert (atau Caps Lock jika diatur)", "Shift", "Windows Key", "F12"], "answer": "Insert (atau Caps Lock jika diatur)"},
            {"question": "Dalam konteks keyboard Braille di TalkBack, apa yang dimaksud dengan 'Mode Tabel' (Tabletop Mode)?", "choices": ["Mode mengetik dengan perangkat diletakkan datar dan orientasi layar terkunci", "Mode untuk menampilkan tabel data", "Mode untuk menghubungkan ke layar eksternal", "Mode hemat daya saat mengetik Braille"], "answer": "Mode mengetik dengan perangkat diletakkan datar dan orientasi layar terkunci"},
            {"question": "Di Windows, 'UI Automation' (UIA) adalah teknologi Microsoft yang penting untuk?", "choices": ["Memungkinkan aplikasi aksesibilitas seperti screen reader berinteraksi dengan elemen UI aplikasi lain", "Mengotomatiskan pembaruan Windows", "Membuat antarmuka pengguna lebih cepat", "Mengenkripsi data pengguna"], "answer": "Memungkinkan aplikasi aksesibilitas seperti screen reader berinteraksi dengan elemen UI aplikasi lain"},
            {"question": "Saat menggunakan TalkBack, jika Anda ingin membaca per karakter atau per kata untuk teks yang sedang fokus, menu apa yang akan Anda buka?", "choices": ["Menu Granularitas Navigasi (Reading granularity)", "Menu Konteks Lokal (menu tindakan)", "Pengaturan TalkBack", "Menu Konteks Global"], "answer": "Menu Granularitas Navigasi (Reading granularity)"},
            {"question": "Untuk pengembang aplikasi Windows, memastikan properti 'AccessibleName' dan 'AccessibleRole' diatur dengan benar pada elemen UI sangat penting untuk?", "choices": ["Screen reader dapat mengidentifikasi dan mengumumkan elemen dengan benar", "Aplikasi berjalan lebih cepat", "Ukuran file aplikasi lebih kecil", "Aplikasi terlihat lebih modern"], "answer": "Screen reader dapat mengidentifikasi dan mengumumkan elemen dengan benar"},
            {"question": "Di Android, 'Layanan Aksesibilitas' (Accessibility Service) adalah API yang memungkinkan aplikasi seperti TalkBack untuk?", "choices": ["Menerima event dari sistem dan aplikasi lain, serta memodifikasi interaksi pengguna", "Mengakses internet tanpa izin", "Mengubah wallpaper secara otomatis", "Merekam panggilan telepon"], "answer": "Menerima event dari sistem dan aplikasi lain, serta memodifikasi interaksi pengguna"},
            {"question": "Di Windows Narrator, apa fungsi dari 'Tampilan Narrator' (Narrator Views) seperti 'Karakter', 'Kata', 'Baris', 'Paragraf', 'Judul', 'Tautan'?", "choices": ["Mengubah unit navigasi saat menggunakan perintah baca berikutnya/sebelumnya", "Mengubah tampilan visual Narrator", "Menyaring jenis konten yang dibacakan", "Mengatur kecepatan bicara untuk unit tertentu"], "answer": "Mengubah unit navigasi saat menggunakan perintah baca berikutnya/sebelumnya"}
        ]

        self.questions = list(self.all_questions)
        random.shuffle(self.questions)

        self.current_question_index = 0
        self.score = 0
        self.selected_answer_candidate = ""
        self.first_interactive_widget = None

        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def load_and_play_music(self, filename, intro_sound_obj_for_length_check):
        if not pygame.mixer.get_init(): # Tidak perlu cek self.audio_problem di sini, sudah ditangani di init
            wx.CallAfter(self.display_welcome_message)
            return

        filepath = os.path.join(self.quiz_dir, filename)
        # File existence already checked before calling this for intro
        # but good to have for generic use if this function is called elsewhere
        if not os.path.exists(filepath):
            wx.LogError(f"File musik '{filename}' tidak ditemukan saat akan diputar.")
            self.music_playing = False
            if self.timer and self.timer.IsRunning(): self.timer.Stop()
            wx.CallAfter(self.display_welcome_message) # Lanjut tanpa musik
            return

        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play(0) # Putar sekali
            self.music_playing = True
            
            # Dapatkan panjang musik dari objek Sound yang sudah dimuat (jika ada)
            # atau muat sementara untuk mendapatkan panjangnya.
            # intro_sound_obj_for_length_check sudah dilewatkan sebagai argumen
            if intro_sound_obj_for_length_check:
                 music_length_ms = int(intro_sound_obj_for_length_check.get_length() * 1000)
            else: # Fallback jika objek tidak tersedia, coba muat lagi (seharusnya tidak terjadi untuk intro)
                temp_sound = pygame.mixer.Sound(filepath)
                music_length_ms = int(temp_sound.get_length() * 1000)

            if self.timer:
                self.timer.Start(music_length_ms, wx.TIMER_ONE_SHOT)
        except pygame.error as e:
            wx.LogError(f"Tidak dapat memuat atau memutar musik '{filename}': {e}")
            self.music_playing = False
            if self.timer and self.timer.IsRunning(): self.timer.Stop()
            wx.CallAfter(self.display_welcome_message) # Lanjut tanpa musik


    def on_music_finished(self, event):
        self.stop_music() # Ini akan menghentikan musik jika masih berjalan
        # Timer sudah otomatis berhenti karena one-shot, tapi bisa juga di-stop eksplisit
        if self.timer and self.timer.IsRunning(): self.timer.Stop()
        wx.CallAfter(self.display_welcome_message)

    def stop_music(self):
        if self.music_playing and pygame.mixer.get_init():
            pygame.mixer.music.stop()
            self.music_playing = False

    def display_welcome_message(self):
        welcome_title = "Selamat Datang di Kuis Uji Pengetahuan Teknology Untuk Aksesibilitas !"
        welcome_message = (
            f"{welcome_title}\n\n"
            "Pengembang: Rahes Technology\n\n"
            "Mari uji pengetahuanmu seputar penggunaan Android dan Windows dengan screen reader. " # Koma dihapus
            "Semoga berhasil dan selamat bermain!\n\n"
            "Petunjuk Bermain:\n"
            "- Untuk membaca keseluruhan soal, tekan CapsLock + B (perintah 'Baca Jendela' standar NVDA).\n"
            "  (Atau gunakan perintah screen reader Anda untuk membaca seluruh konten jendela).\n"
            "- Untuk memilih jawaban yang Anda rasa benar, gunakan tombol Tab untuk bernavigasi antar pilihan.\n"
            "- Tekan Enter atau Spasi untuk memilih jawaban yang telah difokus.\n\n"
            "Apakah Anda Siap untuk memulai?"
        )
        if self.panel: # Pastikan panel ada
            # Hentikan ucapan NVDA yang mungkin sedang berjalan dari intro atau error sebelumnya
            if NVDA_AVAILABLE:
                try:
                    if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                        nvdaController.cancelSpeech()
                    else:
                        nvdaController.speakText("") # Cara lama untuk menghentikan jika cancelSpeech tidak ada
                except Exception as e:
                    print(f"Gagal menghentikan ucapan NVDA sebelum pesan selamat datang: {e}")

            dialog = wx.MessageDialog(self, welcome_message, welcome_title, wx.OK | wx.ICON_INFORMATION)
            
            if NVDA_AVAILABLE:
                try:
                    nvda_welcome_text = welcome_message.replace("\n\n", ". ").replace("\n-", ". -").replace("\n", ". ")
                    nvdaController.speakText(nvda_welcome_text)
                except Exception as e:
                    print(f"Gagal berbicara dengan NVDA untuk pesan selamat datang: {e}")

            if dialog.ShowModal() == wx.ID_OK:
                dialog.Destroy()
                self.display_question()
            else: # Jika dialog ditutup dengan cara lain (misal tombol close window)
                dialog.Destroy()
                self.Close(True) # Tutup aplikasi jika tidak menekan OK
        else:
            wx.LogError("Panel tidak siap untuk menampilkan pesan selamat datang.")
            wx.CallAfter(self.Close)


    def display_question(self):
        if not self.panel:
            wx.LogError("Panel tidak tersedia untuk menampilkan pertanyaan.")
            return

        self.panel.DestroyChildren() # Hapus widget lama
        self.vbox = wx.BoxSizer(wx.VERTICAL) # Buat sizer baru
        self.panel.SetSizer(self.vbox)
        self.first_interactive_widget = None # Reset

        if self.current_question_index < len(self.questions):
            question_data = self.questions[self.current_question_index]
            q_label_text = f"Pertanyaan {self.current_question_index + 1}/{len(self.questions)}:\n{question_data['question']}"
            
            question_text_widget = wx.StaticText(self.panel, label=q_label_text)
            question_text_widget.Wrap(self.GetSize()[0] - 40) # Wrap text
            self.vbox.Add(question_text_widget, 0, wx.ALL | wx.EXPAND, 10)
            
            if NVDA_AVAILABLE:
                try:
                    if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                        nvdaController.cancelSpeech()
                    else:
                        nvdaController.speakText("") 
                    nvdaController.speakText(f"Pertanyaan {self.current_question_index + 1}. {question_data['question']}")
                except Exception as e:
                    print(f"Gagal berbicara dengan NVDA untuk pertanyaan: {e}")

            choices = list(question_data["choices"]) # Salin list agar shuffle tidak mengubah data asli
            random.shuffle(choices)

            for i, choice_text in enumerate(choices):
                button = wx.Button(self.panel, label=choice_text)
                button.Bind(wx.EVT_BUTTON, self.on_answer_selected)
                button.Bind(wx.EVT_SET_FOCUS, self.on_button_focus)
                self.vbox.Add(button, 0, wx.ALL | wx.EXPAND, 5)
                if i == 0: # Tandai tombol pertama untuk fokus awal
                    self.first_interactive_widget = button
            
            self.panel.Layout() # Penting untuk me-refresh layout setelah menambah widget

            if self.first_interactive_widget:
                # wx.CallAfter memastikan fokus diatur setelah semua event UI selesai diproses
                wx.CallAfter(self.set_initial_focus_on_widget, self.first_interactive_widget)
        else:
            self.prepare_final_result()


    def on_button_focus(self, event):
        widget = event.GetEventObject()
        if widget and isinstance(widget, wx.Button):
            label = widget.GetLabel()
            if NVDA_AVAILABLE:
                try:
                    if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                        nvdaController.cancelSpeech()
                    else:
                        nvdaController.speakText("")
                    nvdaController.speakText(f"Pilihan: {label}")
                except Exception as e:
                    print(f"Gagal berbicara dengan NVDA untuk tombol '{label}': {e}")
        event.Skip() # Penting agar event fokus standar tetap berjalan


    def set_initial_focus_on_widget(self, widget_to_focus):
        if widget_to_focus and widget_to_focus.IsShownOnScreen() and widget_to_focus.CanAcceptFocus():
            widget_to_focus.SetFocus()

    def on_answer_selected(self, event):
        button = event.GetEventObject()
        self.selected_answer_candidate = button.GetLabel()
        
        # Hentikan ucapan NVDA yang mungkin sedang berjalan (misal dari fokus tombol)
        if NVDA_AVAILABLE:
            try:
                if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                    nvdaController.cancelSpeech()
            except Exception: pass # Abaikan error jika gagal cancel

        dlg = wx.MessageDialog(self, "Apakah Anda yakin dengan jawaban ini?", "Konfirmasi Jawaban", wx.YES_NO | wx.ICON_QUESTION)
        
        # Ucapkan pesan konfirmasi dengan NVDA
        if NVDA_AVAILABLE:
            try:
                nvdaController.speakText("Apakah Anda yakin dengan jawaban ini? Tekan Y untuk ya, N untuk tidak.")
            except Exception as e:
                print(f"Gagal berbicara dengan NVDA untuk konfirmasi: {e}")

        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            self.process_confirmed_answer()
        else:
            # Jika batal, kembalikan fokus ke tombol yang tadi dipilih atau tombol pertama
            if button and button.IsShown() and button.CanAcceptFocus():
                 wx.CallAfter(self.set_initial_focus_on_widget, button)
            elif self.first_interactive_widget:
                 wx.CallAfter(self.set_initial_focus_on_widget, self.first_interactive_widget)


    def process_confirmed_answer(self):
        correct_answer = self.questions[self.current_question_index]["answer"]
        # Nonaktifkan semua tombol pilihan
        for child in self.panel.GetChildren():
            if isinstance(child, wx.Button):
                child.Disable()

        if self.checking_sound and pygame.mixer.get_init(): # Tidak perlu cek self.audio_problem
            try:
                self.checking_sound.play()
                delay_ms = self.checking_sound_duration_ms + 200 # Tambah buffer
                wx.CallLater(delay_ms, self.show_answer_result, self.selected_answer_candidate, correct_answer)
            except pygame.error as e:
                wx.LogError(f"Gagal memutar suara 'memeriksa jawaban': {e}")
                wx.CallLater(200, self.show_answer_result, self.selected_answer_candidate, correct_answer) # Lanjut tanpa delay suara
        else:
            wx.CallLater(200, self.show_answer_result, self.selected_answer_candidate, correct_answer)


    def show_answer_result(self, selected_answer, correct_answer):
        is_correct = (selected_answer == correct_answer)
        result_text = ""
        sound_to_play = None

        if is_correct:
            sound_to_play = self.correct_sound
            result_text = "Jawaban benar!"
            self.score += 1
        else:
            sound_to_play = self.wrong_sound
            result_text = f"Jawaban salah! Jawaban yang benar adalah: {correct_answer}"

        # Hentikan ucapan NVDA yang mungkin sedang berjalan (misal dari suara 'memeriksa')
        if NVDA_AVAILABLE:
            try:
                if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                    nvdaController.cancelSpeech()
            except Exception: pass


        if sound_to_play and pygame.mixer.get_init():
            try:
                sound_to_play.play()
            except pygame.error as e:
                wx.LogError(f"Gagal memutar suara hasil jawaban: {e}")
        
        # Ucapkan hasil dengan NVDA *sebelum* dialog muncul agar tidak terpotong
        if NVDA_AVAILABLE:
            wx.CallLater(50, self._speak_result_nvda, result_text) # Delay kecil agar suara efek bisa mulai dulu

        # Tampilkan dialog setelah jeda singkat (atau setelah suara selesai jika bisa diukur)
        # Untuk kesederhanaan, kita pakai jeda tetap setelah memulai suara efek.
        # Durasi suara efek bisa digunakan di sini jika diinginkan.
        wx.CallLater(1000, self._show_result_dialog_and_proceed, result_text, is_correct)


    def _show_result_dialog_and_proceed(self, result_text, is_correct):
        icon_style = wx.ICON_INFORMATION if is_correct else wx.ICON_WARNING
        # Pastikan dialog muncul di atas frame utama
        dlg = wx.MessageDialog(self, result_text, "Hasil", wx.OK | icon_style)
        dlg.ShowModal()
        dlg.Destroy()

        self.current_question_index += 1
        wx.CallAfter(self.display_question) # Pindah ke pertanyaan berikutnya atau hasil akhir


    def _speak_result_nvda(self, text_to_speak):
        # Fungsi ini dipanggil oleh CallLater, jadi NVDA_AVAILABLE sudah dicek sebelumnya
        try:
            # Tidak perlu cancel speech di sini karena sudah dihandle sebelum memanggil ini
            nvdaController.speakText(text_to_speak)
        except Exception as e:
            print(f"Gagal berbicara dengan NVDA untuk hasil: {e}")


    def prepare_final_result(self):
        if self.game_over_sound and pygame.mixer.get_init():
            try:
                self.game_over_sound.play()
                delay_ms = self.game_over_sound_duration_ms + 200
                wx.CallLater(delay_ms, self.show_final_dialog)
            except pygame.error as e:
                wx.LogError(f"Gagal memutar suara 'permainan selesai': {e}")
                self.show_final_dialog() # Langsung tampilkan jika suara gagal
        else:
            self.show_final_dialog()


    def show_final_dialog(self):
        result_message = f"Permainan selesai!\nSkor Anda: {self.score}/{len(self.questions)}"
        
        if NVDA_AVAILABLE:
            try:
                if hasattr(nvdaController, 'cancelSpeech') and callable(nvdaController.cancelSpeech):
                    nvdaController.cancelSpeech()
                else:
                    nvdaController.speakText("")
                nvda_result_text = result_message.replace("\n", ". ") 
                nvdaController.speakText(nvda_result_text)
            except Exception as e:
                print(f"Gagal berbicara dengan NVDA untuk hasil akhir: {e}")

        dlg = wx.MessageDialog(self, result_message, "Hasil Akhir Kuis", wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()
        self.Close(True)


    def OnClose(self, event):
        print("Menutup aplikasi...")
        if self.timer and self.timer.IsRunning():
            self.timer.Stop()
            print("Timer dihentikan.")

        if pygame.mixer.get_init():
            print("Menghentikan semua suara Pygame...")
            pygame.mixer.music.stop()
            pygame.mixer.stop() # Hentikan semua channel suara
            pygame.mixer.quit()
            print("Pygame mixer di-quit.")
        
        # Tidak perlu uninitialize NVDA Controller secara eksplisit biasanya
        # if NVDA_AVAILABLE:
        #     try:
        #         # nvdaController.terminate() # Jika ada fungsi terminate
        #         pass 
        #     except Exception as e:
        #         print(f"Error saat uninitialize NVDA Controller: {e}")
        
        self.Destroy()
        print("Frame dihancurkan.")


if __name__ == "__main__":
    app = wx.App(False)
    frame = None
    try:
        # Tambahkan pengecekan apakah Pygame berhasil diinisialisasi sebelum membuat frame
        # Ini mungkin terlalu dini, karena mixer init ada di dalam __init__ QuizApp
        # Biarkan error handling di dalam QuizApp menangani kegagalan mixer.
        
        frame = QuizApp(None, title="Kuis Cerdas Test Pengetahuan - By Rahes Technology") 
        if frame:
            frame.Show()
            app.MainLoop()
    except Exception as e:
        # Tangkap error kritis yang mungkin terjadi sebelum frame bisa menanganinya
        # (misalnya, error wxPython parah atau error di get_application_path)
        error_msg = f"Error kritis saat menjalankan aplikasi: {e}\n"
        error_msg += "Pastikan semua dependensi (Pygame, wxPython) terinstal dengan benar.\n"
        error_msg += "Jika masalah berlanjut, periksa log konsol untuk detail lebih lanjut."
        
        # Coba tampilkan wx.LogError jika wx sudah cukup terinisialisasi
        try:
            wx.LogError(error_msg)
        except: # Jika wx pun gagal
            print(f"ERROR KRITIS (wx tidak tersedia untuk log): {error_msg}")

        # Upaya pembersihan jika frame sempat dibuat atau app ada
        if frame:
            try: frame.Close(True)
            except: pass
        if app and wx.GetApp(): # Cek apakah app masih valid
             try: app.Destroy()
             except: pass
        if pygame.mixer.get_init(): # Jika mixer sempat init
            try: pygame.mixer.quit()
            except: pass
    finally:
        print("Aplikasi Selesai.")