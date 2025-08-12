from flask import Flask, request, jsonify
from iqoptionapi.stable_api import IQ_Option
from threading import Thread
import time
import os

# Configuración
IQ_USERNAME = os.getenv("IQ_USERNAME", "tu_email")
IQ_PASSWORD = os.getenv("IQ_PASSWORD", "tu_password")

app = Flask(__name__)

# Conectar a IQ Option al iniciar
api = IQ_Option(IQ_USERNAME, IQ_PASSWORD)
print("Conectando a IQ Option...")
api.connect()

while not api.check_connect():
    print("Error de conexión, reintentando...")
    time.sleep(1)

print("✅ Conexión establecida con IQ Option")

# Función que procesa la orden en segundo plano
def procesar_orden(data):
    try:
        symbol = data.get("symbol")
        direction = data.get("direction")  # "call" o "put"
        amount = float(data.get("amount", 1))
        expiration = int(data.get("expiration", 1))  # minutos

        print(f"📌 Ejecutando orden: {direction.upper()} {symbol} | Monto: {amount} | Expira en {expiration}m")
        _, order_id = api.buy(amount, symbol, direction, expiration)

        if order_id:
            print(f"✅ Orden enviada correctamente. ID: {order_id}")
        else:
            print("❌ Error al enviar la orden")

    except Exception as e:
        print(f"⚠ Error procesando orden: {e}")

# Endpoint webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"📩 Datos recibidos: {data}")

    # Lanzar la orden en segundo plano
    Thread(target=procesar_orden, args=(data,)).start()

    # Responder inmediatamente
    return jsonify({"status": "ok", "message": "Orden recibida y procesándose"})

# Inicio
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
