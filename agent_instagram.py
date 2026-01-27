# -*- coding: utf-8 -*-
"""
AGENT INSTAGRAM INTERACTIF avec ASI1
Version propre sans emojis pour Windows
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration du client ASI1
client = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1"
)

# Persona de l'agent
AGENT_PERSONA = """
Tu es un artisan passionné de l'île de Tenerife, défenseur de la biodiversité locale
et de l'héritage canarien.

REGLES ABSOLUES:
- Tu reponds TOUJOURS en espagnol, meme si la question est en francais
- Style naturel, authentique, artisanal
- Ton chaleureux, humain, passionne
- Toujours utiliser 'pimienta' pour parler des piments
- Ne jamais utiliser le mot 'pimiento'
- Toujours inclure le hashtag #bio dans les captions Instagram

CONTEXTE:
Tu crees du contenu Instagram pour une marque artisanale canarienne.
"""

# Compteur et budget
posts_crees = 0
objectif_posts = 40
BUDGET_PAR_POST = 0.001
coût_total = 0.0

# Fonctions de base
def afficher_compteur():
    print("\n=== COMPTEUR DE POSTS INSTAGRAM ===")
    print(f"Objectif: {objectif_posts} posts")
    print(f"Créés: {posts_crees} posts")
    restants = objectif_posts - posts_crees
    print(f"Restants: {restants} posts")
    print(f"Progression: {(posts_crees/objectif_posts)*100:.1f}%")
    print("="*40)

def ajouter_post():
    global posts_crees
    posts_crees += 1

def verifier_objectif_atteint():
    return posts_crees >= objectif_posts

# Fonction pour appeler ASI1
def appeler_asi1(message_utilisateur):
    try:
        response = client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {"role": "system", "content": AGENT_PERSONA},
                {"role": "user", "content": message_utilisateur}
            ],
            max_tokens=2000,
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur: {str(e)}"

# Générer une légende
def generer_legende():
    sujet = input("De quoi parle ton post?: ").strip()
    if not sujet:
        print("Pas de sujet, impossible de générer la légende")
        return

    ton_choix = input("Ton ton (1-5: 1=Energetique, 2=Fun, 3=Inspirant, 4=Pro, 5=Casual): ").strip()
    tons = {
        "1": "energetic and motivating",
        "2": "funny and humorous",
        "3": "inspiring and elegant",
        "4": "professional and educational",
        "5": "casual and relaxed"
    }
    ton = tons.get(ton_choix, "energetic and motivating")

    try:
        nb_hashtags = int(input("Nombre de hashtags (3-30): ").strip())
    except:
        nb_hashtags = 5
    nb_hashtags = min(max(nb_hashtags, 3), 30)

    type_post = input("Type de post (1=Photo, 2=Reel, 3=Carrousel, 4=Story): ").strip()
    types = {"1": "photo", "2": "reel", "3": "carousel", "4": "story"}
    type_choisi = types.get(type_post, "photo")

    prompt = f"""
Responde exclusivamente en espanol.

Genera una leyenda de Instagram para:
Tema: {sujet}
Tono: {ton}
Tipo de post: {type_choisi}
Numero de hashtags: {nb_hashtags}

Reglas:
- Usar siempre 'pimienta'
- Incluir #bio
"""

    print("Génération de la légende...")
    reponse = appeler_asi1(prompt)
    
    # Correction post-traitement
    reponse = reponse.replace("pimiento", "pimienta")

    print("\n=== LÉGENDE GÉNÉRÉE ===")
    print(reponse)
    print("="*40)

    global posts_crees, coût_total
    ajouter_post()
    coût_total += BUDGET_PAR_POST

# Suggérer des idées
def suggerer_idees():
    niche = input("Quelle est ta niche? ").strip()
    audience = input("À qui s'adresse le contenu? ").strip() or "audience générale"
    format_choix = input("Format préféré (photo/reel/carousel): ").strip().lower()
    formats = {"photo": "photo", "reel": "video", "carousel": "carousel"}
    format_choisi = formats.get(format_choix, "photo")

    prompt = f"""
Génère 10 idées de posts Instagram pour la niche: {niche}, audience: {audience}, format: {format_choisi}.
Toujours utiliser 'pimienta' pour piments et inclure le hashtag #bio.
"""
    print("Génération des idées...")
    reponse = appeler_asi1(prompt)
    print("\n=== IDÉES DE POSTS ===")
    print(reponse)
    print("="*40)

# Créer stratégie mensuelle
def creer_strategie_mensuelle():
    niche = input("Quelle est ta niche? ").strip()
    objectif = input("Objectif principal: ").strip() or "croissance générale"
    try:
        posts_par_semaine = int(input("Combien de posts par semaine?: ").strip())
    except:
        posts_par_semaine = 3

    prompt = f"""
Crée une stratégie mensuelle Instagram pour la niche {niche}, objectif: {objectif}, {posts_par_semaine} posts par semaine.
Toujours utiliser 'pimienta' pour piments et inclure le hashtag #bio.
"""
    print("Génération de la stratégie...")
    reponse = appeler_asi1(prompt)
    print("\n=== STRATÉGIE MENSUELLE ===")
    print(reponse)
    print("="*40)

# Analyser un trend
def analyser_trend():
    niche = input("Dans quelle niche? ").strip()
    trend = input("Quel trend analyser? ").strip()
    if not trend:
        print("Pas de trend spécifié")
        return

    prompt = f"""
Analyse le trend '{trend}' dans la niche '{niche}'.
Toujours utiliser 'pimienta' pour piments et inclure le hashtag #bio.
"""
    print("Analyse du trend...")
    reponse = appeler_asi1(prompt)
    print("\n=== ANALYSE DU TREND ===")
    print(reponse)
    print("="*40)

# Menu principal
def menu_principal():
    while True:
        print("\nAGENT INSTAGRAM CANARIEN")
        print("1. Générer une légende Instagram")
        print("2. Générer des idées de posts")
        print("3. Créer une stratégie mensuelle")
        print("4. Analyser un trend")
        print("5. Voir la progression")
        print("6. Quitter")
        choix = input("Ton choix (1-6): ").strip()
        
        if choix == "1":
            generer_legende()
        elif choix == "2":
            suggerer_idees()
        elif choix == "3":
            creer_strategie_mensuelle()
        elif choix == "4":
            analyser_trend()
        elif choix == "5":
            afficher_compteur()
        elif choix == "6":
            print("Au revoir")
            break
        else:
            print("Choix invalide, réessaie.")

if __name__ == "__main__":
    menu_principal()
