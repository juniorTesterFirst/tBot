
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from dotenv import load_dotenv
import os
load_dotenv()


# 🔐 Tokenlar


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("⚠️ Iltimos, `.env` faylda TELEGRAM_TOKEN va OPENAI_API_KEY to‘g‘ri yozilganiga ishonch hosil qiling.")
import openai
openai.api_key = OPENAI_API_KEY
def analyze_response(text):
    prompt = f"""Kandidat quyidagi javoblarni berdi. Bu javoblar asosida bu odam IT kompaniyada backend developer sifatida ishlashga mosmi yoki yo‘q?
    Savollar:
    - Ismingiz?
    - Yoshingiz?
    - Tajribangiz qancha?
    - Qaysi texnologiyalarni bilasiz?
    - Ishga munosabatingiz qanday?
    
    Javob:
    {text}

    Iltimos, qisqacha natija bering: mos yoki mos emas, va sababi bilan.
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Siz rekruter yordamchi AI botisiz."},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Iltimos, quyidagi formatda javob bering:\n\n"
                                    "Ism: \nYosh: \nTajriba: \nTexnologiyalar: \nIshga munosabat:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    result = analyze_response(user_input)
    await update.message.reply_text("Natija:\n" + result)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
