import requests

url = "http://localhost:8000/generate_summary"
data = {
    "score_t": 0.8,
    "score_p": 0.7,
    "score_b": 0.6,
    "score_pr": 1.0,
    "score_h": 0.5,
    "score_s": 0.9,
    "score_w": 0.7,
    "score_uv": 0.4,
    "profil": "Sportif"
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.json())
