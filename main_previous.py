from fastapi import FastAPI, Query
from fastapi import Body
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import json
import random
import os
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz

from dotenv import load_dotenv
import google.generativeai as genai

# Chargement des variables d'environnement
load_dotenv()
print("🔐 GOOGLE_API_KEY =", os.getenv("GOOGLE_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "98987bce0d012f69f6c7a660be75c0b9"

with open("citations.json", "r", encoding="utf-8") as f:
    citations_data = json.load(f)


# -------- PROMPT GEMINI EXTERNE -------- #

class ScoreRequest(BaseModel):
    score_t: float
    score_p: float
    score_b: float
    score_pr: float
    score_h: float
    score_s: float
    score_w: float
    score_uv: float
    profil: str
    heure_locale: int



def generate_prompt_from_file(scores: dict, profil: str, niveau_ib: str, heure_locale: int, moment: str) -> str:
    with open("gemini_prompt.txt", "r", encoding="utf-8") as f:
        template = f.read()
    return template.format(
        score_t=scores['score_t'],
        score_p=scores['score_p'],
        score_b=scores['score_b'],
        score_pr=scores['score_pr'],
        score_h=scores['score_h'],
        score_s=scores['score_s'],
        score_w=scores['score_w'],
        score_uv=scores['score_uv'],
        profil=profil,
        niveau_ib=niveau_ib,
        heure_locale=heure_locale,
        moment=moment
    )

@app.post("/generate_summary")
def generate_summary(data: dict = Body(...)):
    scores = {
        'score_t': data.get('score_t'),
        'score_p': data.get('score_p'),
        'score_b': data.get('score_b'),
        'score_pr': data.get('score_pr'),
        'score_h': data.get('score_h'),
        'score_s': data.get('score_s'),
        'score_w': data.get('score_w'),
        'score_uv': data.get('score_uv'),
        'niveau_ib': data.get('niveau_ib', 'Favorable')
    }

    profil = data.get('profil', 'Standard')
    moment = data.get('moment', 'journée')

    lat = data.get('lat')
    lon = data.get('lon')

    print(f"📍 Coordonnées reçues : lat={lat}, lon={lon}")

    heure_locale = 12  # valeur de secours
    if lat is not None and lon is not None:
        try:
            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lat=lat, lng=lon)
            if timezone_str:
                tz = pytz.timezone(timezone_str)
                heure_locale = datetime.now(tz).hour
                print(f"🕒 Heure locale détectée : {heure_locale}h ({timezone_str})")
            else:
                print("⚠️ Fuseau horaire introuvable pour ces coordonnées.")
        except Exception as e:
            print(f"❌ Erreur lors du calcul de l'heure locale : {e}")

    prompt = generate_prompt_from_file(scores, profil, scores['niveau_ib'], heure_locale, moment)

    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash-latest")
    response = model.generate_content(prompt)

    return {"summary": response.text.strip()}



# Fonctions existantes pour récupérer et scorer les données

def get_pollution_data(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    response = requests.get(url)
    data = response.json()
    aqi = data['list'][0]['main']['aqi']
    pm25 = data['list'][0]['components']['pm2_5']
    return aqi, pm25

def get_weather_data(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()
    temp = data['main']['temp']
    humidity = data['main']['humidity']
    pressure = data['main']['pressure']
    cloud_cover = data['clouds']['all']
    wind_speed = data['wind']['speed'] * 3.6
    return temp, humidity, pressure, cloud_cover, wind_speed


def get_uv_data(lat, lon):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&appid={API_KEY}&exclude=minutely,hourly,daily,alerts&units=metric"
    response = requests.get(url)
    data = response.json()
    return data.get("current", {}).get("uvi", 0.0)



def score_sun(cloud_cover):
    return max(0, min(1, 1 - cloud_cover / 100))

def score_pollution(aqi):
    return 1 - (aqi - 1) / 4

def score_pressure(pressure):
    if 1013 <= pressure <= 1020:
        return 1
    elif pressure < 1013:
        return max(0, (pressure - 980) / 33)
    else:
        return max(0, (1040 - pressure) / 20)

def score_temp(temp):
    if 18 <= temp <= 24:
        return 1
    elif temp < 18:
        return max(0, (temp - 5) / 13)
    else:
        return max(0, (30 - temp) / 6)

def score_bruit(noise_level):
    return max(0, min(1, 1 - (noise_level / 10)))

def score_humidity(humidity):
    if 40 <= humidity <= 60:
        return 1
    elif humidity < 40:
        return max(0, (humidity - 20) / 20)
    else:
        return max(0, (80 - humidity) / 20)

def score_wind(wind_speed_kmh):
    if wind_speed_kmh < 5:
        return 0.5
    elif 5 <= wind_speed_kmh <= 20:
        return 1.0
    elif 20 < wind_speed_kmh <= 35:
        return 0.6
    else:
        return 0.3


def score_uv(uvi):
    if uvi == 0:
        return 0.0
    elif uvi <= 2:
        return 0.3
    elif 3 <= uvi <= 6:
        return 1.0
    elif 6 < uvi <= 8:
        return 0.6
    else:
        return 0.3


# Route de test
@app.get("/api/test")
def test_connection():
    return {"message": "Connexion réussie au backend 🎯"}

# Route IB principale (originale)
@app.get("/calculate_ib")
def calculate_ib(lat: float = Query(...), lon: float = Query(...), noise_level: int = Query(...), profile: str = Query(...)):
    profil_original = profile
    profile = profile.strip().lower()

    mapping = {
        "standard": "Standard",
        "standard asthmatique": "Standard asthmatique",
        "sportif": "Sportif",
        "sportif asthmatique": "Sportif asthmatique"
    }
    profile_clean = mapping.get(profile, "Standard")

    print("✅ Profil reçu :", profil_original)
    print("🛠️ Profil utilisé après normalisation :", profile_clean)

    aqi, pm25 = get_pollution_data(lat, lon)
    temp, humidity, pressure, cloud_cover, wind_speed = get_weather_data(lat, lon)
    uvi = get_uv_data(lat, lon)

    score_p = score_pollution(aqi)
    score_pr = score_pressure(pressure)
    score_t = score_temp(temp)
    score_b = score_bruit(noise_level)
    score_h = score_humidity(humidity)
    score_s = score_sun(cloud_cover)

    # Calcul de l'heure locale à partir de lat/lon
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lon)

    if timezone_str:
        tz = pytz.timezone(timezone_str)
        now_local_hour = datetime.now(tz).hour
        if now_local_hour < 6 or now_local_hour > 20:
            score_s = 0.0
            print("🌙 Nuit détectée dans la zone locale → score_s = 0.0")
    else:
        print("⚠️ Impossible de déterminer le fuseau horaire → score_s non modifié")


    score_w = score_wind(wind_speed)
    score_uv_ = score_uv(uvi)

    print(f"🌡️ Température = {temp:.2f}°C → score_t = {score_t:.2f}")
    print(f"🏭 Pollution AQI = {aqi} → score_p = {score_p:.2f}")
    print(f"🔊 Bruit = {noise_level} → score_b = {score_b:.2f}")
    print(f"🌬️ Vent = {wind_speed:.2f} km/h → score_w = {score_w:.2f}")
    print(f"☀️ UV = {uvi:.2f} → score_uv = {score_uv_:.2f}")

    IB = (
        0.25 * score_p +
        0.2 * score_t +
        0.1 * score_b +
        0.1 * score_h +
        0.1 * score_pr +
        0.1 * score_s +
        0.075 * score_w +
        0.075 * score_uv_
    )

    if "sportif" in profile:
        if score_t < 0.8:
            IB -= 0.15
            print("⚠️ Pénalité Sportif appliquée : -0.15")

    if "asthmatique" in profile:
        penalite_asthme = 0.20 * (1 - score_p)
        IB -= penalite_asthme
        print(f"⚠️ Pénalité Asthmatique appliquée : -{penalite_asthme:.2f}")

    print(f"✅ IB final (avant arrondi) = {IB:.3f}")

    if IB >= 0.79:
        level = "Excellent"
    elif IB >= 0.59:
        level = "Favorable"
    elif IB >= 0.39:
        level = "Modéré"
    else:
        level = "Défavorable"

    messages = {
        "Standard": {
            "Excellent": "L’environnement est idéal aujourd’hui.",
            "Favorable": "Les conditions sont bonnes, profitez-en.",
            "Modéré": "Soyez attentif à certaines conditions.",
            "Défavorable": "Prenez soin de vous, les conditions sont peu favorables."
        },
        "Standard asthmatique": {
            "Excellent": "Vous pouvez respirer librement aujourd’hui.",
            "Favorable": "L’air est acceptable pour les sensibles.",
            "Modéré": "Pensez à limiter les efforts prolongés.",
            "Défavorable": "Évitez les sorties prolongées si possible."
        },
        "Sportif": {
            "Excellent": "Conditions idéales pour l’exercice.",
            "Favorable": "C’est un bon jour pour bouger.",
            "Modéré": "Privilégiez des activités douces.",
            "Défavorable": "Préférez le repos ou l’intérieur aujourd’hui."
        },
        "Sportif asthmatique": {
            "Excellent": "Bouger en plein air est un plaisir aujourd’hui.",
            "Favorable": "Les conditions sont convenables pour un effort modéré.",
            "Modéré": "Soyez prudent si vous vous entraînez dehors.",
            "Défavorable": "Repos ou séance à l’intérieur conseillé."
        }
    }

    citation = random.choice(citations_data.get(profile_clean, [])) if profile_clean in citations_data else {"text": "Profitez de votre journée !", "author": "Inconnu"}
    final_message = messages.get(profile_clean, {}).get(level, 'Profitez de votre journée !') + f"\n\n Réflexion : \"{citation['text']}\" – {citation['author']}"

   
    return {
        "profil_utilisé": profile_clean,
        "IB": round(IB * 100),
        "scores": {
            "pollution": round(score_p, 2),
            "temp": round(score_t, 2),
            "pressure": round(score_pr, 2),
            "humidity": round(score_h, 2),
            "bruit": round(score_b, 2),
            "sun": round(score_s, 2),
            "wind": round(score_w, 2),
            "uv": round(score_uv_, 2)
        },
        "raw_values": {
            "pollution": aqi,
            "temp": temp,
            "pressure": pressure,
            "humidity": humidity,
            "bruit": noise_level,
            "sun": cloud_cover,
            "wind": wind_speed,
            "uv": uvi
        },
        "units": {
            "pollution": "AQI",
            "temp": "°C",
            "pressure": "hPa",
            "humidity": "%",
            "bruit": "dB",
            "sun": "%",
            "wind": "km/h",
            "uv": ""
        },
        "level": level,
        "message": final_message,
        "pm25": pm25,
        "temperature": temp,
        "humidity": humidity,
        "pressure": pressure,
        "wind_speed_kmh": wind_speed,
        "uvi": uvi,
        "heure_locale": now_local_hour

    }

@app.post("/generate_full_summary")
def generate_full_summary(lat: float, lon: float, noise_level: int, profile: str):
    ib_result = calculate_ib(lat=lat, lon=lon, noise_level=noise_level, profile=profile)

    scores = {
        'score_t': ib_result["scores"]["temp"],
        'score_p': ib_result["scores"]["pollution"],
        'score_b': ib_result["scores"]["bruit"],
        'score_pr': ib_result["scores"]["pressure"],
        'score_h': ib_result["scores"]["humidity"],
        'score_s': ib_result["scores"]["sun"],
        'score_w': ib_result["scores"]["wind"],
        'score_uv': ib_result["scores"]["uv"],
        'niveau_ib': ib_result["level"]
    }

    heure_locale = ib_result.get("heure_locale", 12)
    moment = (
        "matin" if 5 <= heure_locale < 12 else
        "après-midi" if 12 <= heure_locale < 17 else
        "soirée" if 17 <= heure_locale < 21 else
        "nuit"
    )

    prompt = generate_prompt_from_file(scores, ib_result["profil_utilisé"], ib_result["level"], heure_locale, moment)

    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash-latest")
    response = model.generate_content(prompt)

    return {
        "summary": response.text.strip(),
        "IB": ib_result["IB"],
        "niveau": ib_result["level"],
        "message": ib_result["message"],
        "heure_locale": heure_locale
    }


