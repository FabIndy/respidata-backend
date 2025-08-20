from fastapi import FastAPI, Query
import requests
import json
import random


app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # autorise ton frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


API_KEY = "98987bce0d012f69f6c7a660be75c0b9"

with open("citations.json", "r", encoding="utf-8") as f:
    citations_data = json.load(f)

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
    cloud_cover = data['clouds']['all']  # 👈 pourcentage de couverture nuageuse
    return temp, humidity, pressure, cloud_cover

def score_sun(cloud_cover):
    """
    Score d’ensoleillement basé sur la couverture nuageuse (0–100 %)
    Plus il y a de nuages, plus le score baisse.
    """
    if cloud_cover is None:
        return 0
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

@app.get("/calculate_ib")
def calculate_ib(lat: float = Query(...), lon: float = Query(...), noise_level: int = Query(...), profile: str = Query(...)):
    aqi, pm25 = get_pollution_data(lat, lon)
    temp, humidity, pressure, cloud_cover = get_weather_data(lat, lon)

    score_p = score_pollution(aqi)
    score_pr = score_pressure(pressure)
    score_t = score_temp(temp)
    score_b = score_bruit(noise_level)
    score_h = score_humidity(humidity)
    score_s = score_sun(cloud_cover)


    IB = (0.35 * score_p) + (0.2 * score_t) + (0.1 * score_b) + (0.1 * score_h) + (0.15 * score_pr) + (0.1 * score_s)


    if "Sportif" in profile or "sportif" in profile:
        if score_t < 0.8:
            IB -= 0.15

    if "Asthmatique" in profile or "asthmatique" in profile:
        IB -= 0.20 * (1 - score_p)

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
            "Excellent": "💚 Conditions idéales pour booster votre sérotonine et garder le moral au beau fixe !",
            "Favorable": "💙 Bonnes conditions pour une activité modérée, sentez votre énergie monter en douceur.",
            "Modéré": "🔵 Les conditions sont moyennes, mais une activité légère peut vous aider à relâcher la pression.",
            "Défavorable": "⚠️ Conditions difficiles, privilégiez le repos et laissez votre corps se régénérer."
        },
        "Sportif": {
            "Excellent": "💪 Conditions parfaites pour un entraînement intense, boostez votre sérotonine en plein air !",
            "Favorable": "💙 Bonnes conditions pour une activité modérée, sentez votre énergie monter en douceur.",
            "Modéré": "🟡 Réduisez l'intensité de votre entraînement, les conditions sont moyennes.",
            "Défavorable": "⚠️ Conditions défavorables, privilégiez la récupération aujourd'hui."
        },
        "Asthmatique": {
            "Excellent": "💚 Air pur et stable, profitez de ce moment pour respirer en toute sérénité.",
            "Favorable": "💙 Les conditions sont favorables, une courte sortie vous apportera calme et équilibre.",
            "Modéré": "🔵 Les conditions sont moyennes, soyez attentif à votre respiration.",
            "Défavorable": "⚠️ L'air est chargé, restez à l'intérieur et préservez votre souffle."
        },
        "Sportif asthmatique": {
            "Excellent": "💪💚 Conditions optimales pour bouger tout en préservant votre souffle et votre sérénité.",
            "Favorable": "💙 Une activité douce renforcera votre bien-être sans stresser votre souffle.",
            "Modéré": "🔵 Bougez légèrement, mais soyez vigilant à votre rythme.",
            "Défavorable": "⚠️ Conditions défavorables pour l'activité physique, restez au calme."
        }
    }

    citation = random.choice(citations_data.get(profile, [])) if profile in citations_data else {"text": "Profitez de votre journée !", "author": "Inconnu"}
    final_message = messages.get(profile, {}).get(level, 'Profitez de votre journée !') + f"\n\n Réflexion : \"{citation['text']}\" – {citation['author']}"

    return {
        "IB": round(IB * 100),
        "scores": {
            "pollution": round(score_p, 2),
            "temp": round(score_t, 2),
            "pressure": round(score_pr, 2),
            "humidity": round(score_h, 2),
            "bruit": round(score_b, 2),
            "sun": round(score_s, 2)

        },
        "level": level,
        "message": final_message,
        "pm25": pm25,
        "temperature": temp,
        "humidity": humidity,
        "pressure": pressure
    }
@app.get("/api/test")
def test_connection():
    return {"message": "Connexion réussie au backend 🎯"}
