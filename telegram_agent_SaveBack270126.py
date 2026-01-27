import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from dotenv import load_dotenv

# ===== CONFIG =====
load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1"
)

# ===== MENUS =====
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

# ===== IA =====
def appeler_asi(prompt):
    try:
        response = client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Siempre en español, estilo canario, artesanal, auténtico."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.9
        )
        texte = response.choices[0].message.content
        return texte.replace("pimiento", "pimienta")
    except Exception as e:
        return f"Error: {str(e)}"

async def analyser_photo(photo_path):
    """
    Retourne une description réaliste et cohérente pour Instagram,
    en se basant sur l'univers de Pimienta de Tenerife.
    """
    return (
        "Pimientas canarias cultivadas con dedicación en la Finca Gasconha, "
        "con colores intensos y formas auténticas. Cada fruto refleja "
        "la tradición artesanal de Tenerife y la riqueza natural de nuestras tierras."
    )


def limiter_caption(texte, longueur):
    if not texte:
        return ""

    limites = {
        "Court et direct": 400,
        "2 paragraphes max": 700,
        "Longue et détaillée": 900
    }

    max_len = limites.get(longueur, 700)

    if len(texte) <= max_len:
        return texte

    return texte[:max_len].rsplit(" ", 1)[0] + "…"


# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bienvenido al AGENT INSTAGRAM DE PIMIENTA DE TENERIFE 🇮🇨\nElige una opción:",
        reply_markup=MENU
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # MENU
    if text == "Generar Post":
        await update.message.reply_text("Elige el TON:", reply_markup=TONS_KEYBOARD)
        return

    if text in ["Energetique", "Fun", "Inspirant", "Pro", "Casual"]:
        context.user_data["ton"] = text
        await update.message.reply_text(
            "Elige la LONGITUD del texto:",
            reply_markup=LONGUEUR_KEYBOARD
        )
        return

    if text in ["Longue et détaillée", "2 paragraphes max", "Court et direct"]:
        context.user_data["longueur"] = text
        await update.message.reply_text(
            "Puedes enviar un texto, una foto, o ambos.\nLuego escribe «Generar»."
        )
        return

    # TEXTE UTILISATEUR
    if "longueur" in context.user_data and text.lower() not in ["generar", "regenerar", "salir"]:
        context.user_data["texte"] = text
        await update.message.reply_text("Texto recibido 👍")
        return

    if text.lower() == "generar":
        await generer_post(update, context)
        return

    if text == "Regenerar":
        await generer_post(update, context, regenerar=True)
        return

    if text == "Salir":
        context.user_data.clear()
        await update.message.reply_text("Menu principal 👇", reply_markup=MENU)
        return

    if text == "Ideas":
        await update.message.reply_text("🚧 Ideas – próximamente")
        return

    if text == "Trend":
        await update.message.reply_text("📈 Trends – próximamente")
        return

    if text == "Progression":
        await update.message.reply_text("📊 Progresión – próximamente")
        return

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    path = f"temp_{update.message.from_user.id}.jpg"
    await photo_file.download_to_drive(path)
    context.user_data["photo"] = path
    await update.message.reply_text("📸 Foto recibida. Escribe «Generar».")

async def generer_post(update: Update, context: ContextTypes.DEFAULT_TYPE, regenerar=False):
    ton = context.user_data.get('ton', 'Energetique')
    longueur = context.user_data.get('longueur', '2 paragraphes max')
    texte = context.user_data.get('texte', '')
    photo_path = context.user_data.get('photo', None)

    # 👉 Analyse réelle de la photo (fallback)
    description_photo = ""
    if photo_path:
        description_photo = await analyser_photo(photo_path)

    # Construction du prompt
    prompt = f"Genera una leyenda para Instagram en español. Estilo: {ton}. Longitud: {longueur}."
    if texte:
        prompt += f" Contexto adicional del usuario: {texte}."
    if description_photo:
        prompt += f" Descripción de la imagen: {description_photo}."
    prompt += " Siempre incluir #bio."

    # Appel ASI1
    texte_complet = appeler_asi(prompt)

    # Envoi du résultat sur Telegram
    if photo_path:
        # Pour texte long, on envoie en message séparé
        if longueur == "Longue et détaillée":
            await update.message.reply_photo(photo=open(photo_path, 'rb'))
            await update.message.reply_text(
                texte_complet,
                reply_markup=POST_ACTIONS_KEYBOARD
            )
        else:
            # Texte court ou 2 paragraphes max → en caption
            caption = limiter_caption(texte_complet, max_len=1000)
            await update.message.reply_photo(
                photo=open(photo_path, 'rb'),
                caption=caption,
                reply_markup=POST_ACTIONS_KEYBOARD
            )

        # Nettoyage
        try:
            os.remove(photo_path)
        except:
            pass
        context.user_data.pop('photo', None)
    else:
        # Pas de photo, texte seul
        await update.message.reply_text(
            texte_complet,
            reply_markup=POST_ACTIONS_KEYBOARD
        )




# ===== APP =====
app = ApplicationBuilder().token(API_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

print("🤖 Bot en ligne...")
app.run_polling()
