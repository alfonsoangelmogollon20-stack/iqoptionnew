import os
import json
import logging
from flask import Flask, request, jsonify
from iqoptionapi.stable_api import IQ_Option

# --- Configuración de Logging (para ver qué pasa en Render) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Inicialización de Flask ---
app = Flask(__name__)

# --- Credenciales y Clave Secreta (Configurar en Render) ---
IQ_EMAIL = os.environ.get("IQ_EMAIL")
IQ_PASSWORD = os.environ.get("IQ_PASSWORD")
SECRET_KEY = os.environ.get("WEBHOOK_SECRET_KEY")

# --- Variables Globales ---
API = None # La conexión se gestionará bajo demanda

# --- Función para gestionar la conexión a IQ Option ---
def get_iq_api_connection():
    """
    Gestiona la conexión a IQ Option. Si no existe o se ha perdido, crea una nueva.
    """
    global API
    if API is None or not API.check_connect():
        logging.info("Conexión a IQ Option no encontrada o perdida. Creando una nueva...")
        API = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
        API.connect()
        
        if API.check_connect():
            logging.info("✅ Conexión con IQ Option establecida correctamente.")
            API.change_balance("PRACTICE") # Opcional: Forzar cuenta demo
        else:
            logging.error("❌ Fallo al conectar con IQ Option. Revisa credenciales.")
            API = None # Falló, se reinicia para intentar en la próxima señal
    return API

# --- Endpoint principal que recibe las alertas ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logging.info(f"📩 Señal recibida: {data}")

        # 1. Verificación de Seguridad
        if not SECRET_KEY or data.get("secret") != SECRET_KEY:
            logging.warning("Acceso denegado: Clave secreta incorrecta o no configurada.")
            return jsonify({"status": "error", "msg": "Clave secreta inválida"}), 403

        # 2. Lógica de Trading Flexible
        par = data.get("symbol", "EURUSD")
        accion = data.get("action", "").lower()
        
        direction = "" # Variable para guardar 'call' o 'put'
        if accion == "buy" or accion == "call":
            direction = "call"
        elif accion == "sell" or accion == "put":
            direction = "put"

        if not direction:
            logging.error(f"❌ Acción inválida recibida: '{accion}'")
            return jsonify({"status": "error", "msg": "Acción inválida"}), 400

        # 3. Obtener conexión y operar
        iq_api = get_iq_api_connection()
        if not iq_api:
            return jsonify({"status": "error", "msg": "No se pudo conectar a IQ Option"}), 500

        inversion = int(data.get("amount", 10))
        expiracion = int(data.get("expiration", 5))

        # --- BLOQUE DE DIAGNÓSTICO MEJORADO ---
        check, order_data = iq_api.buy_digital_spot(par, inversion, direction, expiracion)

        if check:
            order_id = order_data if isinstance(order_data, (int, str)) else order_data.get('id')
            msg = f"✅ Orden digital enviada: {par} | {direction.upper()} | ${inversion} | {expiracion} min | ID: {order_id}"
            logging.info(msg)
            return jsonify({"status": "success", "msg": msg, "order_id": order_id}), 200
        else:
            # Esta línea es la clave: nos mostrará la razón real del fallo.
            error_msg = f"Fallo al enviar la orden. Razón de IQ Option: {order_data}"
            logging.error(f"❌ {error_msg}")
            return jsonify({"status": "error", "msg": error_msg}), 500
            
    except Exception as e:
        logging.error(f"🚨 Error inesperado en el webhook: {e}")
        return jsonify({"status": "error", "msg": f"Error interno: {str(e)}"}), 500

# --- Ruta de prueba para saber si el servidor está vivo ---
@app.route("/", methods=["GET"])
def home():
    return "🚀 Servidor del Bot de IQ Option (con diagnóstico) está activo.", 200

# --- Inicio de la aplicación ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


