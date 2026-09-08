import streamlit as st
import os
import tempfile
import json
import google.generativeai as genai
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# SETUP & KONFIGURASI HALAMAN
# ---------------------------------------------------------
st.set_page_config(page_title="AI Video Clipper Mobile", page_icon="🎬", layout="centered")
st.title("🎬 AI Video Clipper Mobile")
st.write("Potong video horizontal menjadi klip vertikal (9:16) lengkap dengan **Hook Banner** dan **Subtitle Otomatis**!")

# ---------------------------------------------------------
# PEMBACAAN API KEY (OTOMATIS / MANUAL)
# ---------------------------------------------------------
st.sidebar.header("🔑 Pengaturan")
api_key_input = st.sidebar.text_input("Gemini API Key", type="password", help="Masukkan API Key berawalan AIzaSy...")

# Gunakan API Key dari input sidebar, atau otomatis ambil dari Secrets jika sidebar kosong
api_key = api_key_input.strip() if api_key_input.strip() else st.secrets.get("GEMINI_API_KEY", "")

if not api_key:
    st.warning("⚠️ Silakan masukkan Gemini API Key di menu samping (Sidebar) atau simpan di Streamlit Secrets!")

# ---------------------------------------------------------
# HELPER: RENDERING TEKS GAMBAR PIL (TANPA IMAGEMAGICK)
# ---------------------------------------------------------
def create_hook_banner(text, width=720, height=180):
    """Membuat Banner Hook Kuning Teks Hitam"""
    img = Image.new("RGBA", (width, height), (255, 220, 0, 230))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except:
        font = ImageFont.load_default()

    # Dynamic Wrapping sederhananya
    words = text.split()
    lines, current = [], []
    for w in words:
        current.append(w)
        bbox = draw.textbbox((0, 0), " ".join(current), font=font)
        if (bbox[2] - bbox[0]) > (width - 40):
            current.pop()
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    
    full_text = "\n".join(lines)
    bbox = draw.textmultilinebbox((0, 0), full_text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.multiline_text((x, y), full_text, fill="black", font=font, align="center")
    
    temp_path = tempfile.mktemp(suffix=".png")
    img.save(temp_path)
    return temp_path

def create_subtitle_overlay(text, width=720, height=120):
    """Membuat Subtitle Putih Outline Hitam Transparan"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2

    # Draw Outline
    for stroke_x in range(-2, 3):
        for stroke_y in range(-2, 3):
            draw.text((x + stroke_x, y + stroke_y), text, font=font, fill="black")
    # Draw Main Text
    draw.text((x, y), text, font=font, fill="yellow")

    temp_path = tempfile.mktemp(suffix=".png")
    img.save(temp_path)
    return temp_path

# ---------------------------------------------------------
# GEMINI AI AUDIO ANALYSIS
# ---------------------------------------------------------
def analyze_audio_with_gemini(audio_path, key):
    genai.configure(api_key=key)
    audio_file = genai.upload_file(audio_path)
    
    prompt = """
    Analisis audio berikut dan pilih 1 bagian paling seru/viral berdurasi 15-45 detik.
    Berikan respon HANYA format JSON valid tanpa markdown backticks seperti ini:
    {
      "start_time": 10.5,
      "end_time": 35.0,
      "hook_text": "RAHASIA CEPAT CUAN DARI RUMAH!",
      "subtitle": "Klip menarik tentang strategi bisnis digital"
    }
    """
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content([audio_file, prompt])
    
    # Clean output
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

# ---------------------------------------------------------
# MAIN INTERFACE
# ---------------------------------------------------------
uploaded_file = st.file_uploader("Pilih Video dari Galeri HP Anda", type=["mp4", "mov", "avi"])

if uploaded_file:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(uploaded_file.read())
        video_path = tmp.name

    clip = VideoFileClip(video_path)
    st.video(video_path)
    st.info(f"Durasi Video: {int(clip.duration)} detik")

    if clip.duration > 300:
        st.warning("⚠️ Video cukup panjang (>5 menit). Pemrosesan mungkin membutuhkan waktu lebih lama di Streamlit Cloud.")

    if st.button("🚀 Potong Video + Hook + Subtitle"):
        if not api_key:
            st.error("Silakan masukkan API Key Gemini terlebih dahulu!")
            st.stop()

        status = st.status("Sedang memproses video...", expanded=True)
        
        try:
            # 1. Ekstrak Audio saja agar upload ringan
            status.write("🎵 Mengekstrak audio...")
            audio_path = tempfile.mktemp(suffix=".mp3")
            clip.audio.write_audiofile(audio_path, logger=None)

            # 2. Kirim Audio ke Gemini
            status.write("🧠 Menganalisis audio & menentukan klip terbaik dengan Gemini AI...")
            ai_data = analyze_audio_with_gemini(audio_path, api_key)
            
            start_t = float(ai_data.get("start_time", 0))
            end_t = min(float(ai_data.get("end_time", clip.duration)), clip.duration)
            hook_text = ai_data.get("hook_text", "KLIP PILIHAN AI")
            sub_text = ai_data.get("subtitle", "")

            # 3. Potong Video & Format 9:16 Vertikal
            status.write("✂️ Memotong video & menyesuaikan ukuran 9:16 (Vertikal)...")
            subclip = clip.subclip(start_t, end_t)
            
            # Crop Center ke 9:16
            w, h = subclip.size
            target_w = int(h * (9 / 16))
            if target_w < w:
                crop_x1 = (w - target_w) // 2
                subclip = subclip.crop(x1=crop_x1, width=target_w)
            
            subclip = subclip.resize(height=1280)  # Standard Vertical Height

            # 4. Tambahkan Overlay Banner Hook & Subtitle
            status.write("🎨 Menempelkan Hook Banner & Subtitle...")
            hook_img = create_hook_banner(hook_text, width=subclip.w, height=180)
            hook_clip = ImageClip(hook_img).set_duration(subclip.duration).set_position(("center", 100))

            overlays = [subclip, hook_clip]

            if sub_text:
                sub_img = create_subtitle_overlay(sub_text, width=subclip.w, height=120)
                sub_overlay = ImageClip(sub_img).set_duration(subclip.duration).set_position(("center", subclip.h - 200))
                overlays.append(sub_overlay)

            final_video = CompositeVideoClip(overlays)

            # 5. Export Hasil
            status.write("🎬 Menyusun video akhir...")
            output_path = tempfile.mktemp(suffix=".mp4")
            final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24, logger=None)

            status.update(label="✅ Pemrosesan Selesai!", state="complete", expanded=False)

            # Tampilkan Hasil & Download
            st.success(f"Hook: **{hook_text}**")
            st.video(output_path)

            with open(output_path, "rb") as file:
                st.download_button(
                    label="📥 Download Video Vertikal (9:16)",
                    data=file,
                    file_name="klip_viral_ai.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            status.update(label="❌ Terjadi Kesalahan", state="error")
            st.error(f"Error: {str(e)}")
