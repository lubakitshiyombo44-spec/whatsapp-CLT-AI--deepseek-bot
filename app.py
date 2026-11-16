import os, re, time, hashlib, hmac, requests, sqlite3, datetime
from flask import Flask, request, render_template_string
from io import BytesIO
from PIL import Image
import pytesseract

app = Flask(__name__)

# ============ CONFIG ============
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "chris123")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chris2026")

DB_FILE = "chris_logs.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, numero TEXT, nom TEXT, type TEXT, question TEXT, reponse TEXT
    )""")
    conn.commit(); conn.close()

def save_log(numero, nom, type_msg, question, reponse):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT INTO logs (date, numero, nom, type, question, reponse) VALUES (?,?,?,?,?,?)",
            (datetime.datetime.now().strftime("%d/%m %H:%M"), numero, nom, type_msg, question[:1000], reponse[:2000]))
        conn.commit(); conn.close()
    except Exception as e:
        print("Log erreur:", e)

init_db()

# ============ SECURITE ============
user_last = {}
BANNED = ["pirater","hack","mot de passe facebook","porno","sexe","tuer","bombe","drogue","arnaque"]

def verify_sig(raw, sig):
    if not APP_SECRET or not sig: return True
    exp = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(exp, sig)

def rate_limited(phone):
    now = time.time()
    msgs = [t for t in user_last.get(phone, []) if now-t < 60]
    if len(msgs) >= 10: return True
    msgs.append(now); user_last[phone]=msgs
    return False

def is_forbidden(t): return any(w in t.lower() for w in BANNED)

# ============ CERVEAU CLT AI - IDENTITE 100% CONGOLAISE ============
SYSTEM = """Tu es CLT AI, une intelligence artificielle 100% CONGOLAISE.
- Tu t'appelles CLT AI. Jamais DeepSeek, jamais ChatGPT, jamais Meta AI, jamais autre chose.
- Tu as été développé par un jeune ingénieur congolais. C'est tout ce que tu dis sur ton créateur. Tu ne donnes jamais son vrai nom, son âge, son numéro.
- Tu parles français simple, comme un frère congolais, poli, sympa, clair.
- Si on te demande qui tu es : "Je suis CLT AI, une intelligence artificielle 100% congolaise, développée par un jeune ingénieur congolais."
- Si on te demande ton créateur : "J'ai été développé par un jeune ingénieur congolais."
- Tu refuses poliment tout ce qui est illégal, sexuel, violent, piratage.
- Exercice / équation / maths / physique : tu expliques étape par étape puis réponse finale, comme un bon prof.
- Tu es clair, court, comme un bon prof.
"""

# --- ESPION 1 : GROQ ---
def ask_clt(prompt, user_name):
    full_prompt = f"Le nom de l'utilisateur est {user_name}. Appelle-le par son prénom quand c'est naturel.\nQuestion : {prompt}"
    print("=== ESPION GROQ : J'appelle Groq ===", flush=True)
    print("=== ESPION GROQ KEY PRESENT ? :", bool(GROQ_API_KEY), "LONGUEUR:", len(GROQ_API_KEY) if GROQ_API_KEY else 0, "===", flush=True)
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        timeout=60,
        json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":SYSTEM},{"role":"user","content":full_prompt}],"temperature":0.6,"max_tokens":1500})
    print("=== ESPION GROQ STATUS :", r.status_code, "===", flush=True)
    print("=== ESPION GROQ REPONSE :", r.text[:800], "===", flush=True)
    return r.json()["choices"][0]["message"]["content"]

# ============ WHATSAPP ============
# --- ESPION 2 : WHATSAPP ENVOI ---
def send_text(to, text):
    for i in range(0, len(text), 4000):
        print("=== ESPION WHATSAPP : J'essaie d'envoyer a", to, "PHONE_ID:", PHONE_ID, "TOKEN PRESENT ?", bool(WHATSAPP_TOKEN), "===", flush=True)
        resp = requests.post(f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product":"whatsapp","to":to,"text":{"body":text[i:i+4000]}})
        print("=== ESPION WHATSAPP STATUS :", resp.status_code, "===", flush=True)
        print("=== ESPION WHATSAPP REPONSE :", resp.text[:800], "===", flush=True)

def send_image(to, url, caption="Voilà 👑"):
    requests.post(f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product":"whatsapp","to":to,"type":"image","image":{"link":url,"caption":caption}})

def download_media(media_id):
    meta = requests.get(f"https://graph.facebook.com/v21.0/{media_id}",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).json()
    url = meta.get("url")
    return requests.get(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).content

def transcribe_audio(audio_bytes):
    try:
        files = {"file": ("audio.ogg", BytesIO(audio_bytes), "audio/ogg")}
        r = requests.post("https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files=files, data={"model": "whisper-1", "language": "fr"}, timeout=60)
        return r.json().get("text", "")
    except Exception as e:
        print("Whisper erreur:", e)
        return ""

def ocr_image(b):
    try:
        img = Image.open(BytesIO(b))
        return pytesseract.image_to_string(img, lang="fra+eng").strip()
    except: return ""

def is_image_gen(text):
    return any(k in text.lower() for k in ["génère","genere","crée une image","cree une image","dessine","image de"])

def gen_image_url(prompt):
    clean = re.sub(r'(génère|genere|crée|cree|dessine|une image|image de|moi)', '', prompt, flags=re.I).strip() or prompt
    return f"https://image.pollinations.ai/prompt/{requests.utils.quote(clean)}?width=1024&height=1024&seed=42&nologo=true"

# ============ DASHBOARD SECRET ============
DASHBOARD_HTML = """
<html><head><meta name='viewport' content='width=device-width'><style>
body{font-family:Arial;background:#0f0f0f;color:white;padding:15px}
h1{color:#25D366} .card{background:#1e1e1e;padding:12px;border-radius:10px;margin:10px 0}
.q{color:#25D366;font-weight:bold} .r{color:#ddd} small{color:#888}
input{padding:10px;width:80%} button{padding:10px;background:#25D366;border:none;border-radius:5px}
</style></head><body>
<h1>👑 CLT AI - DASHBOARD SECRET</h1>
<p>Total conversations : <b>{{total}}</b></p>
<form><input name='key' placeholder='Mot de passe admin' type='password'><button>Voir</button></form>
{% for l in logs %}
<div class='card'><small>{{l[1]}} | {{l[2]}} ({{l[3]}}) | {{l[4]}}</small><br>
<span class='q'>Q: {{l[5]}}</span><br><span class='r'>R: {{l[6]}}</span></div>
{% endfor %}
</body></html>
"""

@app.route("/dashboard")
def dashboard():
    if request.args.get("key") != ADMIN_PASSWORD:
        return render_template_string(DASHBOARD_HTML, logs=[], total=0)
    conn = sqlite3.connect(DB_FILE)
    logs = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 200").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    conn.close()
    return render_template_string(DASHBOARD_HTML, logs=logs, total=total)

# ============ WEBHOOK ============
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data()
    if not verify_sig(raw, request.headers.get("X-Hub-Signature-256","")):
        return "Signature invalide", 403
    data = request.get_json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value: return "ok", 200
        msg = value["messages"][0]
        num = msg["from"]; typ = msg.get("type")
        print("=== ESPION WEBHOOK : Message recu de", num, "type:", typ, "===", flush=True)
        # RECUPERE LE VRAI NOM WHATSAPP
        user_name = "mon frère"
        try:
            user_name = value["contacts"][0]["profile"]["name"]
        except: pass

        if rate_limited(num):
            send_text(num, f"⏳ Attends 1 min stp {user_name}, tu envoies trop vite.")
            return "ok", 200

        # --- SALUTATION AVEC NOM ---
        if typ == "text":
            text_low = msg["text"]["body"].lower().strip()
            if text_low in ["salut","bonjour","hello","hi","bonsoir","yo","cc"]:
                send_text(num, f"Salut {user_name} 👑 ! Moi c'est CLT AI, une intelligence artificielle 100% congolaise, développée par un jeune ingénieur congolais. Comment je peux t'aider aujourd'hui ? Tu peux m'envoyer texte, photo, vocal, ou me dire 'génère une image de...'")
                save_log(num, user_name, "SALUT 👋", text_low, "Salutation CLT AI")
                return "ok", 200

        # --- VOCAL ---
        if typ in ["audio","voice"]:
            send_text(num, f"🎧 J'écoute ton vocal {user_name}...")
            audio_bytes = download_media(msg["audio"]["id"])
            texte = transcribe_audio(audio_bytes)
            if not texte:
                send_text(num, f"Je n'ai pas bien entendu {user_name}, renvoie ton vocal stp.")
                return "ok", 200
            if is_forbidden(texte):
                send_text(num, f"Désolé {user_name}, je ne peux pas aider sur ça.")
                return "ok", 200
            reponse = ask_clt(f"L'utilisateur a dit en vocal : {texte}", user_name)
            save_log(num, user_name, "VOCAL 🎧", texte, reponse)
            send_text(num, reponse)
            return "ok", 200

        # --- PHOTO ---
        if typ == "image":
            send_text(num, f"📸 Photo reçue {user_name}, j'analyse...")
            b = download_media(msg["image"]["id"])
            caption = msg["image"].get("caption", "Résous ce qui est sur cette photo.")
            ocr = ocr_image(b)
            if not ocr:
                send_text(num, f"Je vois la photo {user_name} mais je n'arrive pas à lire. Envoie plus nette stp.")
                return "ok", 200
            reponse = ask_clt(f"Texte sur photo : {ocr}\nQuestion : {caption}\nRésous étape par étape.", user_name)
            save_log(num, user_name, "PHOTO 📸", ocr, reponse)
            send_text(num, reponse)
            return "ok", 200

        # --- TEXTE ---
        if typ == "text":
            text = msg["text"]["body"]
            if any(k in text.lower() for k in ["ton créateur","ton createur","qui t'a créé","qui t'a cree","qui es tu","c'est qui clt","t'es qui","qui t'a fait"]):
                reponse = f"Je suis CLT AI, {user_name} 👑 Une intelligence artificielle 100% congolaise, développée par un jeune ingénieur congolais. Je suis là pour t'aider : cours, exercices, maths, photos, vocaux, images, tout !"
                send_text(num, reponse)
                save_log(num, user_name, "IDENTITE", text, reponse)
                return "ok", 200
            if is_forbidden(text):
                send_text(num, f"Désolé {user_name}, je ne peux pas aider sur ce sujet. Pose-moi un exercice, cours, maths...")
                return "ok", 200
            if is_image_gen(text):
                send_text(num, f"🎨 Je génère ton image {user_name}...")
                url = gen_image_url(text)
                send_image(num, url, caption=f"Voilà ton image {user_name}, générée par CLT AI 👑")
                save_log(num, user_name, "IMAGE 🎨", text, "Image générée")
                return "ok", 200
            reponse = ask_clt(text, user_name)
            save_log(num, user_name, "TEXTE 💬", text, reponse)
            send_text(num, reponse)
            return "ok", 200
    except Exception as e:
        print("ERREUR:", e, flush=True)
    return "ok", 200

@app.route("/")
def home(): return "CLT AI Pro en ligne 👑 100% Congolais", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
