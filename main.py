import os
import time
import smtplib
from moviepy import VideoFileClip
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
MAX_SIZE_MB = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
INITIAL_BITRATE = 1000  # Initial bitrate in kbps


class VideoHandler(FileSystemEventHandler):
    """Handles new video files added to the folder."""

    def on_created(self, event):
        if event.is_directory:
            return  # Ignore directories

        if "compressed" in event.src_path:
            return

        time.sleep(30) # make sure the clip was saved completely
        file_path = event.src_path
        if file_path.endswith((".mp4", ".mov", ".avi")):
            print(f"📂 New video detected: {file_path}")
            try:

                if os.path.getsize(file_path) <= MAX_SIZE_BYTES:
                    upload_to_discord(file_path)
                    return

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
    """Compress video iteratively to fit under 25MB using MoviePy."""
    input_path = os.path.abspath(input_path)
    output_path = os.path.join(os.path.dirname(input_path), "compressed_" + os.path.basename(input_path))

    try:
        # Load the video
        clip = VideoFileClip(input_path)

        # Start with an initial resolution and bitrate
        new_width = clip.w // 2
        new_height = clip.h // 2
        bitrate = INITIAL_BITRATE

        while True:
            # Resize video
            clip_resized = clip.resized((new_width, new_height))

            # Save with reduced bitrate
            clip_resized.write_videofile(output_path, codec="libx264", bitrate=f"{bitrate}k", audio_codec="aac")

            # Check file size
            file_size = os.path.getsize(output_path)
            if file_size <= MAX_SIZE_BYTES:
                print(f"✅ Compression successful: {output_path} ({file_size / (1024 * 1024):.2f} MB)")
                clip.close()
                clip_resized.close()
                return output_path

            print(f"🚨 File still too big ({file_size / (1024 * 1024):.2f} MB), reducing quality further...")

            # Reduce bitrate and resolution for next iteration
            bitrate = int(bitrate * 0.85)  # Reduce bitrate by 15%
            new_width = max(new_width * 0.9, 320)  # Reduce width but not below 320px
            new_height = max(new_height * 0.9, 180)  # Reduce height but not below 180px

            # If bitrate goes too low, break to avoid extreme quality loss
            if bitrate < 200:
                print("⚠️ Unable to compress further without severe quality loss.")
                clip.close()
                clip_resized.close()
                return None

    except Exception as e:
        print(f"❌ Error compressing video: {e}")
        return None

def upload_to_discord(file_path):
    """Uploads the compressed file to Discord via webhook."""
    try:
        with open(file_path, "rb") as f:
            response = requests.post(DISCORD_WEBHOOK_URL, files={"file": f})

        if response.status_code == 200:
            print(f"✅ Uploaded {file_path} to Discord successfully!")
            # Delete all files in the directory with names containing "compressed"
        else:
            print(f"❌ Failed to upload: {response.text}")
            send_email_alert(f"Failed to upload {file_path} to Discord. Response: {response.text}")
    except Exception as e:
        print(f"❌ Error uploading to Discord: {e}")
        send_email_alert(f"Error uploading {file_path} to Discord: {str(e)}")

    for file in os.listdir(os.path.dirname(file_path)):
        if "compressed" in file:
            os.remove(os.path.join(os.path.dirname(file_path), file))


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
