import os
import time
import smtplib
import subprocess
import requests
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

# Load environment variables from .env
load_dotenv()

# 🔹 Load configurations from .env
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CLIPS_FOLDERS = os.getenv("CLIPS_FOLDERS").split(",")
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
        print(f"Waiting for video to save successfully")

        time.sleep(15) # make sure the clip was saved completely
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
    """Compress video using NVIDIA GPU (NVENC) to fit under 25MB."""
    input_path = os.path.abspath(input_path)
    output_path = os.path.join(os.path.dirname(input_path), "compressed_" + os.path.basename(input_path))

    bitrate = 1000  # Start with 1000k bitrate
    width = 1280  # Target width
    height = 720   # Target height

    while True:
        try:
            # Run FFmpeg with NVENC for GPU-based compression
            command = [
                "ffmpeg", "-y", "-hwaccel", "cuda", "-i", input_path,
                "-vf", f"scale={width}:{height}",
                "-c:v", "h264_nvenc", "-b:v", f"{bitrate}k",
                "-preset", "p5", "-c:a", "aac", "-b:a", "128k",
                output_path
            ]

            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            # Check the file size
            file_size = os.path.getsize(output_path)
            if file_size <= MAX_SIZE_BYTES:
                print(f"✅ Compression successful: {output_path} ({file_size / (1024 * 1024):.2f} MB)")
                return output_path

            print(f"🚨 File still too big ({file_size / (1024 * 1024):.2f} MB), reducing quality further...")

            # Reduce bitrate and resolution for next attempt
            bitrate = int(bitrate * 0.85)
            width = max(int(width * 0.9), 320)
            height = max(int(height * 0.9), 180)

            if bitrate < 200:
                print("⚠️ Unable to compress further without severe quality loss.")
                return None

        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg error: {e.stderr.decode()}")
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
    if EMAIL_SENDER is None or EMAIL_RECEIVER is None:
        print("❌ Email sender or receiver not configured. Cannot send email alert.")
        return

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


def start_monitoring(folders):
    """Starts monitoring multiple folders for new videos."""
    observers = []

    for folder in folders:
        print(f"Setting up watcher for folder: {folder}")
        event_handler = VideoHandler()
        observer = PollingObserver()
        observer.schedule(event_handler, folder, recursive=False)
        observer.start()
        observers.append(observer)
        print(f"🔍 Watching folder: {folder} for new videos...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for observer in observers:
            observer.stop()
    for observer in observers:
        observer.join()



if __name__ == "__main__":
    print(f"🚀 Starting video monitoring service...{CLIPS_FOLDERS}")
    start_monitoring(CLIPS_FOLDERS)
