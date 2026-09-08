import json
import os
import re
import tempfile
import time
import google.generativeai as genai
from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# Config Halaman Mobile Friendly
st.set_page_config(
    page_title="AI Video Clipper - Hook & Subtitle",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("🎬 AI Video Clipper Mobile")
st.write(
    "Potong video horizontal menjadi klip vertikal (9:16) lengkap dengan"
    " **Hook Banner** dan **Subtitle Otomatis**!"
)


# Helper Function: Render Teks Hook & Subtitle dengan PIL
def draw_styled_text(width, height, text, is_hook=False, font_size=26):
  img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  draw = ImageDraw.Draw(img)

  try:
    font = ImageFont.load_default(size=font_size)
  except Exception:
    font = ImageFont.load_default()

  # Bungkus teks menjadi beberapa baris jika terlalu panjang
  words = text.split()
  lines = []
  curr_line = []
  max_chars = 16 if is_hook else 22

  for w in words:
    curr_line.append(w)
    if len(" ".join(curr_line)) > max_chars:
      if len(curr_line) > 1:
        lines.append(" ".join(curr_line[:-1]))
        curr_line = [w]
      else:
        lines.append(" ".join(curr_line))
        curr_line = []
  if curr_line:
    lines.append(" ".join(curr_line))

  full_text = "\n".join(lines)

  bbox = draw.multiline_textbbox((0, 0), full_text, font=font, align="center")
  text_w = bbox[2] - bbox[0]
  text_h = bbox[3] - bbox[1]

  x = (width - text_w) // 2

  if is_hook:
    y = int(height * 0.12)  # Posisi Hook di bagian atas
  else:
    y = int(height * 0.72)  # Posisi Subtitle di bagian bawah

  pad_x = 16
  pad_y = 10
  bg_box = [x - pad_x, y - pad_y, x + text_w + pad_x, y + text_h + pad_y]

  if is_hook:
    # Banner Hook: Kotak Kuning dengan Teks Hitam Tebal
    draw.rounded_rectangle(bg_box, radius=12, fill=(255, 215, 0, 240))
    draw.multiline_text(
        (x, y), full_text, font=font, fill=(0, 0, 0, 255), align="center"
    )
  else:
    # Subtitle: Kotak Transparan Gelap dengan Teks Kuning + Outline Hitam
    draw.rounded_rectangle(bg_box, radius=10, fill=(0, 0, 0, 180))
    for ox in range(-2, 3):
      for oy in range(-2, 3):
        draw.multiline_text(
            (x + ox, y + oy),
            full_text,
            font=font,
            fill=(0, 0, 0, 255),
            align="center",
        )
    draw.multiline_text(
        (x, y), full_text, font=font, fill=(255, 255, 0, 255), align="center"
    )

  return np.array(img)


# Sidebar Pengaturan
with st.sidebar:
  st.header("⚙️ Pengaturan AI")
  api_key = st.text_input(
      "Gemini API Key",
      type="password",
      help="Dapatkan API Key gratis di aistudio.google.com",
  )

# Upload File Video
uploaded_file = st.file_uploader(
    "Pilih Video dari Galeri HP Anda", type=["mp4", "mov", "avi", "mkv"]
)

if uploaded_file is not None:
  st.subheader("📹 Preview Video Asli")
  st.video(uploaded_file)

  if st.button("🚀 Potong Video + Hook + Subtitle", use_container_width=True):
    if not api_key:
      st.error("⚠️ Silakan masukkan Gemini API Key di menu samping (Sidebar)!")
    else:
      try:
        with st.status(
            "Sedang memproses video dengan Gemini AI...", expanded=True
        ) as status:

          # 1. Simpan File Sementara
          st.write("📁 Menyimpan file sementara...")
          with tempfile.NamedTemporaryFile(
              delete=False, suffix=".mp4"
          ) as tmp_file:
            tmp_file.write(uploaded_file.read())
            input_video_path = tmp_file.name

          audio_path = input_video_path + ".mp3"
          output_clip_path = input_video_path + "_output.mp4"

          # 2. Ekstrak Audio
          st.write("🎵 Mengekstrak audio dari video...")
          video = VideoFileClip(input_video_path)
          video.audio.write_audiofile(audio_path, logger=None)
          video.close()

          # 3. Analisis Audio + Buat Subtitle & Hook dengan Gemini AI
          st.write("🧠 Menganalisis audio & membuat subtitle dengan Gemini AI...")
          genai.configure(api_key=api_key)

          uploaded_audio = genai.upload_file(audio_path)

          while uploaded_audio.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_audio = genai.get_file(uploaded_audio.name)

          gemini_model = genai.GenerativeModel("gemini-2.5-flash")

          prompt = """
                    Dengarkan audio berikut dengan seksama. 
                    1. Pilih 1 bagian paling menarik/viral berdurasi 20 hingga 40 detik untuk dijadikan video Reels/TikTok.
                    2. Buat judul HOOK singkat & menarik (max 6 kata) untuk dipasang di atas video.
                    3. Buat daftar SUBTITLE lengkap khusus untuk bagian klip yang terpilih.
                       Timestamp subtitle (start dan end) dihitung dalam DETIK RELATIF terhadap awal klip (dimulai dari 0 detik). Setiap baris subtitle berisi 3-6 kata.

                    Tanggapi HANYA dengan format JSON valid berikut tanpa teks markdown/penjelasan tambahan:
                    {
                      "start": detik_mulai_audio_asli, 
                      "end": detik_selesai_audio_asli, 
                      "hook": "JUDUL HOOK VIRAL 😱", 
                      "reason": "Alasan memilih bagian ini",
                      "subtitles": [
                        {"start": 0.0, "end": 2.5, "text": "Kata-kata subtitle pertama"},
                        {"start": 2.5, "end": 5.0, "text": "Kata-kata subtitle kedua"}
                      ]
                    }
                    """

          response = gemini_model.generate_content([uploaded_audio, prompt])

          try:
            genai.delete_file(uploaded_audio.name)
          except:
            pass

          clean_json = re.sub(r"```json|```", "", response.text).strip()
          highlight = json.loads(clean_json)

          st.write(
              f"✨ **Hook Ditemukan:** {highlight.get('hook', 'Klip Viral')}"
          )

          # 4. Crop Video ke Format 9:16 Vertikal
          st.write("✂️ Memotong & mengubah ukuran ke vertikal (9:16)...")
          start_sec = float(highlight["start"])
          end_sec = float(highlight["end"])

          clip = VideoFileClip(input_video_path).subclip(start_sec, end_sec)

          w, h = clip.size
          crop_width = int(h * (9 / 16))

          if crop_width < w:
            x_center = w / 2
            x1 = x_center - (crop_width / 2)
            clip_cropped = clip.crop(x1=x1, width=crop_width, height=h)
          else:
            clip_cropped = clip

          # 5. Pasang Overlay Hook & Subtitle
          st.write("🎨 Menambahkan Banner Hook & Subtitle Otomatis...")
          overlay_clips = []

          # A. Hook Clip (Muncul 6 detik pertama)
          hook_text = highlight.get("hook", "")
          if hook_text:
            hook_img = draw_styled_text(
                crop_width, h, hook_text, is_hook=True, font_size=26
            )
            hook_dur = min(6.0, clip_cropped.duration)
            hook_clip = (
                ImageClip(hook_img, transparent=True)
                .set_start(0)
                .set_duration(hook_dur)
            )
            overlay_clips.append(hook_clip)

          # B. Subtitle Clips (Muncul bergantian)
          subtitles = highlight.get("subtitles", [])
          for sub in subtitles:
            s_text = sub.get("text", "").strip()
            if not s_text:
              continue
            s_start = float(sub.get("start", 0))
            s_end = float(sub.get("end", 0))

            if s_start < clip_cropped.duration and s_end > s_start:
              s_dur = min(s_end, clip_cropped.duration) - s_start
              sub_img = draw_styled_text(
                  crop_width, h, s_text, is_hook=False, font_size=24
              )
              sub_clip = (
                  ImageClip(sub_img, transparent=True)
                  .set_start(s_start)
                  .set_duration(s_dur)
              )
              overlay_clips.append(sub_clip)

          if overlay_clips:
            final_clip = CompositeVideoClip([clip_cropped, *overlay_clips])
          else:
            final_clip = clip_cropped

          # Render Video Akhir
          final_clip.write_videofile(
              output_clip_path,
              codec="libx264",
              audio_codec="aac",
              temp_audiofile=input_video_path + "_temp_audio.m4a",
              logger=None,
          )

          clip.close()
          final_clip.close()

          status.update(
              label="🎉 Selesai memproses klip!",
              state="complete",
              expanded=False,
          )

        # Hasil Akhir
        st.success("✅ Klip Berhasil Dibuat!")
        st.subheader(f"🔥 {highlight.get('hook', 'Klip Hasil AI')}")
        st.caption(f"💡 *{highlight.get('reason', '')}*")

        with open(output_clip_path, "rb") as video_file:
          video_bytes = video_file.read()
          st.video(video_bytes)

          st.download_button(
              label="📥 Download Klip (Dengan Hook & Subtitle)",
              data=video_bytes,
              file_name="viral_clip_subtitle.mp4",
              mime="video/mp4",
              use_container_width=True,
          )

        # Bersihkan file sampah
        for path in [input_video_path, audio_path, output_clip_path]:
          if os.path.exists(path):
            os.remove(path)

      except Exception as e:
        st.error(f"Terjadi kesalahan: {str(e)}")

