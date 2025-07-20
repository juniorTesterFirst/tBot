    from telegram import Update
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
        ConversationHandler
    )
    from dotenv import load_dotenv
    import os
    import openai
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    load_dotenv()

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "AI Recruiter Admin")

    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("⚠️ Iltimos, `.env` faylda TELEGRAM_TOKEN va OPENAI_API_KEY to‘g‘ri yozilganiga ishonch hosil qiling.")

    # --- GOOGLE SHEETGA ULANISH ---
    def get_sheet(sheet_name="AI Recruiter Admin", worksheet_name="Kandidat javoblari"):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("google-credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        return sheet

    def write_to_sheet(data):
        try:
            sheet = get_sheet()
            sheet.append_row(data)
        except Exception as e:
            print(f"Google Sheetga yozishda xatolik: {e}")

    # --- AI yordamida savollar generatsiyasi (O‘zbekcha) ---
    def generate_questions(position):
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            f"Siz tajribali HR mutaxassissiz. "
            f'"{position}" lavozimi uchun nomzoddan intervyu jarayonida so‘ralsa foydali bo‘ladigan 5 ta qisqa, adabiy o‘zbek tilida, imloviy va grammatik xatolarsiz savol tuzing. '
            "Javobingizda faqat savollar ro‘yxatini yozing, boshqa izoh yoki gaplar kerak emas."
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Siz HR intervyu botisiz."},
                {"role": "user", "content": prompt}
            ]
        )
        # Tozalash (AI ba'zida 1., 2., yoki '-' bilan yozishi mumkin)
        savollar = [
            s.strip('- ').strip()
            for s in response.choices[0].message.content.strip().split('\n')
            if s.strip()
        ]
        # Faqat 5 ta savol
        return savollar[:5]

    # --- Javoblar tahlili va xulosa (O‘zbekcha) ---
    def analyze_responses(position, qa_list):
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            f"Siz tajribali HR mutaxassissiz. Quyida '{position}' lavozimiga nomzoddan olingan 5 ta savol va javoblar bor:\n\n"
            + '\n'.join([f"{i+1}. Savol: {qa[0]}\nJavob: {qa[1]}" for i, qa in enumerate(qa_list)]) +
            "\n\nSizdan quyidagini so‘rayman:\n1. Nomzod shu lavozimga mosmi? (Mos yoki mos emas deb yozing)\n2. Qisqacha asoslab bering (2-3 gapda, o‘zbek tilida)."
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Siz HR intervyu botisiz."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()

    # --- STATE-lar ---
    POSITION, INTERVIEW = range(2)

    # --- TELEGRAM BOT HANDLERLARI ---
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Assalomu alaykum! Qaysi lavozimga nomzodlik uchun suhbat boshlaymiz?\n"
            "(Masalan: 'Sotuvchi', 'Dasturchi', 'Operator' va hokazo)"
        )
        return POSITION

    async def get_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
        position = update.message.text.strip()
        context.user_data['position'] = position
        # AI orqali savollar generatsiyasi
        savollar = generate_questions(position)
        context.user_data['savollar'] = savollar
        context.user_data['javoblar'] = []
        context.user_data['soralgan'] = 0

        # 1-savolni yuborish
        await update.message.reply_text(f"1-savol:\n{savollar[0]}")
        return INTERVIEW

    async def interview(update: Update, context: ContextTypes.DEFAULT_TYPE):
        javob = update.message.text.strip()
        javoblar = context.user_data.get('javoblar', [])
        savollar = context.user_data['savollar']
        soralgan = context.user_data.get('soralgan', 0)

        # Javobni saqlash
        javoblar.append(javob)
        context.user_data['javoblar'] = javoblar
        context.user_data['soralgan'] = soralgan + 1

        # Navbatdagi savol bormi?
        if context.user_data['soralgan'] < len(savollar):
            idx = context.user_data['soralgan']
            await update.message.reply_text(f"{idx+1}-savol:\n{savollar[idx]}")
            return INTERVIEW
        else:
            # 5 ta javob to‘plandi, natija chiqaramiz
            qa_list = list(zip(savollar, javoblar))
            position = context.user_data['position']
            result = analyze_responses(position, qa_list)
            user = update.message.from_user

            # Gsheetga yozish
            write_to_sheet([
                str(user.id),
                user.username or "",
                user.first_name or "",
                position,
                "; ".join([f"{i+1}) {q} | {a}" for i, (q, a) in enumerate(qa_list)]),
                result
            ])

            await update.message.reply_text("Suhbat natijasi:\n" + result)
            return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Suhbat bekor qilindi.")
        return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_position)],
            INTERVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, interview)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("Bot webhook orqali ishga tushdi...")

    # --- TO‘G‘RILANGAN QISM ---
    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_PATH = "/webhook"  # oddiy path nomi
    WEBHOOK_URL = f"https://eloquent-warmth.up.railway.app{WEBHOOK_PATH}"

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        path=WEBHOOK_PATH  # bu juda muhim!
    )


    if __name__ == '__main__':
        main()
