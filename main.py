import os
import requests
from google import genai
from google.genai import types
from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# --- 1. CONFIGURACIÓN DE CLIENTES Y TOKENS ---
# Inicializa el cliente de Gemini (detecta automáticamente GEMINI_API_KEY)
client = genai.Client()

# Token de Telegram configurado en Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- 2. INSTRUCCIONES PARA GEMINI ---
INSTRUCCIONES_SISTEMA = """
Eres un asistente experto en finanzas personales y gestión de gastos del hogar, diseñado específicamente para Santiago y Yoly. Tu objetivo es procesar mensajes de texto de comprobantes que ellos te envíen por WhatsApp o Telegram, extraer la información financiera relevante y estructurarla estrictamente en formato JSON.

CRITERIOS DE PROCESAMIENTO:
1. Analiza el gasto descrito en el texto.
2. Categoriza el gasto en: Alimentación, Salud, Transporte, Servicios Públicos, Entretenimiento, Compras Hogar, Educación, Otros.
3. Extrae la fecha (DD/MM/AAAA) y hora (HH:MM). Si no se indica, usa la fecha y hora proporcionada en el contexto del mensaje.
4. Identifica el método de pago (Efectivo, Tarjeta de Crédito, Tarjeta de Débito, Yape, Plin). Si no se menciona, colócalo como "Por clasificar".
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

def procesar_texto_gemini(mensaje_texto: str) -> str:
    ahora = datetime.now()
    contexto_temporal = f"Contexto de envío - Fecha: {ahora.strftime('%d/%m/%Y')} | Hora: {ahora.strftime('%H:%M')}."
    contenido = f"{contexto_temporal}\nMensaje del usuario: {mensaje_texto}"
    
    try:
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
    """Envía la respuesta de vuelta al chat de Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": texto_respuesta
    }
    try:
        respuesta = requests.post(url, json=data)
        print(f"Respuesta de Telegram: {respuesta.json()}")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")


# --- 3. RUTAS DEL SERVIDOR WEB ---
@app.route('/', methods=['GET'])
def home():
    return "¡El Bot de Gastos de Telegram está activo!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Ruta que recibe las alertas de nuevos mensajes desde Telegram"""
    data = request.json
    
    try:
        # Estructura nativa de un mensaje de texto en Telegram
        if 'message' in data and 'text' in data['message']:
            chat_id = data['message']['chat']['id']
            texto_recibido = data['message']['text']
            
            # Evitamos procesar comandos de inicio del bot
            if texto_recibido.startswith('/'):
                enviar_mensaje_telegram(chat_id, "¡Hola! Envíame cualquier gasto (Ej: 'Menú 15 soles yape') y lo registraré automáticamente.")
                return jsonify({"status": "success"}), 200
                
            # 1. Pasar el texto por Gemini para que lo estructure
            respuesta_json = procesar_texto_gemini(texto_recibido)
            
            # 2. Enviar los datos limpios a Google Sheets
            sheets_url = os.environ.get("SHEETS_URL")
            if sheets_url:
                try:
                    datos_limpios = json.loads(respuesta_json)
                    res_sheets = requests.post(sheets_url, json=datos_limpios)
                    print(f"Respuesta Sheets: {res_sheets.text}")
                except Exception as sheet_err:
                    print(f"Error al guardar en Sheets: {sheet_err}")
                    
            # 3. Responder confirmación al usuario en Telegram
            enviar_mensaje_telegram(chat_id, f"✅ Gasto procesado:\n{respuesta_json}")
            
    except Exception as e:
        print(f"Error general en webhook: {e}")
        
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
