import os
import time
import smtplib
import moviepy as mp
import requests
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load environment variables from .env
load_dotenv()

# 🔹 Load configurations from .env
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CLIPS_FOLDER = os.getenv("CLIPS_FOLDER")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# 🔹 Maximum allowed file size for Discord (25MB)
MAX_SIZE_MB = 25
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


class VideoHandler(FileSystemEventHandler):
    """Handles new video files added to the folder."""

    def on_created(self, event):
        if event.is_directory:
            return  # Ignore directories

        file_path = event.src_path
        if file_path.endswith((".mp4", ".mov", ".avi")):
            print(f"📂 New video detected: {file_path}")
            try:
                compressed_path = compress_video(file_path)

                if compressed_path:
                    file_size = os.path.getsize(compressed_path)

                    if file_size <= MAX_SIZE_BYTES:
                        upload_to_discord(compressed_path)
                    else:
                        print(f"🚨 {compressed_path} is still too big! Sending email alert...")
                        send_email_alert(f"{compressed_path} is still too large to upload.")
            except Exception as e:
                print(f"❌ Error during video processing: {e}")
                send_email_alert(f"Error processing video {file_path}: {str(e)}")


def compress_video(input_path):
    """Compress video to fit under 25MB."""
    output_path = os.path.join(CLIPS_FOLDER, f"compressed_{os.path.basename(input_path)}")

    try:
        clip = mp.VideoFileClip(input_path)

        # 🔹 Lower bitrate for higher compression
        target_bitrate = "400k"  # Lower = smaller file size

        clip.write_videofile(
            output_path,
            codec="libx264",
            preset="ultrafast",  # Fast encoding
            bitrate=target_bitrate,
            audio_codec="aac"
        )
    except Exception as e:
        print(f"❌ Error compressing video: {e}")
        send_email_alert(f"Error compressing video {input_path}: {str(e)}")
        return None

    return output_path


def upload_to_discord(file_path):
    """Uploads the compressed file to Discord via webhook."""
    try:
        with open(file_path, "rb") as f:
            response = requests.post(DISCORD_WEBHOOK_URL, files={"file": f})

        if response.status_code == 200:
            print(f"✅ Uploaded {file_path} to Discord successfully!")
        else:
            print(f"❌ Failed to upload: {response.text}")
            send_email_alert(f"Failed to upload {file_path} to Discord. Response: {response.text}")
    except Exception as e:
        print(f"❌ Error uploading to Discord: {e}")
        send_email_alert(f"Error uploading {file_path} to Discord: {str(e)}")


def send_email_alert(message):
    """Send an email alert with the given message."""
    subject = "🚨 Video Processing Alert 🚨"
    body = message

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print("📧 Email alert sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def start_monitoring():
    """Starts monitoring the folder for new videos."""
    event_handler = VideoHandler()
    observer = Observer()
    observer.schedule(event_handler, CLIPS_FOLDER, recursive=False)
    observer.start()
    print(f"🔍 Watching folder: {CLIPS_FOLDER} for new videos...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_monitoring()
