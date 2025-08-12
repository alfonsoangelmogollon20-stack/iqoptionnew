import os
import time
import traceback
from threading import Thread, Lock
from queue import Queue
from flask import Flask, request, jsonify

# IMPORT: asegúrate en requirements.txt de tener iqoptionapi desde GitHub
from iqoptionapi.stable_api import IQ_Option

app = Flask(__name__)

# Credenciales desde env vars
IQ_USERNAME = os.getenv("IQ_USERNAME")
IQ_PASSWORD = os.getenv("IQ_PASSWORD")

api = None
api_lock = Lock()
order_queue = Queue()
connected_flag = False

def try_connect_once():
    """
    Intenta conectar una vez y devuelve (ok_bool, message, profile_or_none, exception_text_or_none)
    """
    global api, connected_flag
    if not IQ_USERNAME or not IQ_PASSWORD:
        return False, "Credenciales no definidas (IQ_USERNAME / IQ_PASSWORD)", None, None

    try:
        tmp = IQ_Option(IQ_USERNAME, IQ_PASSWORD)
        # connect() puede devolver True/False o None; también puede lanzar excepciones
        try:
            res = tmp.connect()
        except Exception as e:
            res = None
            ex_text = traceback.format_exc()
            return False, f"connect() lanzó excepción: {e}", None, ex_text

        # comprobar varias veces check_connect
        for i in range(10):
            try:
                ok = tmp.check_connect()
            except Exception as e:
                ok = False
                ex_text = traceback.format_exc()
                return False, f"check_connect() lanzó excepción: {e}", None, ex_text

            if ok:
                try:
                    tmp.change_balance("PRACTICE")
                except Exception:
                    pass
                profile = None
                try:
                    profile = tmp.get_profile()
                except Exception:
                    profile = None
                # asignar global api
                with api_lock:
                    api = tmp
                    connected_flag = True
                return True, "Conectado correctamente", profile, None
            time.sleep(1)

        # si no se conectó
        return False, "check_connect() nunca fue True (timeout)", None, None

    except Exception as e:
        ex_text = traceback.format_exc()
        return False, f"Excepción en try_connect_once: {e}", None, ex_text

def connect_loop_background():
    """
    Hilo que mantiene la conexión: intenta reconectar cuando se pierde.
    """
    global api, connected_flag
    while True:
        ok, msg, profile, ex = try_connect_once()
        print("connect_loop:", ok, msg)
        if ok:
            # permanecer hasta que la conexión se pierda
            while True:
                with api_lock:
                    tmp = api
                try:
                    if not tmp or not tmp.check_connect():
                        print("connect_loop: conexión perdida.")
                        with api_lock:
                            api = None
                            connected_flag = False
                        break
                except Exception as e:
                    print("connect_loop: check_connect lanzó excepción:", e)
                    with api_lock:
                        api = None
                        connected_flag = False
                    break
                time.sleep(2)
        else:
            if ex:
                print("connect_loop: detalle excepción:\n", ex)
            print("connect_loop: esperando 5s antes de reintentar...")
            time.sleep(5)

# Worker simple que manda órdenes (consumidor de cola)
def order_worker():
    global api
    while True:
        data = order_queue.get()
        try:
            symbol = data.get("symbol")
            direction = data.get("direction")
            amount = float(data.get("amount", 10))
            expiration = int(data.get("expiration", 5))

            print("Order worker: intentando enviar:", symbol, direction, amount, expiration)
            # esperar hasta que haya conexión (timeout 30s)
            waited = 0
            while True:
                with api_lock:
                    tmp = api
                if tmp and tmp.check_connect():
                    break
                time.sleep(1)
                waited += 1
                if waited >= 30:
                    print("Order worker: timeout esperando conexión; descartando orden.")
                    tmp = None
                    break

            if tmp:
                try:
                    ok, order_id = tmp.buy(amount, symbol, direction, expiration)
                    print("Order worker: buy returned:", ok, order_id)
                except Exception as e:
                    print("Order worker: exception al buy:", traceback.format_exc())
            else:
                print("Order worker: no había conexión, orden no enviada.")
        except Exception as e:
            print("Order worker: excepción:", traceback.format_exc())
        finally:
            order_queue.task_done()

# Endpoints

@app.route("/")
def home():
    return jsonify({"status": "ok", "connected": connected_flag}), 200

@app.route("/status")
def status():
    info = {"connected": connected_flag}
    try:
        with api_lock:
            tmp = api
        if tmp and tmp.check_connect():
            try:
                profile = tmp.get_profile()
                info["profile"] = {"id": profile.get("id"), "id2": profile.get("id2")} if profile else None
            except Exception:
                info["profile"] = "error al obtener profile"
        else:
            info["profile"] = None
    except Exception as e:
        info["error"] = str(e)
    return jsonify(info), 200

@app.route("/debug-connect", methods=["POST","GET"])
def debug_connect():
    """
    Forzar intento de conexión inmediato y devolver resultado detallado.
    """
    ok, msg, profile, ex = try_connect_once()
    resp = {"ok": ok, "message": msg}
    if profile:
        resp["profile"] = profile
    if ex:
        resp["exception"] = ex
    return jsonify(resp), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json() or {}
    symbol = data.get("symbol")
    direction = data.get("direction")
    expiration = int(data.get("expiration", 5))

    if not symbol or direction not in ("call","put"):
        return jsonify({"status":"error","msg":"payload inválido: symbol y direction(call|put) required"}), 400

    # Si no hay conexión, avisar (no encolamos si no hay conexión)
    if not connected_flag:
        return jsonify({"status":"error","msg":"Bot no conectado a IQ Option (intente /debug-connect)"}), 503

    payload = {"symbol": symbol, "direction": direction, "amount": 10, "expiration": expiration}
    order_queue.put(payload)
    print("Webhook: orden encolada:", payload)
    return jsonify({"status":"ok","msg":"Orden encolada"}), 200

# arrancar hilos background
if __name__ == "__main__":
    # lanzar hilo de conexión persistente
    t_conn = Thread(target=connect_loop_background, daemon=True)
    t_conn.start()
    # lanzar worker de órdenes
    t_worker = Thread(target=order_worker, daemon=True)
    t_worker.start()
    # arrancar Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
else:
    t_conn = Thread(target=connect_loop_background, daemon=True)
    t_conn.start()
    t_worker = Thread(target=order_worker, daemon=True)
    t_worker.start()
