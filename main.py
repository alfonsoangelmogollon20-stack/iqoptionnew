from flask import Flask, request, jsonify
from iqoptionapi.stable_api import IQ_Option
import time

# === CONFIGURACIÓN DE IQ OPTION ===
IQ_USER = "TU_CORREO"       # <-- Pon tu correo de IQ Option
IQ_PASSWORD = "TU_PASSWORD" # <-- Pon tu contraseña de IQ Option

print("🔁 Intentando conectar a IQ Option...")
Iq = IQ_Option(IQ_USER, IQ_PASSWORD)
Iq.connect()

if Iq.check_connect():
    print("✅ Conectado a IQ Option correctamente")
else:
    print("❌ No se pudo conectar a IQ Option")
    exit()

# === CONFIGURACIÓN FLASK ===
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "🚀 Webhook IQ Option activo"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Muestra la data cruda
        raw_data = request.data.decode()
        print("📩 Señal recibida (RAW):", raw_data)

        # Intenta parsear JSON aunque no tenga header correcto
        data = request.get_json(force=True, silent=True)
        print("📦 JSON parseado:", data)

        if not data:
            return jsonify({"error": "No se recibió JSON válido"}), 400

        par = data.get("par")
        monto = float(data.get("monto", 1))
        direccion = data.get("direccion", "").lower()
        tiempo = int(data.get("tiempo", 1))

        print(f"✅ Operando: {par} - {direccion} - {monto}$ - {tiempo}m")

        # Enviar operación
        check, order_id = Iq.buy(monto, par, direccion, tiempo)
        if check:
            print(f"🎯 Operación enviada correctamente. ID: {order_id}")
            return jsonify({"status": "ok", "order_id": order_id}), 200
        else:
            print("❌ Error al enviar la operación.")
            return jsonify({"status": "error"}), 500

    except Exception as e:
        print("⚠️ Error en webhook:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
