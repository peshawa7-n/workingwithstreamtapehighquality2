import os
import logging
import yt_dlp
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ====== CONFIGURATION ======
TELEGRAM_BOT_TOKEN = "BOT_TOKEN"
STREAMTAPE_API_USER = "STREAMTAPE_API_USERNAME"
STREAMTAPE_API_KEY = "STREAMTAPE_API_KEY"
DOWNLOAD_FOLDER = "/tmp/downloads"
# ===========================

logging.basicConfig(level=logging.INFO)

user_data = {}  # Track user steps and input


def start(update: Update, context: CallbackContext):
    update.message.reply_text("Send me the YouTube link.")
    user_data[update.effective_chat.id] = {"step": "waiting_for_link"}


def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text = update.message.text

    if chat_id not in user_data:
        user_data[chat_id] = {}

    step = user_data[chat_id].get("step")

    if step == "waiting_for_link":
        user_data[chat_id]["link"] = text
        user_data[chat_id]["step"] = "waiting_for_folder"
        update.message.reply_text("Now send me the Streamtape folder name.")
    elif step == "waiting_for_folder":
        user_data[chat_id]["folder"] = text
        update.message.reply_text("Downloading and uploading... Please wait.")
        context.bot.send_chat_action(chat_id=chat_id, action="upload_video")

        # Process download and upload
        link = user_data[chat_id]["link"]
        folder = user_data[chat_id]["folder"]
        filename = download_youtube_video(link)

        if filename:
            streamtape_link = upload_to_streamtape(filename, folder)
            if streamtape_link:
                update.message.reply_text(f"✅ Uploaded: {streamtape_link}")
            else:
                update.message.reply_text("❌ Failed to upload to Streamtape.")
        else:
            update.message.reply_text("❌ Failed to download video.")

        # Reset user data
        user_data[chat_id] = {"step": "waiting_for_link"}
    else:
        update.message.reply_text("Please send /start to begin.")


def download_youtube_video(url: str):
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp4').replace('.mkv', '.mp4')
            return filename
    except Exception as e:
        logging.error(f"Download failed: {e}")
        return None


def upload_to_streamtape(filepath, folder_name):
    try:
        # Get upload URL
        res = requests.get(
            f"https://api.streamtape.com/file/ul?login={STREAMTAPE_API_USER}&key={STREAMTAPE_API_KEY}"
        ).json()

        upload_url = res["result"]["url"]
        with open(filepath, "rb") as f:
            files = {'file1': f}
            r = requests.post(upload_url, files=files).json()

        if r["status"] != 200:
            return None

        file_code = r["result"]["filecode"]

        # Move to desired folder
        requests.get(
            f"https://api.streamtape.com/file/mov?file={file_code}&folder={folder_name}&login={STREAMTAPE_API_USER}&key={STREAMTAPE_API_KEY}"
        )

        return f"https://streamtape.com/v/{file_code}"
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return None


def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
