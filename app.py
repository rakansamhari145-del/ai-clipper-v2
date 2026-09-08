import json
import os
import re
import tempfile
import google.generativeai as genai
from moviepy.editor import VideoFileClip
import streamlit as st
import whisper

# Config Halaman Mobile Friendly
st.set_page_config(
    page_title="AI Video Clipper",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("🎬 AI Video Clipper Mobile")
st.write(
    "Ubah video horizontal Anda menjadi klip vertikal (9:16) otomatis"
    " menggunakan AI!"
)

# Sidebar Pengaturan
with st.sidebar:
  st.header("⚙️ Pengaturan AI")
  api_key = st.text_input(
      "Gemini API Key",
      type="password",
      help="Dapatkan API Key gratis di aistudio.google.com",
  )
  whisper_model_type = st.selectbox(
      "Ukuran Model Whisper (Akurasi)",
      ["tiny", "base", "small"],
      index=0,
      help="'tiny' paling cepat, 'small' lebih akurat.",
  )

# Upload File Video
uploaded_file = st.file_uploader(
    "Pilih Video dari Galeri HP Anda", type=["mp4", "mov", "avi", "mkv"]
)

if uploaded_file is not None:
  st.subheader("📹 Preview Video Asli")
  st.video(uploaded_file)

  if st.button("🚀 Potong Video dengan AI", use_container_width=True):
    if not api_key:
      st.error("⚠️ Silakan masukkan Gemini API Key di menu samping (Sidebar)!")
    else:
      try:
        with st.status("Sedang memproses video...", expanded=True) as status:

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
          st.write("🎵 Mengambil audio dari video...")
          video = VideoFileClip(input_video_path)
          video.audio.write_audiofile(audio_path, logger=None)
          video.close()

          # 3. Transkripsi Audio
          st.write(
              f"🎙️ Mengubah suara ke teks dengan Whisper"
              f" ({whisper_model_type})..."
          )
          model = whisper.load_model(whisper_model_type)
          transcript_result = model.transcribe(audio_path)
          segments = transcript_result["segments"]

          # 4. Cari Momen Terbaik dengan Gemini AI
          st.write("🧠 Menganalisis momen paling viral dengan Gemini AI...")
          genai.configure(api_key=api_key)
          gemini_model = genai.GenerativeModel("gemini-2.5-flash")

          transcript_text = "\n".join([
              f"{s['start']:.1f}s - {s['end']:.1f}s: {s['text']}"
              for s in segments
          ])

          prompt = f"""
                    Kamu adalah editor video viral. Berikut transkrip video beserta durasi:
                    {transcript_text}

                    Pilih 1 momen terbaik/paling menarik berdurasi 20-40 detik.
                    Tanggapi HANYA dalam format JSON valid berikut tanpa teks markdown tambahan:
                    {{"start": detik_mulai, "end": detik_selesai, "title": "Judul Klip", "reason": "Alasan memilih"}}
                    """

          response = gemini_model.generate_content(prompt)
          clean_json = re.sub(r"```json|```", "", response.text).strip()
          highlight = json.loads(clean_json)

          st.write(f"✨ **Momen Ditemukan:** {highlight.get('title')}")

          # 5. Crop Video ke Format 9:16 Vertikal
          st.write("✂️ Memotong & mengubah ukuran ke vertikal (9:16)...")
          clip = VideoFileClip(input_video_path).subclip(
              highlight["start"], highlight["end"]
          )

          w, h = clip.size
          crop_width = int(h * (9 / 16))

          if crop_width < w:
            x_center = w / 2
            x1 = x_center - (crop_width / 2)
            clip_cropped = clip.crop(x1=x1, width=crop_width, height=h)
          else:
            clip_cropped = clip

          clip_cropped.write_videofile(
              output_clip_path,
              codec="libx264",
              audio_codec="aac",
              temp_audiofile=input_video_path + "_temp_audio.m4a",
              logger=None,
          )
          clip.close()

          status.update(
              label="🎉 Selesai memproses klip!",
              state="complete",
              expanded=False,
          )

        # Hasil Pemotongan
        st.success("✅ Klip Berhasil Dibuat!")
        st.subheader(f"📌 {highlight.get('title')}")
        st.caption(f"💡 *{highlight.get('reason')}*")

        with open(output_clip_path, "rb") as video_file:
          video_bytes = video_file.read()
          st.video(video_bytes)

          st.download_button(
              label="📥 Download Klip (Vertikal 9:16)",
              data=video_bytes,
              file_name="viral_clip_hp.mp4",
              mime="video/mp4",
              use_container_width=True,
          )

        # Bersihkan file sampah
        if os.path.exists(input_video_path):
          os.remove(input_video_path)
        if os.path.exists(audio_path):
          os.remove(audio_path)
        if os.path.exists(output_clip_path):
          os.remove(output_clip_path)

      except Exception as e:
        st.error(f"Terjadi kesalahan: {str(e)}")
