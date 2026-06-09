import urllib.request
import json
import os

URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

def extraer_codigo(respuesta_llm):
    if "```python" in respuesta_llm:
        partes = respuesta_llm.split("```python")
        if len(partes) > 1 and "```" in partes[1]:
            return partes[1].split("```")[0].strip()
    elif "```" in respuesta_llm:
        partes = respuesta_llm.split("```")
        if len(partes) > 1:
            return partes[1].strip()
    return respuesta_llm.strip()

def refactorizar_con_ollama(ruta_archivo_entrada, ruta_archivo_salida):
    if not os.path.exists(ruta_archivo_entrada):
        print(f"Error: El archivo {ruta_archivo_entrada} no existe.")
        return

    with open(ruta_archivo_entrada, "r", encoding="utf-8") as f:
        codigo_malo = f.read()

    print(f"Leyendo '{ruta_archivo_entrada}'...")
    print(f"Contactando API local de Ollama ({MODEL})...")
    
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Eres un experto en refactorizacion de codigo Python. Devuelve SOLO el codigo refactorizado dentro de un bloque ```python ... ```, sin explicaciones ni texto adicional."
            },
            {
                "role": "user",
                "content": f"Refactoriza este codigo que tiene un Code Smell para cumplir con el principio de responsabilidad unica:\n\n```python\n{codigo_malo}\n```"
            }
        ],
        "options": {
            "temperature": 0.2
        },
        "stream": False
    }
    
    req = urllib.request.Request(URL, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            texto_crudo = response_data['message']['content']
            
            codigo_limpio = extraer_codigo(texto_crudo)
            
            with open(ruta_archivo_salida, "w", encoding="utf-8") as f_out:
                f_out.write(codigo_limpio)
                
            print("\n--- RESPUESTA PROCESADA ---")
            print(f"El codigo refactorizado se guardo exitosamente en: '{ruta_archivo_salida}'")
            print("\nVista previa del codigo limpio:\n")
            print(codigo_limpio)
            
    except Exception as e:
        if hasattr(e, 'read'):
            print(f"\nError de API Ollama: {e} - {e.read().decode('utf-8')}")
        else:
            print(f"\nError al conectar con Ollama: {e}. Asegurate de que Ollama este ejecutandose de fondo (el icono en la barra de tareas).")

if __name__ == "__main__":
    archivo_entrada = "codigo_malo.py"
    archivo_salida = "codigo_refactorizado_ollama.py"
    refactorizar_con_ollama(archivo_entrada, archivo_salida)
