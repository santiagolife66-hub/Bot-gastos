import os
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- 1. CONFIGURACIÓN DE CLAVES API ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Estas dos variables las sacaremos de Meta en el siguiente paso
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

# --- 2. INSTRUCCIONES PARA GEMINI ---
INSTRUCCIONES_SISTEMA = """
Eres un asistente experto en finanzas personales y gestión de gastos del hogar, diseñado específicamente para Santiago y Yoly. Tu objetivo es procesar mensajes de texto de comprobantes que ellos te envíen por WhatsApp, extraer la información financiera relevante y estructurarla estrictamente en formato JSON.

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
    modelo = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=INSTRUCCIONES_SISTEMA,
        generation_config=genai.GenerationConfig(response_mime_type="application/json")
    )
    ahora = datetime.now()
    contexto_temporal = f"Contexto de envío - Fecha: {ahora.strftime('%d/%m/%Y')} | Hora: {ahora.strftime('%H:%M')}."
    contenido = [f"{contexto_temporal}\nMensaje del usuario: {mensaje_texto}"]
    
    try:
        respuesta = modelo.generate_content(contenido)
        return respuesta.text
    except Exception as e:
        return f'{{"error": "Fallo en Gemini: {str(e)}"}}'

def enviar_mensaje_whatsapp(numero_destino: str, texto_respuesta: str):
    """Envía la respuesta de vuelta al usuario por WhatsApp"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto_respuesta}
    }
    respuesta = requests.post(url, headers=headers, json=data)
    # Esto imprimirá la respuesta exacta de Meta en los logs de Render
    print(f"Respuesta de Meta: {respuesta.json()}") 


# --- 3. RUTAS DEL SERVIDOR WEB ---
@app.route('/', methods=['GET'])
def home():
    return "¡El bot está activo y conectado a WhatsApp!"

@app.route('/webhook', methods=['GET', 'POST'])
# ... (dentro de @app.route('/webhook', methods=['GET', 'POST']))

# Si envías texto
if mensaje['type'] == 'text':
    texto_recibido = mensaje['text']['body']
    respuesta_json = procesar_texto_gemini(texto_recibido)
    
    # [NUEVO]: Enviar datos a Google Sheets si la URL está configurada
    sheets_url = os.environ.get("SHEETS_URL")
    if sheets_url:
        try:
            import json
            datos_limpios = json.loads(respuesta_json)
            # Enviamos el JSON directamente a tu Google Sheets
            requests.post(sheets_url, json=datos_limpios)
        except Exception as sheet_err:
            print(f"Error al guardar en Sheets: {sheet_err}")
            
    # Enviar confirmación por WhatsApp
    enviar_mensaje_whatsapp(numero_remitente, respuesta_json)


def webhook():
    # Verificación inicial de Meta
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "mi_token_secreto":
            return challenge, 200
        return "Token inválido", 403
                
    # Recepción de mensajes de WhatsApp
    if request.method == 'POST':
        data = request.json
        try:
            if 'object' in data and data['object'] == 'whatsapp_business_account':
                entry = data['entry'][0]
                changes = entry['changes'][0]
                value = changes['value']
                
                # Verificar si es un mensaje (y no un check azul de lectura)
                if 'messages' in value:
                    mensaje = value['messages'][0]
                    numero_remitente = mensaje['from']
                    
                    # Si envías texto
                    if mensaje['type'] == 'text':
                        texto_recibido = mensaje['text']['body']
                        respuesta_json = procesar_texto_gemini(texto_recibido)
                        enviar_mensaje_whatsapp(numero_remitente, respuesta_json)
                        
                    # Si envías una imagen (Dejamos esto preparado para el futuro)
                    elif mensaje['type'] == 'image':
                        enviar_mensaje_whatsapp(numero_remitente, "Recibí la foto. La función de imágenes requiere unos permisos más. ¡Por ahora probemos enviando el gasto en texto!")
                        
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            
        return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
