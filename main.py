from flask import Flask, request, jsonify
from iqoptionapi.stable_api import IQ_Option
import json
import os

# Credenciales IQ Option (cárgalas desde variables de entorno en Render)
IQ_EMAIL = os.getenv("IQ_EMAIL")
IQ_PASSWORD = os.getenv("IQ_PASSWORD")

# Conexión a IQ Option
print("Conectando a IQ Option...")
API = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
API.connect()

if API.check_connect():
    print("✅ Conectado a IQ Option en cuenta DEMO")
    API.change_balance("PRACTICE")  # Forzamos demo
else:
    print("❌ Error al conectar. Revisa credenciales.")
    exit()

# Configuración del bot
INVERSIÓN = 10  # USD por operación
EXPIRATION = 5  # minutos

# Flask App
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = json.loads(request.data)
        print(f"📩 Señal recibida: {data}")

        par = data.get("symbol", "EURUSD")
        accion = data.get("action", "").lower()

        if accion not in ["call", "put"]:
            return jsonify({"status": "error", "msg": "Acción inválida"}), 400

        direction = "call" if accion == "call" else "put"

        status, order_id = API.buy(INVERSIÓN, par, direction, EXPIRATION)

        if status:
            print(f"✅ Orden enviada: {order_id} | {par} | {direction.upper()} | {INVERSIÓN}$ | {EXPIRATION} min")
            return jsonify({"status": "success", "order_id": order_id}), 200
        else:
            print("❌ Error al enviar la orden")
            return jsonify({"status": "error", "msg": "Fallo al enviar la orden"}), 500

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot IQ Option activo en Render", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
