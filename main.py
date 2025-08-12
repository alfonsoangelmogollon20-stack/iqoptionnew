import os
import time
from threading import Thread, Lock
from queue import Queue
from flask import Flask, request, jsonify

# IQ Option import desde el repo
from iqoptionapi.stable_api import IQ_Option

# Config
IQ_USERNAME = os.getenv("IQ_USERNAME")
IQ_PASSWORD = os.getenv("IQ_PASSWORD")
USE_DEMO = True

# Globals
api = None
api_lock = Lock()
connect_thread = None
order_queue = Queue()
connected_flag = False

app = Flask(__name__)

def connect_loop():
    """
    Hilo de conexión persistente a IQ Option.
    Intenta reconectar si se cae.
    """
    global api, connected_flag
    while True:
        try:
            if not IQ_USERNAME or not IQ_PASSWORD:
                print("⚠️ IQ credentials not set - set IQ_USERNAME and IQ_PASSWORD in env vars")
                time.sleep(10)
                continue

            print("🔁 Intentando conectar a IQ Option...")
            tmp_api = IQ_Option(IQ_USERNAME, IQ_PASSWORD)
            tmp_api.connect()
            # retry until connected
            retry_count = 0
            while not tmp_api.check_connect() and retry_count < 10:
                print("⏳ Esperando conexión... retry", retry_count + 1)
                time.sleep(1)
                retry_count += 1

            if tmp_api.check_connect():
                with api_lock:
                    api = tmp_api
                    if USE_DEMO:
                        try:
                            api.change_balance("PRACTICE")
                        except Exception:
                            pass
                    connected_flag = True
                print("✅ Conectado a IQ Option")
                # permanecer hasta que se desconecte
                while tmp_api.check_connect():
                    time.sleep(2)
                print("⚠️ Se perdió conexión con IQ Option, reintentando...")
                with api_lock:
                    api = None
                    connected_flag = False
            else:
                print("❌ No se pudo conectar (timeout), reintentando en 5s")
                time.sleep(5)
        except Exception as e:
            print("❌ Error en connect_loop:", e)
            with api_lock:
                api = None
                connected_flag = False
            time.sleep(5)

def order_worker():
    """
    Consume la cola de órdenes y las envía cuando hay conexión.
    """
    global api
    while True:
        data = order_queue.get()
        try:
            symbol = data.get("symbol")
            direction = data.get("direction")  # "call" o "put"
            amount = float(data.get("amount", 10))
            expiration = int(data.get("expiration", 5))  # minutos
            print("📌 Order worker got:", symbol, direction, amount, expiration)

            # esperar hasta que haya conexión (pero con timeout)
            wait_for = 30  # seg
            waited = 0
            while True:
                with api_lock:
                    tmp_api = api
                if tmp_api and tmp_api.check_connect():
                    break
                time.sleep(1)
                waited += 1
                if waited >= wait_for:
                    print("⚠️ Timeout esperando conexión para enviar orden; descartando orden.")
                    break

            if tmp_api and tmp_api.check_connect():
                # enviar orden (iqoptionapi devuelve (success, id) o similar)
                try:
                    _, order_id = tmp_api.buy(amount, symbol, direction, expiration)
                    if order_id:
                        print(f"✅ Orden enviada. ID: {order_id}")
                    else:
                        print("❌ iqoptionapi devolvió fallo al intentar buy.")
                except Exception as e:
                    print("❌ Error enviando orden:", e)
            else:
                print("❌ No se envió la orden por falta de conexión.")
        except Exception as e:
            print("⚠ Error en order_worker:", e)
        finally:
            order_queue.task_done()

@app.route("/", methods=["GET"])
def home():
    status = {"connected": connected_flag}
    return jsonify(status), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json or {}
        # validaciones básicas
        symbol = data.get("symbol")
        direction = data.get("direction")
        if not symbol or direction not in ("call", "put"):
            return jsonify({"status": "error", "msg": "payload inválido: symbol y direction(call|put) required"}), 400

        # Forzar monto y expiración según tu petición (10$ y 5 min)
        payload = {
            "symbol": symbol,
            "direction": direction,
            "amount": float(10),      # monto fijo 10$
            "expiration": int(5)      # expiración fija 5 minutos
        }

        # encolar y devolver respuesta inmediata
        order_queue.put(payload)
        print("📩 Señal recibida y encolada:", payload)
        return jsonify({"status": "ok", "msg": "Orden encolada"}), 200

    except Exception as e:
        print("❌ Error en /webhook:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500

# Iniciar hilos al arrancar la app (si no están arrancados)
def ensure_background_threads():
    global connect_thread
    if connect_thread is None or not connect_thread.is_alive():
        connect_thread = Thread(target=connect_loop, daemon=True)
        connect_thread.start()
    # start order worker(s)
    worker = Thread(target=order_worker, daemon=True)
    worker.start()

# Si se ejecuta directamente (modo debug o local), arrancar la app y threads
if __name__ == "__main__":
    ensure_background_threads()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
else:
    # cuando Gunicorn importa el app, arrancar los hilos también
    ensure_background_threads()
            
