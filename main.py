from flask import Flask, request, jsonify
from iqoptionapi.stable_api import IQ_Option
import os
import threading
import time

app = Flask(__name__)

# Credenciales desde variables de entorno
IQ_USERNAME = os.getenv("IQ_USERNAME")
IQ_PASSWORD = os.getenv("IQ_PASSWORD")

# Conexión IQ Option
Iq = IQ_Option(IQ_USERNAME, IQ_PASSWORD)

def conectar_iqoption():
    print("🔁 Intentando conectar a IQ Option...")
    conectado, razon = Iq.connect()
    if conectado:
        print("✅ Conectado a IQ Option correctamente")
    else:
        print(f"❌ Error al conectar: {razon}")
    return conectado

# Mantener sesión viva
def mantener_sesion():
    while True:
        if not Iq.check_connect():
            print("⚠️ Conexión perdida. Reintentando...")
            conectar_iqoption()
        time.sleep(10)

# Inicia conexión al arrancar
if conectar_iqoption():
    threading.Thread(target=mantener_sesion, daemon=True).start()

@app.route("/", methods=["GET"])
def home():
    return "Servidor IQ Option activo", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"📩 Señal recibida: {data}")

    if not Iq.check_connect():
        print("⚠️ Reconectando antes de operar...")
        conectar_iqoption()

    try:
        par = data["par"]
        monto = float(data["monto"])
        direccion = data["direccion"].lower()
        tiempo = int(data["tiempo"])

        Iq.buy(monto, par, direccion, tiempo)
        print(f"✅ Operación enviada: {par} {direccion.upper()} {monto}$ {tiempo}m")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"❌ Error procesando la señal: {e}")
        return jsonify({"status": "error", "detalle": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
