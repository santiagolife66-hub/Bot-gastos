import os
import requests
from google import genai
from google.genai import types
from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# --- 1. CONFIGURACIÓN DE CLIENTES Y TOKENS ---
client = genai.Client()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- 2. INSTRUCCIONES PARA GEMINI ---
INSTRUCCIONES_SISTEMA = """
Eres un asistente experto en finanzas personales y gestión de gastos del hogar, diseñado específicamente para Santiago y Yoly. Tu objetivo es procesar mensajes de texto o imágenes de comprobantes (vouchers, boletas, capturas de Yape/Plin) que ellos te envíen, extraer la información financiera relevante y estructurarla estrictamente en formato JSON.

CRITERIOS DE PROCESAMIENTO:
1. Analiza el gasto descrito en el texto o visible en la imagen del comprobante.
2. Categoriza el gasto en: Alimentación, Salud, Transporte, Servicios Públicos, Entretenimiento, Compras Hogar, Educación, Otros.
3. Extrae la fecha (DD/MM/AAAA) y hora (HH:MM). Si no se indica o no es visible en la imagen, usa la fecha y hora proporcionada en el contexto del mensaje.
4. Identifica el método de pago (Efectivo, Tarjeta de Crédito, Tarjeta de Débito, Yape, Plin). Si no se menciona ni se ve, colócalo como "Por clasificar".
5. Determina el monto total como un número decimal.

Estructura del JSON:
{
  "comprador": "[Santiago o Yoly]",
  "fecha": "DD/MM/AAAA",
  "hora": "HH:MM",
  "proveedor": "[Nombre del establecimiento o empresa]",
  "monto": 0.00,
  "categoria": "[Categoría asignada]",
  "metodo_pago": "[Método de pago identificado]",
  "descripcion": "[Breve detalle de lo que se compró o pagó]"
}
"""

def procesar_con_gemini(contenido_datos, es_imagen=False) -> str:
    ahora = datetime.now()
    contexto_temporal = f"Contexto de envío - Fecha: {ahora.strftime('%d/%m/%Y')} | Hora: {ahora.strftime('%H:%M')}."
    
    try:
        if es_imagen:
            # Si es imagen, pasamos los bytes de la foto junto con el texto de contexto
            contenido = [
                types.Part.from_bytes(data=contenido_datos, mime_type="image/jpeg"),
                f"{contexto_temporal}\nAnaliza este comprobante visual y extrae los datos del gasto."
            ]
        else:
            # Si es texto normal
            contenido = f"{contexto_temporal}\nMensaje del usuario: {contenido_datos}"
            
        respuesta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contenido,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCCIONES_SISTEMA,
                response_mime_type="application/json"
            )
        )
        return respuesta.text
    except Exception as e:
        return f'{{"error": "Fallo en Gemini: {str(e)}"}}'

def enviar_mensaje_telegram(chat_id: int, texto_respuesta: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": texto_respuesta}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Error al enviar a Telegram: {e}")

def obtener_bytes_imagen_telegram(file_id: str) -> bytes:
    """Descarga la foto desde los servidores de Telegram y devuelve sus bytes"""
    url_info = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    res_info = requests.get(url_info).json()
    
    if res_info.get("ok"):
        file_path = res_info["result"]["file_path"]
        url_descarga = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        res_foto = requests.get(url_descarga)
        return res_foto.content
    return b""


# --- 3. RUTAS DEL SERVIDOR WEB ---
@app.route('/', methods=['GET'])
def home():
    return "¡El Bot de Gastos de Telegram está activo y soporta imágenes!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    try:
        if 'message' in data:
            chat_id = data['message']['chat']['id']
            texto_recibido = data['message'].get('text')
            
            # CASO 1: Es un mensaje de texto normal u orden de inicio
            if texto_recibido:
                if texto_recibido.startswith('/'):
                    enviar_mensaje_telegram(chat_id, "¡Hola! Envíame un texto (Ej: 'Cena 45 soles yape') o la FOTO de un comprobante y lo registraré en el acto.")
                    return jsonify({"status": "success"}), 200
                
                respuesta_json = procesar_con_gemini(texto_recibido, es_imagen=False)
                
            # CASO 2: El usuario envió una IMAGEN/FOTO
            elif 'photo' in data['message']:
                enviar_mensaje_telegram(chat_id, "📷 Leyendo la imagen del comprobante... dame un momento.")
                
                # Telegram envía varias resoluciones, la última [-1] es la de mejor calidad
                file_id = data['message']['photo'][-1]['file_id']
                bytes_foto = obtener_bytes_imagen_telegram(file_id)
                
                if bytes_foto:
                    respuesta_json = procesar_con_gemini(bytes_foto, es_imagen=True)
                else:
                    enviar_mensaje_telegram(chat_id, "❌ No pude descargar la imagen de Telegram.")
                    return jsonify({"status": "success"}), 200
            else:
                return jsonify({"status": "success"}), 200

            # GUARDAR LOS DATOS EN GOOGLE SHEETS
            sheets_url = os.environ.get("SHEETS_URL")
            if sheets_url and "error" not in respuesta_json:
                try:
                    datos_limpios = json.loads(respuesta_json)
                    requests.post(sheets_url, json=datos_limpios)
                except Exception as sheet_err:
                    print(f"Error al guardar en Sheets: {sheet_err}")
                    
            # RESPONDER CONFIRMACIÓN EN TELEGRAM
            enviar_mensaje_telegram(chat_id, f"✅ Gasto procesado:\n{respuesta_json}")
            
    except Exception as e:
        print(f"Error general en webhook: {e}")
        
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
