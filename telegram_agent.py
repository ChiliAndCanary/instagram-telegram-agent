import os
import json
import asyncio
import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from openai import OpenAI
from dotenv import load_dotenv

# ---------- CONFIG ----------
load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client_asi = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1"
)

# OpenRouter pour la vision (Gemini Flash — gratuit)
client_vision = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
    base_url="https://openrouter.ai/api/v1"
)

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- DOSSIERS ----------
Path("clients").mkdir(exist_ok=True)
Path("historique").mkdir(exist_ok=True)
Path("temp_photos").mkdir(exist_ok=True)

# ---------- SYSTEM PROMPTS ----------
SYSTEM_POST = (
    "Siempre responde en español. "
    "Eres un creador de contenido profesional para redes sociales y blogs. "
    "Escribes textos listos para publicar. "
    "Estilo canario, artesanal, auténtico, humano. "
    "Proyecto: Pimienta de Tenerife (Icod de los Vinos, Tenerife). "
    "Productos: pimientas canarias, salsas picantes, mojo, especias, sal con pimienta. "
    "Venta en mercadillos y online. "
    "Máximo 5 hashtags. Usa siempre #bio."
)

SYSTEM_IDEAS = (
    "Siempre responde en español. "
    "Eres un consultor creativo en marketing digital. "
    "NO escribes textos finales para publicar. "
    "Propones ideas de contenido claras, útiles y accionables. "
    "Para cada idea explica: concepto, objetivo y formato recomendado. "
    "Tono de asesor, no publicitario."
)

SYSTEM_TREND = (
    "Siempre responde en español. "
    "Eres un analista de tendencias de Instagram y branding gastronómico. "
    "Explicas por qué una tendencia funciona. "
    "Das recomendaciones estratégicas adaptadas a Pimienta de Tenerife. "
    "Tono experto, pedagógico y concreto."
)

SYSTEM_PROGRESS = (
    "Siempre responde en español. "
    "Eres un coach en crecimiento de cuentas Instagram. "
    "Das consejos estructurados paso a paso. "
    "Enfocado en constancia, engagement, storytelling y comunidad."
)

# ---------- MENUS ----------
MENU = ReplyKeyboardMarkup(
    [["Generar Post", "Ideas", "Trend"],
     ["Progression", "WordPress Article", "Mi Perfil"],
     ["Planificar Recordatorio", "Salir"]],
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

# ---------- GESTION CLIENTS ----------
def get_client_path(user_id: int) -> str:
    return f"clients/{user_id}.json"

def load_client(user_id: int) -> dict:
    path = get_client_path(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "user_id": user_id,
        "nom": "",
        "marque": "Pimienta de Tenerife",
        "produits": "pimientas canarias, salsas, mojo, especias",
        "ton_prefere": "Inspirant",
        "posts_generes": 0,
        "date_inscription": datetime.now().isoformat(),
        "rappels": []
    }

def save_client(user_id: int, data: dict):
    path = get_client_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- HISTORIQUE ----------
def save_historique(user_id: int, type_contenu: str, contenu: str):
    path = f"historique/{user_id}.json"
    historique = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            historique = json.load(f)
    historique.append({
        "date": datetime.now().isoformat(),
        "type": type_contenu,
        "contenu": contenu[:500]  # Tronqué pour le stockage
    })
    historique = historique[-50:]  # Garder les 50 derniers
    with open(path, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)

# ---------- UTILS ----------
def appeler_asi(prompt: str, system_prompt: str) -> str:
    response = client_asi.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.9,
        max_tokens=1800
    )
    texte = response.choices[0].message.content
    return texte.replace("el pimiento", "la pimienta")


def _build_vision_messages(image_path: str, contexte_marque: str) -> list:
    """Construit le payload vision standard (compatible ASI1 et OpenRouter)."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    ext = image_path.split(".")[-1].lower()
    media_type = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
    prompt = (
        f"Analiza esta imagen para una marca artesanal canaria: {contexte_marque}. "
        "Describe en 3-4 frases: qué se ve, colores, ambiente, "
        "emociones que transmite y cómo conecta con los valores artesanales. "
        "Responde en español."
    )
    return [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}},
            {"type": "text", "text": prompt}
        ]
    }]


def analyser_photo_vision(image_path: str, contexte_marque: str) -> str:
    """
    Analyse photo avec fallback automatique :
    1. Tentative ASI1-mini (vision intégrée)
    2. Fallback OpenRouter Gemini Flash (gratuit)
    """
    messages = _build_vision_messages(image_path, contexte_marque)

    # Tentative 1 — ASI1
    try:
        response = client_asi.chat.completions.create(
            model="asi1-mini",
            messages=messages,
            max_tokens=400,
            temperature=0.7
        )
        result = response.choices[0].message.content
        if result and len(result) > 20:
            logger.info("Vision: ASI1 OK")
            return result
        raise ValueError("Réponse ASI1 trop courte ou vide")
    except Exception as e:
        logger.warning(f"Vision ASI1 échoué ({e}), fallback OpenRouter...")

    # Tentative 2 — OpenRouter Gemini Flash (gratuit)
    try:
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY manquante")
        response = client_vision.chat.completions.create(
            model="google/gemini-flash-1.5",
            messages=messages,
            max_tokens=400,
            extra_headers={
                "HTTP-Referer": "https://pimienta-bot.railway.app",
                "X-Title": "Pimienta de Tenerife Bot"
            }
        )
        result = response.choices[0].message.content
        logger.info("Vision: OpenRouter Gemini Flash OK")
        return result
    except Exception as e:
        logger.error(f"Vision OpenRouter échoué ({e})")

    # Fallback final — description générique
    return (
        "Producto artesanal canario de calidad, "
        "elaborado con ingredientes naturales de Tenerife. "
        "Transmite autenticidad y conexión con la tierra."
    )


def limiter_hashtags(texte: str, max_hashtags: int = 5) -> str:
    mots = texte.split()
    hashtags = [m for m in mots if m.startswith("#")]
    if len(hashtags) <= max_hashtags:
        return texte
    texte_sans = " ".join(m for m in mots if not m.startswith("#"))
    return texte_sans.strip() + "\n" + " ".join(hashtags[:max_hashtags])


def limiter_caption(texte: str, longueur: str) -> str:
    limites = {
        "Longue et détaillée": 1800,
        "2 paragraphes max": 1000,
        "Court et direct": 450
    }
    max_len = limites.get(longueur, 1000)
    if len(texte) <= max_len:
        return texte
    return texte[:max_len].rsplit(" ", 1)[0] + "…"


def cleanup_photo(path: str):
    """Supprime la photo temporaire après usage."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"Impossible de supprimer {path}: {e}")

# ---------- PLANIFICATEUR ----------
async def envoyer_rappel(context: ContextTypes.DEFAULT_TYPE):
    """Job exécuté par le scheduler Telegram."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    message = job_data["message"]
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Rappel planifié :\n\n{message}"
        )
        # Supprimer le rappel de la liste client
        client = load_client(user_id)
        client["rappels"] = [
            r for r in client.get("rappels", [])
            if r.get("id") != job_data.get("rappel_id")
        ]
        save_client(user_id, client)
    except Exception as e:
        logger.error(f"Erreur envoi rappel: {e}")

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    context.user_data.clear()

    # Créer ou charger le profil client
    client = load_client(user_id)
    if not client["nom"]:
        client["nom"] = update.message.from_user.first_name or "Cliente"
        save_client(user_id, client)

    await update.message.reply_text(
        f"🌶️ AGENT INSTAGRAM – PIMIENTA DE TENERIFE\n"
        f"Hola {client['nom']}! Elige una opción:",
        reply_markup=MENU
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # ---------- MENU PRINCIPAL ----------
    if text == "Generar Post":
        context.user_data.clear()
        context.user_data["mode"] = "instagram_post"
        await update.message.reply_text("Elige el TON:", reply_markup=TONS_KEYBOARD)
        return

    if text == "WordPress Article":
        context.user_data.clear()
        context.user_data["mode"] = "wordpress_article"
        await update.message.reply_text(
            "Vamos a generar un artículo WordPress.\nElige el TON:",
            reply_markup=TONS_KEYBOARD
        )
        return

    if text == "Ideas":
        await update.message.reply_text("🔄 Generando ideas...")
        try:
            prompt = (
                "Propón 5 ideas de contenido para Instagram "
                "adaptadas a una marca artesanal canaria de pimientas."
            )
            reponse = await asyncio.to_thread(appeler_asi, prompt, SYSTEM_IDEAS)
            save_historique(user_id, "ideas", reponse)
            await update.message.reply_text(reponse, reply_markup=MENU)
        except Exception as e:
            logger.error(f"Error Ideas: {e}")
            await update.message.reply_text("⚠️ Error al generar. Inténtalo de nuevo.", reply_markup=MENU)
        return

    if text == "Trend":
        await update.message.reply_text("🔄 Analizando tendencias...")
        try:
            prompt = (
                "Explica 3 tendencias actuales de Instagram "
                "relacionadas con food artesanal y producto local, "
                "y cómo aprovecharlas."
            )
            reponse = await asyncio.to_thread(appeler_asi, prompt, SYSTEM_TREND)
            save_historique(user_id, "trend", reponse)
            await update.message.reply_text(reponse, reply_markup=MENU)
        except Exception as e:
            logger.error(f"Error Trend: {e}")
            await update.message.reply_text("⚠️ Error al generar. Inténtalo de nuevo.", reply_markup=MENU)
        return

    if text == "Progression":
        await update.message.reply_text("🔄 Preparando tu plan...")
        try:
            prompt = (
                "Da un plan claro para mejorar progresivamente "
                "una cuenta Instagram de productos artesanales."
            )
            reponse = await asyncio.to_thread(appeler_asi, prompt, SYSTEM_PROGRESS)
            save_historique(user_id, "progression", reponse)
            await update.message.reply_text(reponse, reply_markup=MENU)
        except Exception as e:
            logger.error(f"Error Progression: {e}")
            await update.message.reply_text("⚠️ Error al generar. Inténtalo de nuevo.", reply_markup=MENU)
        return

    if text == "Mi Perfil":
        client = load_client(user_id)
        nb_rappels = len(client.get("rappels", []))
        profil_txt = (
            f"👤 TU PERFIL\n"
            f"Nombre: {client['nom']}\n"
            f"Marca: {client['marque']}\n"
            f"Productos: {client['produits']}\n"
            f"Tono preferido: {client['ton_prefere']}\n"
            f"Posts generados: {client['posts_generes']}\n"
            f"Recordatorios activos: {nb_rappels}\n"
            f"Miembro desde: {client['date_inscription'][:10]}"
        )
        await update.message.reply_text(profil_txt, reply_markup=MENU)
        return

    if text == "Planificar Recordatorio":
        context.user_data["mode"] = "planificador"
        await update.message.reply_text(
            "⏰ PLANIFICADOR\n"
            "Escribe el mensaje del recordatorio y cuándo enviarlo.\n"
            "Formato: MENSAJE | DD/MM/YYYY HH:MM\n"
            "Ejemplo: Publicar foto del mercadillo | 15/03/2025 09:00"
        )
        return

    if text == "Salir":
        context.user_data.clear()
        await update.message.reply_text("Volvemos al menú. 🌶️", reply_markup=MENU)
        return

    # ---------- PLANIFICADOR ----------
    if context.user_data.get("mode") == "planificador":
        if "|" in text:
            try:
                parts = text.split("|")
                message_rappel = parts[0].strip()
                date_str = parts[1].strip()
                date_rappel = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
                delai = (date_rappel - datetime.now()).total_seconds()

                if delai <= 0:
                    await update.message.reply_text(
                        "⚠️ La fecha debe ser en el futuro.", reply_markup=MENU
                    )
                    return

                import uuid
                rappel_id = str(uuid.uuid4())[:8]

                context.job_queue.run_once(
                    envoyer_rappel,
                    when=delai,
                    data={
                        "user_id": user_id,
                        "message": message_rappel,
                        "rappel_id": rappel_id
                    }
                )

                # Sauvegarder dans le profil client
                client = load_client(user_id)
                client.setdefault("rappels", []).append({
                    "id": rappel_id,
                    "message": message_rappel,
                    "date": date_rappel.isoformat()
                })
                save_client(user_id, client)

                await update.message.reply_text(
                    f"✅ Recordatorio guardado!\n"
                    f"📅 {date_str}\n"
                    f"💬 {message_rappel}",
                    reply_markup=MENU
                )
            except ValueError:
                await update.message.reply_text(
                    "⚠️ Formato incorrecto. Usa: MENSAJE | DD/MM/YYYY HH:MM",
                    reply_markup=MENU
                )
            context.user_data["mode"] = None
        return

    # ---------- TON ----------
    if text in ["Energetique", "Fun", "Inspirant", "Pro", "Casual"]:
        context.user_data["ton"] = text
        # Sauvegarder le ton préféré
        client = load_client(user_id)
        client["ton_prefere"] = text
        save_client(user_id, client)

        if context.user_data.get("mode") == "instagram_post":
            await update.message.reply_text(
                "Elige la LONGITUD:", reply_markup=LONGUEUR_KEYBOARD
            )
        else:
            await update.message.reply_text("Envía el prompt del artículo WordPress.")
        return

    # ---------- LONGUEUR ----------
    if text in ["Longue et détaillée", "2 paragraphes max", "Court et direct"]:
        context.user_data["longueur"] = text
        await update.message.reply_text(
            "Envía texto y/o una foto.\nLuego escribe Generar."
        )
        return

    # ---------- TEXTE UTILISATEUR ----------
    if text.lower() not in ["generar", "regenerar"]:
        context.user_data["texte"] = text
        await update.message.reply_text("Texto guardado. Escribe Generar.")
        return

    # ---------- GENERAR / REGENERAR ----------
    if text.lower() in ["generar", "regenerar"]:
        if context.user_data.get("mode") == "wordpress_article":
            await generer_article_wordpress(update, context)
        else:
            await generer_post(update, context)
        return


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    user_id = update.message.from_user.id
    path = f"temp_photos/{user_id}.jpg"
    await photo.download_to_drive(path)
    context.user_data["photo"] = path
    await update.message.reply_text("📸 Foto recibida. Escribe Generar.")


# ---------- POST INSTAGRAM ----------
async def generer_post(update, context):
    user_id = update.message.from_user.id
    ton = context.user_data.get("ton", "Inspirant")
    longueur = context.user_data.get("longueur", "2 paragraphes max")
    texte = context.user_data.get("texte", "")
    photo_path = context.user_data.get("photo")
    client_data = load_client(user_id)

    await update.message.reply_text("🔄 Generando tu post...")

    try:
        description_photo = ""
        if photo_path and os.path.exists(photo_path):
            try:
                await update.message.reply_text("🖼️ Analizando la foto con IA...")
                contexte_marque = f"{client_data['marque']} - {client_data['produits']}"
                description_photo = await asyncio.to_thread(
                    analyser_photo_vision, photo_path, contexte_marque
                )
            except Exception as e:
                logger.error(f"Error análisis foto: {e}")
                description_photo = "Producto artesanal canario, relación con la tierra."

        prompt = (
            f"Genera una leyenda de Instagram.\n"
            f"Marca: {client_data['marque']}\n"
            f"Productos: {client_data['produits']}\n"
            f"Tono: {ton}\n"
            f"Longitud: {longueur}\n"
        )
        if texte:
            prompt += f"Contexto: {texte}\n"
        if description_photo:
            prompt += f"Descripción de la imagen: {description_photo}\n"

        texte_complet = await asyncio.to_thread(appeler_asi, prompt, SYSTEM_POST)
        texte_complet = limiter_hashtags(texte_complet, 5)
        reponse = limiter_caption(texte_complet, longueur)

        # Stats client
        client_data["posts_generes"] += 1
        save_client(user_id, client_data)
        save_historique(user_id, "instagram_post", reponse)

        # Nettoyage photo
        if photo_path:
            cleanup_photo(photo_path)
            context.user_data["photo"] = None

        await update.message.reply_text(reponse, reply_markup=POST_ACTIONS_KEYBOARD)

    except Exception as e:
        logger.error(f"Error generar_post: {e}")
        await update.message.reply_text(
            "⚠️ Error al generar el post. Inténtalo de nuevo.",
            reply_markup=MENU
        )


# ---------- ARTICLE WORDPRESS ----------
async def generer_article_wordpress(update, context):
    user_id = update.message.from_user.id
    sujet = context.user_data.get("texte", "Tema por definir")
    ton = context.user_data.get("ton", "Pro")

    await update.message.reply_text("🔄 Generando artículo WordPress...")

    try:
        prompt = (
            f"Genera un artículo WordPress en español. "
            f"Tono: {ton}. "
            f"Tema: {sujet}. "
            "Divide el contenido en 4 capítulos. "
            "Cada capítulo debe tener título y párrafo. "
            "Al final: palabras clave separadas por comas y una frase SEO opcional. "
            "Responde de forma natural y humana."
        )

        reponse = await asyncio.to_thread(appeler_asi, prompt, SYSTEM_POST)
        save_historique(user_id, "wordpress", reponse)

        parts = reponse.split("Capítulo")
        parts = [p.strip() for p in parts if p.strip()]

        async def send_long(text, last=False):
            while text:
                chunk = text[:4000]
                if len(text) > 4000:
                    chunk = chunk.rsplit(" ", 1)[0]
                text = text[len(chunk):].lstrip()
                await update.message.reply_text(
                    chunk,
                    reply_markup=POST_ACTIONS_KEYBOARD if last else None
                )
                last = False

        for i, part in enumerate(parts):
            await send_long(part, last=(i == len(parts) - 1))

    except Exception as e:
        logger.error(f"Error generar_article: {e}")
        await update.message.reply_text(
            "⚠️ Error al generar el artículo. Inténtalo de nuevo.",
            reply_markup=MENU
        )


# ---------- APP ----------
app = ApplicationBuilder().token(API_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("🤖 Bot en ligne – H24 sur Railway")
app.run_polling()
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
