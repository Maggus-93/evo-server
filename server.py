from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import requests
from datetime import datetime
import os

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

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route("/verify", methods=["POST"])
def verify():
    data    = request.get_json() or {}
    key     = data.get("key",     "").strip().upper()
    pc_name = data.get("pc_name", "Unbekannt")
    hwid    = data.get("hwid",    "Unbekannt")
    product = data.get("product", "op")          # welches Programm fragt an

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

    # ── Key existiert nicht ──────────────────────────
    if not row:
        conn.close()
        return jsonify({"valid": False, "msg": "Ungültiger Key — bitte nochmal prüfen."})

    # ── Key gehört zum falschen Produkt ──────────────
    if row["product"] and row["product"] != product:
        conn.close()
        return jsonify({"valid": False, "msg": f"Dieser Key ist nicht für dieses Produkt gültig."})

    # ── Key bereits auf anderem PC aktiviert ─────────
    if row["used"] == 1 and row["used_by_hwid"] and row["used_by_hwid"] != hwid:
        conn.close()
        return jsonify({"valid": False, "msg": "Key ist bereits auf einem anderen PC aktiviert!"})

    event_type = "ERSTAKTIVIERUNG" if row["used"] == 0 else "LOGIN"

    # ── Erstaktivierung: in DB eintragen ─────────────
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


@app.route("/download/<path:filename>")
def download(filename):
    return send_from_directory(DOWNLOADS_DIR, filename)


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
            {"name": "🔑 Key",        "value": f"`{key}`",                          "inline": False},
            {"name": "📦 Produkt",    "value": prod_name,                           "inline": True},
            {"name": "👤 Discord",    "value": f"{discord_name} (<@{discord_id}>)", "inline": True},
            {"name": "🖥️ PC-Name",    "value": f"`{pc_name}`",                      "inline": True},
            {"name": "🌐 IP",         "value": f"`{ip}`",                           "inline": True},
            {"name": "🕒 Zeit",       "value": time,                                "inline": False},
        ],
        "footer": {"text": "EVO System"}
    }
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
    except Exception:
        pass


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
