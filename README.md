# DiscordClipHandler

### add the env file in the same directory as the script with the following content
```
# 🔹 Discord Webhook URL (Replace with your actual webhook)
DISCORD_WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL"


# 🔹 Email Configuration
SMTP_SERVER="smtp.gmail.com"  # Change for other providers if needed
SMTP_PORT=587
EMAIL_SENDER="YOUR_EMAIL@gmail.com"
EMAIL_PASSWORD="YOUR_APP_PASSWORD"  # Use an app password, NOT your real password!
EMAIL_RECEIVER="RECEIVER_EMAIL@gmail.com"
# 🔹 Folders where video clips are saved (Update these paths), place all three inside a single pair of quotation marks
CLIPS_FOLDERS="/path/to/folder1,/path/to/folder2,/path/to/folder3"
```
- Please fill in the necessary data in the env file and save it as `.env` in the same directory as the script.
