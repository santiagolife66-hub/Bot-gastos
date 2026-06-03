import google.generativeai as genai
from datetime import datetime

# 1. Configurar la clave API de Google (Reemplaza con tu clave real o usa variables de entorno)
genai.configure(api_key="TU_API_KEY_AQUI")

# 2. Definir las instrucciones del sistema (System Prompt)
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
    """
    Procesa el mensaje de WhatsApp enviándolo a Gemini y retorna un JSON estructurado.
    """
    # Usamos Gemini 1.5 Flash por su rapidez, bajo costo y excelente soporte multimodal (texto + imágenes)
    modelo = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=INSTRUCCIONES_SISTEMA,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json" # Fuerza al modelo a devolver ÚNICAMENTE un JSON válido
        )
    )

    # Obtenemos la fecha y hora actuales del sistema para enviarlas como contexto
    ahora = datetime.now()
    contexto_temporal = f"Contexto de envío - Fecha: {ahora.strftime('%d/%m/%Y')} | Hora: {ahora.strftime('%H:%M')}."

    # Preparamos el payload con los metadatos y el mensaje del usuario
    contenido = [
        f"Usuario: {usuario}\n{contexto_temporal}\nMensaje del usuario: {mensaje_texto}"
    ]

    # Si se incluye una imagen del comprobante, la cargamos y la adjuntamos al payload
    if ruta_imagen:
        try:
            archivo_imagen = genai.upload_file(path=ruta_imagen)
            contenido.append(archivo_imagen)
        except Exception as e:
            return f'{{"error": "No se pudo cargar la imagen: {str(e)}"}}'

    # Generamos la respuesta
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

