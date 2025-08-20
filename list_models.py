import google.generativeai as genai

# Remplace ici par ta vraie clé ou récupère-la depuis ton .env
genai.configure(api_key="AIzaSyDxsnrBuL_xNL6TX6mztWe-wDaB9e4y8xA")

models = genai.list_models()
for m in models:
    print(f"✅ {m.name} – {m.supported_generation_methods}")
