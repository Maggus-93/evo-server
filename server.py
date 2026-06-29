from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import requests
from datetime import datetime
import os
import time
import threading

app = Flask(__name__)

# ═══════════════════════════════════════════════════
#  KONFIGURATION
# ═══════════════════════════════════════════════════
WEBHOOK_URL   = "https://discord.com/api/webhooks/1513941742376849429/iNukmmK1cWaAG0_65mZXDrVRxvILnH89TN0qmQWhlPAxGR2qQIEL4102ADMzwwHqSUPS"
DB_PATH       = "licenses.db"
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "files")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════
#  DB
# ═══════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key            TEXT PRIMARY KEY,
            product        TEXT,
            discord_id     TEXT,
            discord_name   TEXT,
            used           BOOLEAN DEFAULT 0,
            used_by_ip     TEXT,
            used_by_pcname TEXT,
            used_by_hwid   TEXT,
            used_at        TEXT
        )
    """)
    conn.commit()
    return conn

# ═══════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════

@app.route("/")
def index():
    # ─── Diese HTML-Seite wird angezeigt ───
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EVO Produkte</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a2e; color: #fff; padding: 20px; }
            .product { background: #16213e; border-radius: 10px; padding: 20px; margin: 20px 0; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
            .product img { width: 80px; height: 80px; border-radius: 10px; }
            .product-info { flex: 1; }
            .product-info h2 { margin: 0; }
            .product-info p { color: #aaa; }
            .btn { background: #4CAF50; border: none; color: white; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 16px; }
            .btn:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <h1>📦 Meine Produkte</h1>
        <div id="product-list"></div>

        <script>
            async function loadProducts() {
                try {
                    const response = await fetch('/products');
                    const data = await response.json();
                    const container = document.getElementById('product-list');
                    container.innerHTML = '';

                    data.products.forEach(product => {
                        const div = document.createElement('div');
                        div.className = 'product';

                        const img = document.createElement('img');
                        img.src = product.img;
                        img.alt = product.name;

                        const info = document.createElement('div');
                        info.className = 'product-info';
                        info.innerHTML = `<h2>${product.name}</h2><p>${product.desc}</p>`;

                        const btn = document.createElement('button');
                        btn.className = 'btn';
                        btn.textContent = '📥 Auf Google Drive öffnen';
                        // ✅ Hier: Öffnet die Google‑Drive‑Seite im neuen Tab – KEIN Download!
                        btn.addEventListener('click', () => {
                            window.open(product.file_url, '_blank');
                        });

                        div.appendChild(img);
                        div.appendChild(info);
                        div.appendChild(btn);
                        container.appendChild(div);
                    });
                } catch (error) {
                    console.error('Fehler:', error);
                    document.getElementById('product-list').innerHTML = '<p>⚠️ Produkte konnten nicht geladen werden.</p>';
                }
            }
            document.addEventListener('DOMContentLoaded', loadProducts);
        </script>
    </body>
    </html>
    """
    return html, 200, {'Content-Type': 'text/html'}

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route("/products")
def products():
    return jsonify({
        "products": [
            {
                "name":     "PC Optimizer",
                "desc":     "Optimiert deinen PC für maximale Performance.",
                "img":      "https://raw.githubusercontent.com/Maggus-93/evo-server/main/myoptimizer.png",
                "file_url": "https://drive.google.com/file/d/1csjNprYTRFb4Qku9Em-dwq7UXqAjk32K/view?usp=sharing"
            },
            {
                "name":     "Swiftfind",
                "desc":     "Findet jede Datei auf deinem PC für maximale Übersicht.",
                "img":      "https://raw.githubusercontent.com/Maggus-93/evo-server/main/Swiftfinds.png",
                "file_url": "https://drive.google.com/file/d/1NKtqUisk-tUOC6aVm1iW_CsyJKDcg5P2/view?usp=sharing"
            }
        ]
    })

@app.route("/addkey", methods=["POST"])
def addkey():
    data = request.get_json() or {}
    if data.get("secret") != "EVO_SECRET_2024":
        return jsonify({"success": False, "msg": "Unauthorized"}), 403

    key          = data.get("key", "").strip().upper()
    product      = data.get("product", "")
    discord_id   = data.get("discord_id", "")
    discord_name = data.get("discord_name", "")

    if not key or not product:
        return jsonify({"success": False, "msg": "Fehlende Felder"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO keys (key, product, discord_id, discord_name) VALUES (?,?,?,?)",
            (key, product, discord_id, discord_name)
        )
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "msg": "Key existiert bereits"})
    finally:
        conn.close()

@app.route("/verify", methods=["POST"])
def verify():
    data    = request.get_json() or {}
    key     = data.get("key",     "").strip().upper()
    pc_name = data.get("pc_name", "Unbekannt")
    hwid    = data.get("hwid",    "Unbekannt")
    product = data.get("product", "op")

    ip = (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For")  or
        request.remote_addr
    )
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM keys WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"valid": False, "msg": "Ungültiger Key — bitte nochmal prüfen."})

    if row["product"] and row["product"] != product:
        conn.close()
        return jsonify({"valid": False, "msg": "Dieser Key ist nicht für dieses Produkt gültig."})

    if row["used"] == 1 and row["used_by_hwid"] and row["used_by_hwid"] != hwid:
        conn.close()
        return jsonify({"valid": False, "msg": "Key ist bereits auf einem anderen PC aktiviert!"})

    event_type = "ERSTAKTIVIERUNG" if row["used"] == 0 else "LOGIN"

    if row["used"] == 0:
        c.execute("""
            UPDATE keys
            SET used=1,
                used_by_ip=?,
                used_by_pcname=?,
                used_by_hwid=?,
                used_at=?
            WHERE key=?
        """, (ip, pc_name, hwid, now, key))
        conn.commit()

    conn.close()

    _discord_notify(key, row["discord_name"], row["discord_id"],
                    ip, pc_name, now, event_type, row["product"] or product)

    return jsonify({"valid": True, "msg": "Aktivierung erfolgreich!"})

@app.route("/keyinfo/<key>")
def keyinfo(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM keys WHERE key=?", (key.strip().upper(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"found": False})
    return jsonify({"found": True, "key": dict(row)})

@app.route("/revokekey", methods=["POST"])
def revokekey():
    data = request.get_json() or {}
    if data.get("secret") != "EVO_SECRET_2024":
        return jsonify({"success": False}), 403

    key = data.get("key", "").strip().upper()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key FROM keys WHERE key=?", (key,))
    if not c.fetchone():
        conn.close()
        return jsonify({"success": False})

    c.execute("""
        UPDATE keys SET used=0, used_by_ip=NULL,
        used_by_pcname=NULL, used_by_hwid=NULL, used_at=NULL
        WHERE key=?
    """, (key,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/stats")
def stats():
    conn = get_db()
    c = conn.cursor()
    result = {}
    for prod_id in ["op", "fps"]:
        c.execute("SELECT COUNT(*) FROM keys WHERE product=?", (prod_id,))
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM keys WHERE product=? AND used=1", (prod_id,))
        used = c.fetchone()[0]
        result[prod_id] = {"total": total, "used": used}
    conn.close()
    return jsonify(result)

# ═══════════════════════════════════════════════════
#  DISCORD WEBHOOK
# ═══════════════════════════════════════════════════
def _discord_notify(key, discord_name, discord_id, ip, pc_name, time, event_type, product):
    color = 0x9333ea if event_type == "ERSTAKTIVIERUNG" else 0x3b82f6
    emoji = "🚀" if event_type == "ERSTAKTIVIERUNG" else "🔑"
    prod_labels = {"op": "PC Optimizer", "fps": "FPS Booster"}
    prod_name = prod_labels.get(product, product.upper())

    embed = {
        "title":  f"{emoji} {event_type} — {prod_name}",
        "color":  color,
        "fields": [
            {"name": "🔑 Key",      "value": f"`{key}`",                          "inline": False},
            {"name": "📦 Produkt",  "value": prod_name,                           "inline": True},
            {"name": "👤 Discord",  "value": f"{discord_name} (<@{discord_id}>)", "inline": True},
            {"name": "🖥️ PC-Name",  "value": f"`{pc_name}`",                      "inline": True},
            {"name": "🌐 IP",       "value": f"`{ip}`",                           "inline": True},
            {"name": "🕒 Zeit",     "value": time,                                "inline": False},
        ],
        "footer": {"text": "EVO System"}
    }
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
    except Exception:
        pass

def _keep_alive():
    while True:
        try:
            requests.get("https://evo-server-eegx.onrender.com/ping", timeout=5)
        except:
            pass
        time.sleep(240)

threading.Thread(target=_keep_alive, daemon=True).start()

# ═══════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    print("✅ EVO Server läuft auf Port 5000...")
    try:
        requests.post(WEBHOOK_URL, json={"content": "✅ EVO Server gestartet"}, timeout=5)
    except Exception as e:
        print("Webhook Fehler:", e)
    app.run(host="0.0.0.0", port=5000, debug=False)
