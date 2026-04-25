import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)
DATABASE = "orders.db"

BLAND_API_KEY = os.environ.get("BLAND_API_KEY", "org_1403040aa8b2e290506e96ea3d2a5ba8ec38040ac4ab8bd7b03640a13f1b9170e44953cdf2809d5b254c69")
BLAND_API_URL = "https://api.bland.ai/v1/calls"

# ── Products ──────────────────────────────────────────────────────────────────
PRODUCTS = {
    "1": {"id": "1", "name": "Classic", "price": 3999},
    "2": {"id": "2", "name": "Premium", "price": 4499},
    "3": {"id": "3", "name": "Basic",   "price": 2999},
}

# ── Bland.ai conversation script (multilingual prompt) ───────────────────────
BLAND_PROMPT = """
You are an AI sales agent for Automaton Crocs Store. Your job is to take orders from customers over a phone call.

IMPORTANT RULES:
1. Detect the language the customer is speaking (English, Hindi, Kannada, or Marathi) and RESPOND IN THE SAME LANGUAGE throughout the entire call.
2. Be friendly, concise, and professional — this is a phone call, keep responses short.
3. Follow the exact flow below and do not deviate.
4. Once order is confirmed, say goodbye and end the call.

PRODUCTS AVAILABLE:
1. Classic - ₹3,999
2. Premium - ₹4,499
3. Basic - ₹2,999

CALL FLOW:
Step 1 - GREET:
  English: "Hello! This is Automaton Crocs Store. I'm calling to help you place a Crocs order. Is this a good time?"
  Hindi: "Namaste! Main Automaton Crocs Store se bol raha hoon. Kya aap Crocs order karna chahenge?"
  Kannada: "Namaskara! Naanu Automaton Crocs Store inda maathaaduttiddene. Nimma order tegedukollabahuda?"
  Marathi: "Namaskar! Mi Automaton Crocs Store madhun bolto. Tumhi order dyaycha ahe ka?"

Step 2 - ASK WHICH PRODUCT:
  Present all 3 options with prices. Ask customer to choose one or more.
  English: "We have three Crocs options: Classic at ₹3,999, Premium at ₹4,499, and Basic at ₹2,999. Which one would you like to order?"

Step 3 - ASK QUANTITY for each product chosen:
  Ask how many pairs they want for each product.

Step 4 - CONFIRM ORDER:
  Read back the full order with total price. Ask them to confirm.
  Example: "So you want 2 pairs of Classic (₹7,998) and 1 Premium (₹4,499). Total: ₹12,497. Shall I confirm this order?"

Step 5 - SAVE & END:
  If confirmed: "Your order has been placed successfully! You will receive a confirmation soon. Thank you for choosing Automaton Crocs!"
  If cancelled: "No problem! Feel free to call us anytime. Goodbye!"

LANGUAGE RESPONSES FOR STEP 5:
  Hindi confirmed: "Aapka order confirm ho gaya! Jaldi hi confirmation milega. Dhanyavaad!"
  Kannada confirmed: "Nimma order confirm aagide! Sheeghradalli confirmation baruttade. Dhanyavaadagalu!"
  Marathi confirmed: "Tumcha order confirm zala! Lavkarch confirmation milel. Dhanyavaad!"

At the end of the call, after you say goodbye, you MUST output the order summary in this EXACT format (this is for the system, do not read the word 'ORDER_DATA' out loud):
ORDER_DATA:{"customer_phone":"{{phone}}","products":[{"name":"Classic","quantity":1,"price":3999}],"total":3999,"language":"en"}

Ensure the product names match EXACTLY: "Classic", "Premium", or "Basic".
"""

# ── Inbound prompt (for when customers call IN) ──────────────────────────────
INBOUND_PROMPT = """
You are an AI sales agent for Automaton Crocs Store. A customer is calling YOU to place an order.

IMPORTANT RULES:
1. Detect the language the customer is speaking (English, Hindi, Kannada, or Marathi) and RESPOND IN THE SAME LANGUAGE throughout the entire call.
2. Be friendly, concise, and professional — this is a phone call, keep responses short.
3. Follow the exact flow below and do not deviate.
4. Once order is confirmed, say goodbye and end the call.

PRODUCTS AVAILABLE:
1. Classic - ₹3,999
2. Premium - ₹4,499
3. Basic - ₹2,999

CALL FLOW:
Step 1 - GREET:
  English: "Hello! Welcome to Automaton Crocs Store! How can I help you today?"
  Hindi: "Namaste! Automaton Crocs Store mein aapka swagat hai! Aapki kya madad kar sakta hoon?"
  Kannada: "Namaskara! Automaton Crocs Store ge swagatavagide! Nimge hege sahaya maadabeku?"
  Marathi: "Namaskar! Automaton Crocs Store madhye tumche swagat aahe! Tumhala kaay madad karoo?"

Step 2 - ASK WHICH PRODUCT:
  Present all 3 options with prices. Ask customer to choose one or more.
  English: "We have three Crocs options: Classic at ₹3,999, Premium at ₹4,499, and Basic at ₹2,999. Which one would you like to order?"

Step 3 - ASK QUANTITY for each product chosen:
  Ask how many pairs they want for each product.

Step 4 - CONFIRM ORDER:
  Read back the full order with total price. Ask them to confirm.

Step 5 - SAVE & END:
  If confirmed: "Your order has been placed successfully! You will receive a confirmation soon. Thank you for choosing Automaton Crocs!"
  If cancelled: "No problem! Feel free to call us anytime. Goodbye!"

At the end of the call, after you say goodbye, you MUST output the order summary in this EXACT format (this is for the system, do not read the word 'ORDER_DATA' out loud):
ORDER_DATA:{"customer_phone":"caller","products":[{"name":"Classic","quantity":1,"price":3999}],"total":3999,"language":"en"}

Ensure the product names match EXACTLY: "Classic", "Premium", or "Basic".
"""

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                phone       TEXT NOT NULL,
                call_id     TEXT,
                products    TEXT NOT NULL,
                total       INTEGER DEFAULT 0,
                language    TEXT DEFAULT 'en',
                status      TEXT DEFAULT 'pending',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id     TEXT UNIQUE,
                phone       TEXT NOT NULL,
                status      TEXT DEFAULT 'initiated',
                created_at  TEXT NOT NULL
            );
        """)
        db.commit()

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/products")
def get_products():
    return jsonify(list(PRODUCTS.values()))

@app.route("/api/call", methods=["POST"])
def make_call():
    """Trigger a Bland.ai outbound call to the customer."""
    data  = request.json or {}
    phone = data.get("phone", "").strip()
    lang  = data.get("language", "en")

    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    # Format phone number — ensure it has country code
    if not phone.startswith("+"):
        phone = "+91" + phone.lstrip("0")

    # Language-specific first sentences
    first_sentences = {
        "auto": "Hello! This is Automaton Crocs Store calling.",
        "en": "Hello! This is Automaton Crocs Store calling.",
        "hi": "Namaste! Main Automaton Crocs Store se bol raha hoon.",
        "kn": "Namaskara! Naanu Automaton Crocs Store inda maathaaduttiddene.",
    }

    # Bland.ai language codes (auto = en, but prompt handles switching)
    bland_langs = {"auto": "en", "en": "en", "hi": "hi", "kn": "kn"}

    import urllib.request
    import urllib.error

    payload = json.dumps({
        "phone_number": phone,
        "task": BLAND_PROMPT.replace("{{phone}}", phone),
        "voice": "maya",
        "language": bland_langs.get(lang, "en"),
        "max_duration": 5,
        "wait_for_greeting": True,
        "record": True,
        "amd": False,
        "answered_by_enabled": False,
        "noise_cancellation": True,
        "model": "enhanced",
        "first_sentence": first_sentences.get(lang, first_sentences["en"]),
        "webhook": "https://snuff-mortified-cilantro.ngrok-free.dev/api/webhook/bland",
    }).encode("utf-8")

    req = urllib.request.Request(
        BLAND_API_URL,
        data=payload,
        headers={
            "Authorization": BLAND_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return jsonify({"error": f"Bland API error: {body}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    call_id = result.get("call_id", "")

    # Save call record
    db = get_db()
    db.execute(
        "INSERT INTO calls (call_id, phone, status, created_at) VALUES (?,?,?,?)",
        (call_id, phone, "initiated", datetime.now().isoformat())
    )
    db.commit()

    return jsonify({"success": True, "call_id": call_id, "phone": phone})


@app.route("/api/webhook/bland", methods=["POST"])
def bland_webhook():
    """Receive call completion data from Bland.ai and extract order."""
    data = request.json or {}

    call_id    = data.get("call_id", "")
    transcript = data.get("concatenated_transcript", "") or data.get("transcript", "")
    status     = data.get("status", "completed")
    phone      = data.get("to", "") or data.get("from", "")

    db = get_db()

    # Update call status
    db.execute("UPDATE calls SET status=? WHERE call_id=?", (status, call_id))
    
    # Log full webhook data for debugging
    with open("webhook_log.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.now().isoformat()} ---\n")
        f.write(f"Call ID: {call_id}\n")
        f.write(f"Phone: {phone}\n")
        f.write(f"Status: {status}\n")
        f.write(f"Transcript: {transcript}\n")
        f.write(f"Full data keys: {list(data.keys())}\n")
        f.write("-" * 30 + "\n")

    order_saved = False

    # Method 1: Try ORDER_DATA JSON (if AI includes it)
    if "ORDER_DATA:" in transcript:
        try:
            import re
            match = re.search(r"ORDER_DATA:\s*(\{.*?\})", transcript, re.DOTALL)
            if match:
                order_data = json.loads(match.group(1))
                products_json = json.dumps(order_data.get("products", []))
                total = order_data.get("total", 0)
                language = order_data.get("language", "en")
                o_phone = order_data.get("customer_phone", phone)
                db.execute(
                    "INSERT INTO orders (phone, call_id, products, total, language, status, created_at) VALUES (?,?,?,?,?,?,?)",
                    (o_phone, call_id, products_json, total, language, "confirmed", datetime.now().isoformat())
                )
                order_saved = True
        except Exception as e:
            print(f"ORDER_DATA parse error: {e}")

    # Method 2: Parse natural conversation for products & quantities
    if not order_saved and transcript:
        try:
            order = parse_transcript_order(transcript, phone)
            if order and order["products"]:
                db.execute(
                    "INSERT INTO orders (phone, call_id, products, total, language, status, created_at) VALUES (?,?,?,?,?,?,?)",
                    (order["phone"], call_id, json.dumps(order["products"]), order["total"], order["language"], "confirmed", datetime.now().isoformat())
                )
                order_saved = True
                print(f"Order parsed from transcript: {order}")
        except Exception as e:
            print(f"Transcript parse error: {e}")

    db.commit()
    return jsonify({"received": True, "order_saved": order_saved})


def parse_transcript_order(transcript, phone):
    """Parse a natural conversation transcript to extract order details."""
    import re
    t = transcript.lower()

    # Detect language
    language = "en"
    if any(w in t for w in ["namaste", "haan", "chahiye", "kitne", "theek", "dhanyavaad"]):
        language = "hi"
    elif any(w in t for w in ["namaskara", "haudu", "beku", "dhanyavaadagalu"]):
        language = "kn"
    elif any(w in t for w in ["namaskar", "pahije", "tumcha"]):
        language = "mr"

    # Check if order was confirmed (not cancelled)
    cancel_words = ["cancel", "no thank", "not interested", "nahi", "illa", "nako", "goodbye", "it's not me"]
    confirm_words = ["confirm", "yes", "haan", "haudu", "ho", "placed successfully", "order confirm"]
    
    was_cancelled = any(w in t for w in cancel_words)
    was_confirmed = any(w in t for w in confirm_words)
    
    if was_cancelled and not was_confirmed:
        return None

    # Extract products mentioned by the assistant (what the customer agreed to)
    products = []
    product_map = {
        "classic": {"name": "Classic", "price": 3999},
        "premium": {"name": "Premium", "price": 4499},
        "basic":   {"name": "Basic",   "price": 2999},
    }

    # Look for quantity patterns near product names
    for key, prod in product_map.items():
        # Patterns like "2 pairs of Classic", "Classic × 2", "3 Classic"
        patterns = [
            rf'(\d+)\s*(?:pairs?\s*(?:of\s*)?)?{key}',
            rf'{key}\s*(?:×|x|pairs?)?\s*(\d+)',
            rf'(\d+)\s*{key}',
        ]
        qty = 0
        for pat in patterns:
            matches = re.findall(pat, t)
            if matches:
                qty = max(int(m) for m in matches)
                break
        
        # If product is mentioned but no quantity found, check for "one/1" defaults
        if qty == 0 and key in t:
            # Check if it's in the assistant's confirmation section
            # Look for the product being mentioned after customer says yes
            assistant_parts = re.findall(r'assistant:\s*(.*?)(?:user:|$)', t, re.DOTALL)
            for part in assistant_parts:
                if key in part and any(w in part for w in ["confirm", "order", "total", "placed"]):
                    qty = 1
                    break
        
        if qty > 0:
            products.append({"name": prod["name"], "quantity": qty, "price": prod["price"]})

    if not products:
        return None

    total = sum(p["price"] * p["quantity"] for p in products)
    return {"phone": phone, "products": products, "total": total, "language": language}


@app.route("/api/call/transcript/<call_id>")
def get_transcript(call_id):
    """Fetch full call transcript from Bland.ai."""
    import urllib.request
    req = urllib.request.Request(
        f"https://api.bland.ai/v1/calls/{call_id}",
        headers={
            "Authorization": BLAND_API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            transcript = data.get("concatenated_transcript", "") or data.get("transcript", "")
            return jsonify({
                "call_id": call_id,
                "status": data.get("status", ""),
                "transcript": transcript,
                "to": data.get("to", ""),
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/orders/manual", methods=["POST"])
def manual_order():
    """Save an order manually (fallback if webhook doesn't capture it)."""
    data = request.json or {}
    phone    = data.get("phone", "")
    call_id  = data.get("call_id", "")
    products = data.get("products", [])
    total    = data.get("total", 0)
    language = data.get("language", "en")

    if not phone or not products:
        return jsonify({"error": "phone and products required"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO orders (phone, call_id, products, total, language, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (phone, call_id, json.dumps(products), total, language, "confirmed", datetime.now().isoformat())
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/orders")
def get_orders():
    db     = get_db()
    rows   = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    orders = []
    for r in rows:
        o = dict(r)
        try:
            o["products"] = json.loads(o["products"])
        except Exception:
            o["products"] = []
        orders.append(o)
    return jsonify(orders)


@app.route("/api/calls")
def get_calls():
    db   = get_db()
    rows = db.execute("SELECT * FROM calls ORDER BY created_at DESC LIMIT 50").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/call/status/<call_id>")
def call_status(call_id):
    import urllib.request
    req = urllib.request.Request(
        f"https://api.bland.ai/v1/calls/{call_id}",
        headers={
            "Authorization": BLAND_API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return jsonify(json.loads(resp.read().decode()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/stats")
def get_stats():
    db = get_db()
    total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = db.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status='confirmed'").fetchone()[0]
    total_calls   = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    pending       = db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]

    # Language counts
    lang_rows = db.execute("SELECT language, COUNT(*) as cnt FROM orders GROUP BY language").fetchall()
    lang_counts = {}
    for row in lang_rows:
        lang_counts[row["language"] or "en"] = row["cnt"]

    return jsonify({
        "total_orders":   total_orders,
        "total_revenue":  total_revenue,
        "total_calls":    total_calls,
        "pending_orders": pending,
        "lang_counts":    lang_counts,
    })


@app.route("/api/inbound/setup", methods=["POST"])
def setup_inbound():
    """Set up a Bland.ai inbound phone number so customers can call the bot."""
    import urllib.request
    import urllib.error

    data = request.json or {}
    phone_number = data.get("phone_number", "").strip()

    if not phone_number:
        return jsonify({"error": "Phone number is required. Get one from Bland.ai dashboard."}), 400

    webhook_url = "https://snuff-mortified-cilantro.ngrok-free.dev/api/webhook/bland"

    payload = json.dumps({
        "phone_number": phone_number,
        "prompt": INBOUND_PROMPT,
        "voice": "maya",
        "first_sentence": "Hello! Welcome to Automaton Crocs Store! How can I help you today?",
        "wait_for_greeting": True,
        "record": True,
        "noise_cancellation": True,
        "model": "enhanced",
        "max_duration": 5,
        "webhook": webhook_url,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.bland.ai/v1/inbound",
        data=payload,
        headers={
            "Authorization": BLAND_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return jsonify({"error": f"Bland API error: {body}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"success": True, "data": result, "phone_number": phone_number})


@app.route("/api/inbound/numbers")
def get_inbound_numbers():
    """List inbound phone numbers from Bland.ai."""
    import urllib.request

    req = urllib.request.Request(
        "https://api.bland.ai/v1/inbound",
        headers={
            "Authorization": BLAND_API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return jsonify(json.loads(resp.read().decode()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  Automaton Crocs Order Bot")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
