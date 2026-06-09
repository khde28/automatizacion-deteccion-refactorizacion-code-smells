import os
import urllib.request
import json

API_KEY = "AIzaSyBjZsR7diOtxPC3nAQT4g759FkwiqQ1Bxg"
MODEL = "gemini-flash-latest"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SMELL_LONG_FUNCTION = """
def procesar_datos_usuario(usuario):
    if not usuario:
        print("Error: Usuario vacio")
        return
    if usuario.get("edad", 0) < 18:
        print("Error: Menor de edad")
        return
        
    total_puntos = 0
    for punto in usuario.get("historial", []):
        total_puntos += punto
        
    promedio = 0
    if len(usuario.get("historial", [])) > 0:
        promedio = total_puntos / len(usuario["historial"])
        
    reporte = f"Usuario: {usuario.get('nombre', 'N/A')}\n"
    reporte += f"Total: {total_puntos}\n"
    reporte += f"Promedio: {promedio}\n"
    
    with open("reporte.txt", "w") as f:
        f.write(reporte)
        
    print("Datos procesados con exito.")
"""

SMELL_EXCESSIVE_PARAMETERS = """
def crear_perfil_cliente(nombre, apellido, email, telefono, calle, ciudad, estado, codigo_postal, pais):
    perfil = {
        "nombre_completo": f"{nombre} {apellido}",
        "contacto": {
            "email": email,
            "telefono": telefono
        },
        "direccion": {
            "calle": calle,
            "ciudad": ciudad,
            "estado": estado,
            "zip": codigo_postal,
            "pais": pais
        }
    }
    print(f"Perfil de {perfil['nombre_completo']} creado.")
    return perfil
"""

SMELL_DUPLICATED_CODE = """
def registrar_error_bd(mensaje):
    fecha = "2023-10-27"
    log = f"[{fecha}] ERROR_BD: {mensaje}"
    print(f"Escribiendo en logs: {log}")
    with open("errores.log", "a") as f:
        f.write(log + "\n")

def registrar_error_red(mensaje):
    fecha = "2023-10-27"
    log = f"[{fecha}] ERROR_RED: {mensaje}"
    print(f"Escribiendo en logs: {log}")
    with open("errores.log", "a") as f:
        f.write(log + "\n")
"""

EJEMPLOS_LONG_FUNCTION = [
    {
        "bad": "def hacer_cafe():\n    print('Hirviendo agua')\n    print('Moliendo granos')\n    print('Sirviendo agua')\n    print('Anadiendo leche')\n    print('Anadiendo azucar')",
        "good": "def preparar_agua():\n    print('Hirviendo agua')\n    print('Sirviendo agua')\n\ndef agregar_ingredientes():\n    print('Moliendo granos')\n    print('Anadiendo leche')\n    print('Anadiendo azucar')\n\ndef hacer_cafe():\n    preparar_agua()\n    agregar_ingredientes()",
        "explanation": "Se dividio la funcion en metodos mas pequenos y enfocados."
    },
    {
        "bad": "def calcular_e_imprimir_total(items):\n    total = 0\n    for i in items:\n        total += i.precio\n    print('Factura:')\n    for i in items:\n        print(i.nombre)\n    print(f'Total: {total}')",
        "good": "def calcular_total(items):\n    return sum(i.precio for i in items)\n\ndef imprimir_factura(items, total):\n    print('Factura:')\n    for i in items:\n        print(i.nombre)\n    print(f'Total: {total}')\n\ndef calcular_e_imprimir_total(items):\n    total = calcular_total(items)\n    imprimir_factura(items, total)",
        "explanation": "Se separo la logica de calculo y la de impresion en funciones distintas."
    }
]

EJEMPLOS_EXCESSIVE_PARAMETERS = [
    {
        "bad": "def dibujar_rectangulo(x, y, ancho, alto, color, grosor_borde):\n    pass",
        "good": "def dibujar_rectangulo(posicion, dimensiones, estilo):\n    pass",
        "explanation": "Se agruparon los parametros en objetos representativos."
    },
    {
        "bad": "def enviar_correo(destinatario, remitente, asunto, cuerpo, cc, bcc, es_html):\n    pass",
        "good": "def enviar_correo(configuracion_correo):\n    pass",
        "explanation": "Se introdujo un objeto Data Class para encapsular atributos."
    }
]

EJEMPLOS_DUPLICATED_CODE = [
    {
        "bad": "def imprimir_usuario(u):\n    print('Nombre:', u.nombre)\n    print('Edad:', u.edad)\n\ndef imprimir_admin(a):\n    print('Nombre:', a.nombre)\n    print('Edad:', a.edad)\n    print('Rol: Admin')",
        "good": "def imprimir_persona(p):\n    print('Nombre:', p.nombre)\n    print('Edad:', p.edad)\n\ndef imprimir_usuario(u):\n    imprimir_persona(u)\n\ndef imprimir_admin(a):\n    imprimir_persona(a)\n    print('Rol: Admin')",
        "explanation": "Se extrajo la logica comun de impresion a una funcion base."
    },
    {
        "bad": "def cobro_tarjeta(monto):\n    print('Verificando')\n    print(f'Cobrando {monto} con Tarjeta')\n\ndef cobro_paypal(monto):\n    print('Verificando')\n    print(f'Cobrando {monto} con PayPal')",
        "good": "def procesar_cobro(monto, metodo):\n    print('Verificando')\n    print(f'Cobrando {monto} con {metodo}')\n\ndef cobro_tarjeta(monto):\n    procesar_cobro(monto, 'Tarjeta')\n\ndef cobro_paypal(monto):\n    procesar_cobro(monto, 'PayPal')",
        "explanation": "Se parametrizo la diferencia en una funcion reutilizable."
    }
]

def refactor_with_few_shot(codigo_malo, ejemplos, tipo_smell):
    contents = []
    
    for ej in ejemplos:
        contents.append({
            "role": "user",
            "parts": [{"text": f"Por favor refactoriza este codigo que tiene el smell '{tipo_smell}':\n\n```python\n{ej['bad']}\n```"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": f"CODIGO REFACTORIZADO:\n```python\n{ej['good']}\n```\n\nEXPLICACION:\n{ej['explanation']}"}]
        })
        
    contents.append({
        "role": "user",
        "parts": [{"text": f"Por favor refactoriza este codigo que tiene el smell '{tipo_smell}':\n\n```python\n{codigo_malo}\n```"}]
    })
    
    data = {
        "system_instruction": {
            "parts": [{"text": "Eres un experto en refactorizacion de codigo Python. Tu objetivo es refactorizar el codigo para corregir el Code Smell especificado. Responde SIEMPRE con este formato exacto:\n\nCODIGO REFACTORIZADO:\n```python\n[Tu codigo aqui]\n```\n\nEXPLICACION:\n[Tu explicacion breve aqui]"}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.7,
            "maxOutputTokens": 1024
        }
    }
    
    req = urllib.request.Request(URL, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            return response_data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        if hasattr(e, 'read'):
            return f"Error de API: {e} - {e.read().decode('utf-8')}"
        return f"Error de API: {e}"

def probar_smell(nombre, codigo_original, ejemplos):
    print(f"\n{'='*60}")
    print(f"PROBANDO SMELL: {nombre.upper()}")
    print(f"{'='*60}")
    
    print("\n--- CODIGO ORIGINAL ---")
    print(codigo_original.strip())
    
    print(f"\nContactando API de Gemini ({MODEL})...")
    try:
        resultado = refactor_with_few_shot(codigo_original, ejemplos, nombre)
        
        print("\n--- RESPUESTA DEL LLM ---")
        print(resultado.strip())
        
        lineas_original = len([l for l in codigo_original.split('\n') if l.strip()])
        lineas_refactor = 0
        if "```python" in resultado and "```" in resultado.split("```python")[1]:
            codigo_generado = resultado.split("```python")[1].split("```")[0]
            lineas_refactor = len([l for l in codigo_generado.split('\n') if l.strip()])
        else:
            lineas_refactor = len([l for l in resultado.split('\n') if l.strip()])
            
        print("\n--- COMPARACION ---")
        print(f"Lineas de codigo original : {lineas_original}")
        print(f"Lineas de codigo nuevo    : {lineas_refactor}")
            
    except Exception as e:
        print(f"\nError durante la prueba: {e}")

if __name__ == "__main__":
    probar_smell("Long Function", SMELL_LONG_FUNCTION, EJEMPLOS_LONG_FUNCTION)
    probar_smell("Parametros Excesivos", SMELL_EXCESSIVE_PARAMETERS, EJEMPLOS_EXCESSIVE_PARAMETERS)
    probar_smell("Codigo Duplicado", SMELL_DUPLICATED_CODE, EJEMPLOS_DUPLICATED_CODE)
