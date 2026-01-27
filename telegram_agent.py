import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from dotenv import load_dotenv

# ---------- CONFIG ----------
load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1"
)

# ---------- MENUS ----------
MENU = ReplyKeyboardMarkup(
    [["Generar Post", "Ideas", "Trend", "Progression", "Salir"]],
    resize_keyboard=True
)

TONS_KEYBOARD = ReplyKeyboardMarkup(
    [["Energetique", "Fun", "Inspirant"],
     ["Pro", "Casual"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

LONGUEUR_KEYBOARD = ReplyKeyboardMarkup(
    [["Longue et détaillée", "2 paragraphes max", "Court et direct"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

POST_ACTIONS_KEYBOARD = ReplyKeyboardMarkup(
    [["Regenerar", "Salir"]],
    resize_keyboard=True
)

# ---------- UTILS ----------
def appeler_asi(prompt):
    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Siempre responde en español. "
                    "Estilo canario, artesanal, auténtico, humano. "
                    "Máximo 5 hashtags. "
                    "Usa siempre #bio."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.9,
        max_tokens=1800
    )

    texte = response.choices[0].message.content
    return texte.replace("pimiento", "pimienta")


def limiter_hashtags(texte, max_hashtags=5):
    mots = texte.split()
    hashtags = [m for m in mots if m.startswith("#")]

    if len(hashtags) <= max_hashtags:
        return texte

    texte_sans = " ".join(m for m in mots if not m.startswith("#"))
    return texte_sans.strip() + "\n" + " ".join(hashtags[:max_hashtags])


def limiter_caption(texte, longueur):
    limites = {
        "Longue et détaillée": 1800,
        "2 paragraphes max": 1000,
        "Court et direct": 450
    }

    max_len = limites.get(longueur, 1000)

    if len(texte) <= max_len:
        return texte

    return texte[:max_len].rsplit(" ", 1)[0] + "…"


async def analyser_photo(_path):
    # Fallback cohérent avec ta marque
    return (
        "Producto artesanal canario, "
        "relación directa con la tierra, el sol y el trabajo manual."
    )

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🌶️ AGENT INSTAGRAM CANARIEN\nElige una opción:",
        reply_markup=MENU
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Generar Post":
        await update.message.reply_text("Elige el TON:", reply_markup=TONS_KEYBOARD)
        return

    if text in ["Energetique", "Fun", "Inspirant", "Pro", "Casual"]:
        context.user_data["ton"] = text
        await update.message.reply_text("Elige la LONGITUD:", reply_markup=LONGUEUR_KEYBOARD)
        return

    if text in ["Longue et détaillée", "2 paragraphes max", "Court et direct"]:
        context.user_data["longueur"] = text
        await update.message.reply_text(
            "Puedes enviar texto y/o una foto.\nLuego escribe **Generar**."
        )
        return

    if "longueur" in context.user_data and text.lower() not in ["generar", "regenerar", "salir"]:
        context.user_data["texte"] = text
        await update.message.reply_text("Texto guardado. Puedes añadir una foto o escribir Generar.")
        return

    if text.lower() == "generar":
        await generer_post(update, context)
        return

    if text == "Regenerar":
        await generer_post(update, context)
        return

    if text == "Salir":
        context.user_data.clear()
        await update.message.reply_text("Volvemos al menú.", reply_markup=MENU)
        return

    if text == "Ideas":
        await update.message.reply_text("Función Ideas (próximamente).")
        return

    if text == "Trend":
        await update.message.reply_text("Función Trend (próximamente).")
        return

    if text == "Progression":
        await update.message.reply_text("Función Progression (próximamente).")
        return


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    path = f"temp_{update.message.from_user.id}.jpg"
    await photo.download_to_drive(path)

    context.user_data["photo"] = path
    await update.message.reply_text("📸 Foto recibida. Escribe Generar.")


async def generer_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ton = context.user_data.get("ton", "Inspirant")
    longueur = context.user_data.get("longueur", "2 paragraphes max")
    texte = context.user_data.get("texte", "")
    photo_path = context.user_data.get("photo")

    description_photo = ""
    if photo_path:
        description_photo = await analyser_photo(photo_path)

    prompt = (
        f"Genera una leyenda de Instagram.\n"
        f"Tono: {ton}\n"
        f"Longitud: {longueur}\n"
    )

    if texte:
        prompt += f"Contexto del usuario: {texte}\n"

    if description_photo:
        prompt += f"Imagen: {description_photo}\n"

    texte_complet = appeler_asi(prompt)
    texte_complet = limiter_hashtags(texte_complet, 5)
    reponse = limiter_caption(texte_complet, longueur)

    if photo_path:
        await update.message.reply_photo(
            photo=open(photo_path, "rb"),
            caption=reponse,
            reply_markup=POST_ACTIONS_KEYBOARD
        )
        try:
            os.remove(photo_path)
        except:
            pass
        context.user_data.pop("photo", None)
    else:
        await update.message.reply_text(reponse, reply_markup=POST_ACTIONS_KEYBOARD)

# ---------- APP ----------
app = ApplicationBuilder().token(API_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("🤖 Bot en ligne")
app.run_polling()
