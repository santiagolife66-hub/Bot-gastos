import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from datetime import datetime

# 1. Inicializar la aplicación web Flask
app = Flask(__name__)

# 2. Configurar la clave API usando las variables de entorno de Render
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# 3. Instrucciones del Sistema
INSTRUCCIONES_SISTEMA = """
Eres un asistente experto en finanzas personales y gestión de gastos del hogar, diseñado específicamente para Santiago y Yoly. Tu objetivo es procesar mensajes de texto o imágenes de comprobantes (boletas, facturas, recibos, capturas de pantalla) que ellos te envíen por WhatsApp, extraer la información financiera relevante y estructurarla estrictamente en formato JSON.

CRITERIOS DE PROCESAMIENTO:
1. Si recibes un texto, analiza el gasto descrito.
2. Si recibes una imagen, realiza un reconocimiento óptico de caracteres (OCR) preciso.
3. Categoriza el gasto en: Alimentación, Salud, Transporte, Servicios Públicos, Entretenimiento, Compras Hogar, Educación, Otros.
4. Extrae la fecha (DD/MM/AAAA) y hora (HH:MM). Si no se indica, usa la fecha y hora proporcionada en el contexto del mensaje.
5. Identifica el método de pago (Efectivo, Tarjeta de Crédito, Tarjeta de Débito, Yape, Plin). Si no se menciona ni se ve, colócalo como "Por clasificar".
6. Determina el monto total como un número decimal.

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

def procesar_gasto_whatsapp(usuario: str, mensaje_texto: str, ruta_imagen: str = None) -> str:
    modelo = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=INSTRUCCIONES_SISTEMA,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )

    ahora = datetime.now()
    contexto_temporal = f"Contexto de envío - Fecha: {ahora.strftime('%d/%m/%Y')} | Hora: {ahora.strftime('%H:%M')}."

    contenido = [f"Usuario: {usuario}\n{contexto_temporal}\nMensaje del usuario: {mensaje_texto}"]

    # (Lógica de imagen comentada temporalmente hasta conectar con WhatsApp)
    
    try:
        respuesta = modelo.generate_content(contenido)
        return respuesta.text
    except Exception as e:
         return f'{{"error": "Fallo en la generación de la API: {str(e)}"}}'

# --- RUTAS DEL SERVIDOR WEB ---

# Ruta de prueba para saber si el servidor está vivo
@app.route('/', methods=['GET'])
def home():
    return "¡El bot de gastos está activo y funcionando correctamente!"

# Ruta Webhook donde WhatsApp enviará los mensajes
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # WhatsApp usa GET para verificar la conexión la primera vez
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        # Este token ("mi_token_secreto") lo usaremos luego en Meta for Developers
        if mode and token:
            if mode == "subscribe" and token == "mi_token_secreto":
                return challenge, 200
            else:
                return "Token inválido", 403
                
    # WhatsApp usa POST para enviar los mensajes entrantes
    if request.method == 'POST':
        # Por ahora solo respondemos que recibimos el mensaje para que Render y WhatsApp estén felices
        # Más adelante conectaremos la función "procesar_gasto_whatsapp" aquí dentro
        data = request.json
        return jsonify({"status": "success", "message": "Mensaje recibido"}), 200

if __name__ == "__main__":
    # Gunicorn se encargará de ejecutar esto en Render
    app.run(host='0.0.0.0', port=5000)
    try:
        respuesta = modelo.generate_content(contenido)
        return respuesta.text
    except Exception as e:
         return f'{{"error": "Fallo en la generación de la API: {str(e)}"}}'

# ==========================================
# PRUEBAS DE EJECUCIÓN DEL CÓDIGO
# ==========================================
if __name__ == "__main__":
    
    # Prueba 1: Gasto en texto simple
    print("--- PRUEBA 1: TEXTO ---")
    json_resultado_texto = procesar_gasto_whatsapp(
        usuario="Santiago",
        mensaje_texto="Me acabo de comprar el menú de hoy por 45 soles. Lo pasé por Yape."
    )
    print(json_resultado_texto)

    # Prueba 2: Gasto con imagen (Simulado)
    # Para probar esto, descomenta las líneas inferiores y asegúrate de tener una imagen real
    # print("\n--- PRUEBA 2: IMAGEN ---")
    # json_resultado_imagen = procesar_gasto_whatsapp(
    #     usuario="Yoly",
    #     mensaje_texto="Aquí está el recibo de las compras para la casa en el súper.",
    #     ruta_imagen="./boleta_supermercado.jpg"
    # )
    # print(json_resultado_imagen)

