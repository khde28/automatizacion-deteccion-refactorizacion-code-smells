"""
=============================================================================
 refactor_engine.py - Motor de Refactorización con Gemini (Google)
=============================================================================
 Primer Avance - Tesis Doctoral:
 "Refactorización automática de Code Smells mediante LLMs para la
  mitigación de la deuda técnica en proyectos de código abierto en Python"

 Descripción:
    Este módulo implementa el núcleo de la investigación: la refactorización
    automática de code smells usando el LLM Gemini de Google con la técnica
    de Few-Shot Prompting, a través del SDK oficial google-genai.

 Técnica de prompting utilizada:
    Few-Shot Prompting: Se proporcionan 2-3 ejemplos de "código con smell →
    código refactorizado" al LLM antes de presentar el código objetivo.
    Esto guía al modelo para que aplique patrones de refactorización
    consistentes y bien fundamentados.

 Referencia teórica:
    - Brown et al. (2020). Language Models are Few-Shot Learners. (GPT-3)
    - Wei et al. (2022). Chain-of-Thought Prompting.
    - Fan et al. (2023). Large Language Models for Software Engineering.
=============================================================================
"""

import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

# Cargar variables de entorno desde archivo .env
from dotenv import load_dotenv
load_dotenv()

# SDK oficial de Google Gemini
from google import genai
from google.genai import types


# =============================================================================
# Estructura para almacenar el resultado de la refactorización
# =============================================================================

@dataclass
class ResultadoRefactorizacion:
    """
    Almacena el resultado completo de una refactorización realizada por el LLM.
    
    Atributos:
        codigo_original: Código fuente antes de la refactorización.
        codigo_refactorizado: Código fuente después de la refactorización.
        explicacion: Explicación del LLM sobre qué smell se refactorizó y por qué.
        tipo_smell: Tipo de code smell que fue refactorizado.
        tecnica_aplicada: Técnica de refactorización utilizada.
        modelo_usado: Modelo LLM utilizado para la refactorización.
        tokens_usados: Cantidad de tokens consumidos en la llamada a la API.
        exitoso: Indica si la refactorización fue exitosa.
        error: Mensaje de error si la refactorización falló.
    """
    codigo_original: str = ""
    codigo_refactorizado: str = ""
    explicacion: str = ""
    tipo_smell: str = ""
    tecnica_aplicada: str = ""
    modelo_usado: str = ""
    tokens_usados: int = 0
    exitoso: bool = False
    error: str = ""


# =============================================================================
# Ejemplos Few-Shot para cada tipo de Code Smell
# =============================================================================
# Estos ejemplos enseñan al LLM el patrón de refactorización esperado.
# Cada ejemplo muestra un "antes" y "después" claro para que el modelo
# aprenda por analogía.

EJEMPLOS_FEW_SHOT = {
    # =========================================================================
    # Ejemplos para "Long Method" (Función Larga)
    # Técnica: Extract Method - dividir la función en subfunciones cohesivas
    # =========================================================================
    "Long Method": [
        {
            "codigo_malo": '''def procesar_pedido(pedido):
    # Validar pedido
    if not pedido.get("items"):
        raise ValueError("Pedido sin items")
    if not pedido.get("cliente_id"):
        raise ValueError("Pedido sin cliente")
    for item in pedido["items"]:
        if item["cantidad"] <= 0:
            raise ValueError(f"Cantidad inválida para {item['nombre']}")
    
    # Calcular totales
    subtotal = 0
    for item in pedido["items"]:
        precio = item["precio"] * item["cantidad"]
        if item.get("descuento"):
            precio -= precio * item["descuento"] / 100
        subtotal += precio
    impuesto = subtotal * 0.18
    total = subtotal + impuesto
    
    # Generar factura
    factura = {
        "cliente": pedido["cliente_id"],
        "items": pedido["items"],
        "subtotal": subtotal,
        "impuesto": impuesto,
        "total": total,
        "estado": "pendiente"
    }
    
    return factura''',
            "codigo_bueno": '''def procesar_pedido(pedido):
    """Procesa un pedido: valida, calcula totales y genera factura."""
    validar_pedido(pedido)
    subtotal, impuesto, total = calcular_totales(pedido["items"])
    return generar_factura(pedido["cliente_id"], pedido["items"],
                           subtotal, impuesto, total)


def validar_pedido(pedido):
    """Valida que el pedido tenga los campos requeridos y datos correctos."""
    if not pedido.get("items"):
        raise ValueError("Pedido sin items")
    if not pedido.get("cliente_id"):
        raise ValueError("Pedido sin cliente")
    for item in pedido["items"]:
        if item["cantidad"] <= 0:
            raise ValueError(f"Cantidad inválida para {item['nombre']}")


def calcular_totales(items):
    """Calcula subtotal, impuesto y total de una lista de items."""
    subtotal = sum(calcular_precio_item(item) for item in items)
    impuesto = subtotal * 0.18
    total = subtotal + impuesto
    return subtotal, impuesto, total


def calcular_precio_item(item):
    """Calcula el precio de un item aplicando descuento si existe."""
    precio = item["precio"] * item["cantidad"]
    if item.get("descuento"):
        precio -= precio * item["descuento"] / 100
    return precio


def generar_factura(cliente_id, items, subtotal, impuesto, total):
    """Genera el diccionario de factura con los datos procesados."""
    return {
        "cliente": cliente_id,
        "items": items,
        "subtotal": subtotal,
        "impuesto": impuesto,
        "total": total,
        "estado": "pendiente"
    }''',
            "explicacion": "Se aplicó 'Extract Method': la función monolítica se dividió en 4 funciones cohesivas (validar_pedido, calcular_totales, calcular_precio_item, generar_factura). Cada función tiene una responsabilidad única."
        },
        {
            "codigo_malo": '''def generar_reporte(datos, formato):
    resultados = []
    for d in datos:
        if d["tipo"] == "venta":
            monto = d["cantidad"] * d["precio"]
            if d.get("descuento"):
                monto = monto * (1 - d["descuento"])
            resultados.append({"tipo": "venta", "monto": monto})
        elif d["tipo"] == "devolucion":
            monto = -d["cantidad"] * d["precio"]
            resultados.append({"tipo": "devolucion", "monto": monto})
    
    total = sum(r["monto"] for r in resultados)
    
    if formato == "texto":
        lineas = []
        for r in resultados:
            lineas.append(f"{r['tipo']}: ${r['monto']:.2f}")
        lineas.append(f"Total: ${total:.2f}")
        return "\\n".join(lineas)
    elif formato == "json":
        import json
        return json.dumps({"resultados": resultados, "total": total})
    return str(resultados)''',
            "codigo_bueno": '''def generar_reporte(datos, formato):
    """Genera un reporte de transacciones en el formato especificado."""
    resultados = calcular_resultados(datos)
    total = sum(r["monto"] for r in resultados)
    return formatear_reporte(resultados, total, formato)


def calcular_resultados(datos):
    """Procesa los datos y calcula los montos de cada transacción."""
    return [procesar_transaccion(d) for d in datos]


def procesar_transaccion(dato):
    """Calcula el monto de una transacción individual."""
    monto = dato["cantidad"] * dato["precio"]
    if dato["tipo"] == "venta":
        if dato.get("descuento"):
            monto *= (1 - dato["descuento"])
        return {"tipo": "venta", "monto": monto}
    elif dato["tipo"] == "devolucion":
        return {"tipo": "devolucion", "monto": -monto}
    return {"tipo": dato["tipo"], "monto": monto}


def formatear_reporte(resultados, total, formato):
    """Formatea el reporte según el formato solicitado."""
    import json
    if formato == "texto":
        lineas = [f"{r['tipo']}: ${r['monto']:.2f}" for r in resultados]
        lineas.append(f"Total: ${total:.2f}")
        return "\\n".join(lineas)
    elif formato == "json":
        return json.dumps({"resultados": resultados, "total": total})
    return str(resultados)''',
            "explicacion": "Se aplicó 'Extract Method': se separó el cálculo de resultados, el procesamiento de transacciones individuales y el formateo del reporte en funciones independientes."
        }
    ],

    # =========================================================================
    # Ejemplos para "Long Parameter List" (Lista de Parámetros Excesiva)
    # Técnica: Introduce Parameter Object - agrupar parámetros en un objeto
    # =========================================================================
    "Long Parameter List": [
        {
            "codigo_malo": '''def crear_usuario(nombre, apellido, edad, email, telefono,
                   direccion, ciudad, pais, codigo_postal):
    return {
        "nombre_completo": f"{nombre} {apellido}",
        "edad": edad,
        "contacto": {"email": email, "telefono": telefono},
        "ubicacion": {
            "direccion": direccion,
            "ciudad": ciudad,
            "pais": pais,
            "codigo_postal": codigo_postal
        }
    }''',
            "codigo_bueno": '''from dataclasses import dataclass


@dataclass
class DatosPersonales:
    """Agrupa los datos personales del usuario."""
    nombre: str
    apellido: str
    edad: int


@dataclass
class DatosContacto:
    """Agrupa los datos de contacto del usuario."""
    email: str
    telefono: str


@dataclass
class DatosUbicacion:
    """Agrupa los datos de ubicación del usuario."""
    direccion: str
    ciudad: str
    pais: str
    codigo_postal: str


def crear_usuario(personales: DatosPersonales, contacto: DatosContacto,
                  ubicacion: DatosUbicacion):
    """Crea un usuario a partir de objetos de datos agrupados."""
    return {
        "nombre_completo": f"{personales.nombre} {personales.apellido}",
        "edad": personales.edad,
        "contacto": {"email": contacto.email, "telefono": contacto.telefono},
        "ubicacion": {
            "direccion": ubicacion.direccion,
            "ciudad": ubicacion.ciudad,
            "pais": ubicacion.pais,
            "codigo_postal": ubicacion.codigo_postal
        }
    }''',
            "explicacion": "Se aplicó 'Introduce Parameter Object': los 9 parámetros se agruparon en 3 dataclasses semánticas (DatosPersonales, DatosContacto, DatosUbicacion), reduciendo la firma a 3 parámetros."
        },
        {
            "codigo_malo": '''def enviar_email(remitente, destinatario, asunto, cuerpo,
                 cc, bcc, adjuntos, prioridad, formato_html):
    mensaje = {
        "from": remitente,
        "to": destinatario,
        "subject": asunto,
        "body": cuerpo,
        "cc": cc,
        "bcc": bcc,
        "attachments": adjuntos,
        "priority": prioridad,
        "html": formato_html
    }
    return mensaje''',
            "codigo_bueno": '''from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ConfiguracionEmail:
    """Configuración y opciones del email."""
    cc: Optional[str] = None
    bcc: Optional[str] = None
    adjuntos: List[str] = field(default_factory=list)
    prioridad: str = "normal"
    formato_html: bool = False


def enviar_email(remitente: str, destinatario: str, asunto: str,
                 cuerpo: str, config: ConfiguracionEmail = None):
    """Envía un email con la configuración especificada."""
    config = config or ConfiguracionEmail()
    return {
        "from": remitente,
        "to": destinatario,
        "subject": asunto,
        "body": cuerpo,
        "cc": config.cc,
        "bcc": config.bcc,
        "attachments": config.adjuntos,
        "priority": config.prioridad,
        "html": config.formato_html
    }''',
            "explicacion": "Se aplicó 'Introduce Parameter Object': los parámetros opcionales se agruparon en ConfiguracionEmail con valores por defecto, manteniendo solo los parámetros esenciales (remitente, destinatario, asunto, cuerpo) en la firma."
        }
    ],

    # =========================================================================
    # Ejemplos para "High Cyclomatic Complexity" y "Deep Nesting"
    # Técnicas: Guard Clauses, Replace Conditional with Polymorphism
    # =========================================================================
    "High Cyclomatic Complexity": [
        {
            "codigo_malo": '''def calcular_descuento(cliente, producto, cantidad, fecha):
    descuento = 0
    if cliente["tipo"] == "premium":
        if producto["categoria"] == "electronica":
            if cantidad > 10:
                descuento = 25
            elif cantidad > 5:
                descuento = 15
            else:
                descuento = 10
        elif producto["categoria"] == "ropa":
            if cantidad > 20:
                descuento = 20
            else:
                descuento = 8
        else:
            descuento = 5
    elif cliente["tipo"] == "regular":
        if producto["categoria"] == "electronica":
            if cantidad > 10:
                descuento = 10
            else:
                descuento = 5
        else:
            descuento = 3
    else:
        descuento = 0
    return descuento''',
            "codigo_bueno": '''# Tabla de descuentos: (tipo_cliente, categoría) -> función de descuento
TABLA_DESCUENTOS = {
    ("premium", "electronica"): lambda cant: 25 if cant > 10 else (15 if cant > 5 else 10),
    ("premium", "ropa"): lambda cant: 20 if cant > 20 else 8,
    ("premium", None): lambda cant: 5,
    ("regular", "electronica"): lambda cant: 10 if cant > 10 else 5,
    ("regular", None): lambda cant: 3,
}


def calcular_descuento(cliente, producto, cantidad, fecha):
    """Calcula el descuento usando una tabla de estrategias."""
    tipo = cliente["tipo"]
    categoria = producto["categoria"]
    
    clave = (tipo, categoria)
    estrategia = TABLA_DESCUENTOS.get(clave) or TABLA_DESCUENTOS.get((tipo, None))
    
    if estrategia is None:
        return 0
    
    return estrategia(cantidad)''',
            "explicacion": "Se aplicó 'Replace Conditional with Strategy/Table': las condiciones anidadas se reemplazaron con una tabla de búsqueda (diccionario) que mapea combinaciones de tipo de cliente y categoría a funciones de cálculo."
        }
    ],

    "Deep Nesting": [
        {
            "codigo_malo": '''def validar_formulario(datos):
    errores = []
    if datos:
        if "nombre" in datos:
            if len(datos["nombre"]) >= 2:
                if len(datos["nombre"]) <= 100:
                    pass
                else:
                    errores.append("Nombre muy largo")
            else:
                errores.append("Nombre muy corto")
        else:
            errores.append("Nombre requerido")
        
        if "email" in datos:
            if "@" in datos["email"]:
                if "." in datos["email"].split("@")[1]:
                    pass
                else:
                    errores.append("Email inválido")
            else:
                errores.append("Email sin @")
        else:
            errores.append("Email requerido")
    else:
        errores.append("Datos vacíos")
    return errores''',
            "codigo_bueno": '''def validar_formulario(datos):
    """Valida los datos del formulario usando Guard Clauses."""
    if not datos:
        return ["Datos vacíos"]
    
    errores = []
    errores.extend(validar_nombre(datos))
    errores.extend(validar_email(datos))
    return errores


def validar_nombre(datos):
    """Valida el campo nombre con retornos tempranos."""
    if "nombre" not in datos:
        return ["Nombre requerido"]
    if len(datos["nombre"]) < 2:
        return ["Nombre muy corto"]
    if len(datos["nombre"]) > 100:
        return ["Nombre muy largo"]
    return []


def validar_email(datos):
    """Valida el campo email con retornos tempranos."""
    if "email" not in datos:
        return ["Email requerido"]
    email = datos["email"]
    if "@" not in email:
        return ["Email sin @"]
    dominio = email.split("@")[1]
    if "." not in dominio:
        return ["Email inválido"]
    return []''',
            "explicacion": "Se aplicaron 'Guard Clauses' (retornos tempranos) y 'Extract Method': cada validación se extrajo a su propia función con retornos tempranos que eliminan la necesidad de anidamiento profundo."
        }
    ]
}


class MotorDeRefactorizacion:
    """
    Motor de refactorización que utiliza Gemini LLM con Few-Shot Prompting.
    
    Este es el componente central de la investigación. Toma un fragmento de
    código con un code smell identificado y genera una versión refactorizada
    usando la API de Gemini (Google) con ejemplos few-shot que guían al modelo.
    
    Utiliza el SDK oficial google-genai para la comunicación con la API,
    lo cual simplifica la autenticación, el manejo de errores y el
    formato de mensajes.
    
    La técnica Few-Shot Prompting proporciona al LLM ejemplos concretos de
    transformaciones de código, permitiéndole aprender el patrón de
    refactorización esperado por analogía.
    """

    def __init__(self):
        """
        Inicializa el motor de refactorización con el SDK de Gemini.
        
        Carga la API Key desde variables de entorno y configura el
        cliente oficial de Google GenAI. Usar el SDK oficial es más
        robusto que hacer llamadas REST directas, ya que maneja
        automáticamente reintentos, timeouts y formato de mensajes.
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.cliente = None

        # Validar que la API key esté configurada
        if not self.api_key or self.api_key == "tu_api_key_aqui":
            print("  ⚠ ADVERTENCIA: No se encontró una API Key válida de Gemini.")
            print("    Configura GEMINI_API_KEY en el archivo .env")
            print("    Obtén tu key GRATIS en: https://aistudio.google.com/apikey")
        else:
            # Inicializar el cliente del SDK de Gemini
            self.cliente = genai.Client(api_key=self.api_key)
            print(f"  ✓ Motor de refactorización inicializado (Gemini)")
            print(f"    Modelo: {self.modelo}")
            print(f"    SDK: google-genai (oficial)")

    def construir_conversacion_few_shot(self, codigo_smell: str, tipo_smell: str):
        """
        Construye la conversación completa con ejemplos few-shot para Gemini.
        
        El prompt sigue la estructura de Few-Shot Prompting:
        1. System instruction: establece el rol y las instrucciones
        2. Ejemplos (shots): pares de código malo → código bueno
        3. Consulta: el código real a refactorizar
        
        Usa el formato nativo del SDK de Gemini con types.Content y
        types.Part para construir la conversación multi-turno.

        Args:
            codigo_smell: Código fuente con el code smell identificado.
            tipo_smell: Tipo de code smell a refactorizar.

        Returns:
            Tupla (system_instruction, contents) para la llamada a Gemini.
        """
        # =====================================================================
        # 1. SYSTEM INSTRUCTION - Establece el rol y las instrucciones
        # =====================================================================
        system_instruction = (
            "Eres un ingeniero de software experto en refactorización de código Python. "
            "Tu especialidad es identificar y corregir code smells siguiendo los catálogos "
            "de refactorización de Martin Fowler (2018) y las prácticas de Clean Code de "
            "Robert C. Martin (2008).\n\n"
            "INSTRUCCIONES:\n"
            "1. Analiza el código proporcionado e identifica el code smell presente.\n"
            "2. Aplica la técnica de refactorización más apropiada.\n"
            "3. Genera el código refactorizado completo y funcional.\n"
            "4. Explica detalladamente:\n"
            "   - QUÉ code smell se refactorizó\n"
            "   - QUÉ técnica de refactorización se aplicó\n"
            "   - POR QUÉ esta refactorización mejora la calidad del código\n"
            "   - QUÉ métricas de calidad se mejoraron\n\n"
            "FORMATO DE RESPUESTA (respeta EXACTAMENTE este formato):\n"
            "```python\n"
            "# Código refactorizado aquí\n"
            "```\n\n"
            "EXPLICACIÓN:\n"
            "[Tu explicación detallada aquí]"
        )

        # =====================================================================
        # 2. EJEMPLOS FEW-SHOT - Enseñan al LLM el patrón esperado
        # =====================================================================
        ejemplos = EJEMPLOS_FEW_SHOT.get(tipo_smell, [])

        if not ejemplos:
            print(f"  ⚠ No hay ejemplos few-shot para '{tipo_smell}', usando Long Method")
            ejemplos = EJEMPLOS_FEW_SHOT.get("Long Method", [])

        # Construir la lista de contenidos (conversación multi-turno)
        contents = []

        # Agregar cada ejemplo como par user/model
        for ejemplo in ejemplos:
            # El "user" presenta el código con smell
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(
                        text=f"Refactoriza el siguiente código Python que tiene el smell "
                        f"'{tipo_smell}':\n\n"
                        f"```python\n{ejemplo['codigo_malo']}\n```"
                    )]
                )
            )
            # El "model" muestra la refactorización esperada
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(
                        text=f"```python\n{ejemplo['codigo_bueno']}\n```\n\n"
                        f"EXPLICACIÓN:\n{ejemplo['explicacion']}"
                    )]
                )
            )

        print(f"  ✓ Se incluyeron {len(ejemplos)} ejemplos few-shot para '{tipo_smell}'")

        # =====================================================================
        # 3. CONSULTA REAL - El código que el LLM debe refactorizar
        # =====================================================================
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text=f"Ahora refactoriza el siguiente código Python REAL extraído de un "
                    f"proyecto de código abierto. Se ha identificado el code smell "
                    f"'{tipo_smell}'.\n\n"
                    f"Código a refactorizar:\n"
                    f"```python\n{codigo_smell}\n```\n\n"
                    f"Recuerda:\n"
                    f"1. Genera el código refactorizado completo dentro de bloques ```python\n"
                    f"2. Explica QUÉ smell refactorizaste, QUÉ técnica aplicaste y POR QUÉ "
                    f"mejora el código.\n"
                    f"3. Asegúrate de que el código refactorizado sea funcional y mantenga "
                    f"la misma funcionalidad que el original."
                )]
            )
        )

        return system_instruction, contents

    def parsear_respuesta(self, texto_respuesta: str):
        """
        Extrae el código refactorizado y la explicación de la respuesta del LLM.
        
        Parsea el texto de respuesta de Gemini para separar el bloque de
        código Python de la explicación textual.

        Args:
            texto_respuesta: Texto completo de la respuesta de Gemini.

        Returns:
            Tupla (codigo_refactorizado, explicacion).
        """
        codigo_refactorizado = ""
        explicacion = ""

        if "```python" in texto_respuesta:
            # Extraer todos los bloques de código Python
            partes = texto_respuesta.split("```python")
            bloques_codigo = []

            for parte in partes[1:]:
                if "```" in parte:
                    bloque = parte.split("```")[0].strip()
                    bloques_codigo.append(bloque)

            codigo_refactorizado = "\n\n".join(bloques_codigo)

            # Buscar la sección de explicación
            ultima_parte = texto_respuesta.split("```")[-1].strip()
            if "EXPLICACIÓN:" in texto_respuesta.upper():
                for marcador in ["EXPLICACIÓN:", "EXPLICACION:", "Explicación:", "Explicacion:"]:
                    if marcador in texto_respuesta:
                        explicacion = texto_respuesta.split(marcador, 1)[1].strip()
                        if "```" in explicacion:
                            explicacion = explicacion.split("```")[0].strip()
                        break
            
            if not explicacion:
                explicacion = ultima_parte

        elif "```" in texto_respuesta:
            partes = texto_respuesta.split("```")
            if len(partes) >= 3:
                codigo_refactorizado = partes[1].strip()
                explicacion = partes[-1].strip()
        else:
            explicacion = texto_respuesta

        return codigo_refactorizado, explicacion

    def refactorizar(self, codigo_smell: str, tipo_smell: str) -> ResultadoRefactorizacion:
        """
        Método principal: refactoriza un fragmento de código usando Gemini.
        
        Orquesta el flujo completo de refactorización:
        1. Construye la conversación con ejemplos few-shot
        2. Llama a la API de Gemini via SDK oficial
        3. Parsea la respuesta
        4. Retorna el resultado estructurado

        Args:
            codigo_smell: Código fuente con el code smell a refactorizar.
            tipo_smell: Tipo de code smell identificado.

        Returns:
            ResultadoRefactorizacion con el código refactorizado y explicación.
        """
        resultado = ResultadoRefactorizacion(
            codigo_original=codigo_smell,
            tipo_smell=tipo_smell,
            modelo_usado=f"{self.modelo} (Gemini)"
        )

        # Verificar que el cliente esté inicializado
        if not self.cliente:
            resultado.error = (
                "API Key de Gemini no configurada. "
                "Configura GEMINI_API_KEY en el archivo .env"
            )
            print(f"  ✗ {resultado.error}")
            return resultado

        try:
            # Paso 1: Construir la conversación con few-shot examples
            print("\n  [Paso 1] Construyendo prompt con Few-Shot Prompting...")
            system_instruction, contents = self.construir_conversacion_few_shot(
                codigo_smell, tipo_smell
            )

            # Paso 2: Llamar a la API de Gemini usando el SDK oficial
            print(f"\n  [Paso 2] Llamando a Gemini ({self.modelo}) via SDK...")
            print(f"    Mensajes en la conversación: {len(contents)}")

            # Configuración de generación
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,         # Baja para respuestas determinísticas
                max_output_tokens=8192,  # Máximo de tokens en la respuesta
                top_p=0.9,               # Nucleus sampling
            )

            # Llamada al SDK de Gemini
            respuesta = self.cliente.models.generate_content(
                model=self.modelo,
                contents=contents,
                config=config,
            )

            print(f"  ✓ Respuesta recibida de Gemini exitosamente")

            # Extraer información de uso de tokens
            if hasattr(respuesta, 'usage_metadata') and respuesta.usage_metadata:
                uso = respuesta.usage_metadata
                tokens_prompt = getattr(uso, 'prompt_token_count', 0) or 0
                tokens_resp = getattr(uso, 'candidates_token_count', 0) or 0
                tokens_total = getattr(uso, 'total_token_count', 0) or 0
                print(f"    Tokens prompt: {tokens_prompt}")
                print(f"    Tokens respuesta: {tokens_resp}")
                print(f"    Tokens total: {tokens_total}")
                resultado.tokens_usados = tokens_total

            # Paso 3: Parsear la respuesta
            print("\n  [Paso 3] Parseando respuesta del LLM...")
            texto_respuesta = respuesta.text
            codigo_ref, explicacion = self.parsear_respuesta(texto_respuesta)

            # Almacenar resultados
            resultado.codigo_refactorizado = codigo_ref
            resultado.explicacion = explicacion
            resultado.exitoso = bool(codigo_ref)

            if resultado.exitoso:
                print("  ✓ Refactorización completada exitosamente")
            else:
                resultado.error = "No se pudo extraer código refactorizado de la respuesta"
                print(f"  ⚠ {resultado.error}")

        except Exception as e:
            resultado.error = f"Error al comunicarse con Gemini: {str(e)}"
            print(f"  ✗ {resultado.error}")

        return resultado

    def refactorizar_demo(self, codigo_smell: str, tipo_smell: str) -> ResultadoRefactorizacion:
        """
        Versión de demostración que NO requiere API Key.
        
        Útil para probar el flujo completo sin consumir créditos de la API,
        o cuando no se tiene conexión a internet. Retorna un ejemplo
        de refactorización predefinido basado en los ejemplos few-shot.

        Args:
            codigo_smell: Código fuente con el code smell.
            tipo_smell: Tipo de code smell.

        Returns:
            ResultadoRefactorizacion con ejemplo predefinido.
        """
        print("  ℹ Modo DEMO activado (sin llamada a API)")
        print("    Para usar la API real, configura GEMINI_API_KEY en .env")

        resultado = ResultadoRefactorizacion(
            codigo_original=codigo_smell,
            tipo_smell=tipo_smell,
            modelo_usado="demo-local (sin API)"
        )

        ejemplos = EJEMPLOS_FEW_SHOT.get(tipo_smell, [])
        if ejemplos:
            ejemplo = ejemplos[0]
            resultado.codigo_refactorizado = ejemplo["codigo_bueno"]
            resultado.explicacion = (
                f"[MODO DEMO - Ejemplo predefinido]\n\n"
                f"{ejemplo['explicacion']}\n\n"
                f"NOTA: Este es un ejemplo predefinido. Para obtener una "
                f"refactorización real del código proporcionado, configura "
                f"tu GEMINI_API_KEY en el archivo .env y ejecuta sin --demo."
            )
            resultado.tecnica_aplicada = "Ejemplo Few-Shot (demo)"
            resultado.exitoso = True
        else:
            resultado.error = f"No hay ejemplos de demostración para '{tipo_smell}'"

        return resultado


# =============================================================================
# Bloque de prueba independiente
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" PRUEBA DEL MOTOR DE REFACTORIZACIÓN (MODO DEMO)")
    print("=" * 70)

    codigo_prueba = '''def procesar_datos(datos):
    resultado = []
    for d in datos:
        if d["activo"]:
            nombre = d["nombre"].strip().title()
            email = d["email"].strip().lower()
            edad = int(d["edad"])
            if edad >= 18:
                if "@" in email and "." in email:
                    resultado.append({
                        "nombre": nombre,
                        "email": email,
                        "edad": edad,
                        "categoria": "adulto" if edad < 65 else "senior"
                    })
    return resultado'''

    motor = MotorDeRefactorizacion()

    print("\n[1] Código original:")
    print(codigo_prueba)

    print("\n[2] Refactorizando en modo demo...")
    resultado = motor.refactorizar_demo(codigo_prueba, "Long Method")

    if resultado.exitoso:
        print("\n[3] Código refactorizado:")
        print(resultado.codigo_refactorizado)
        print("\n[4] Explicación:")
        print(resultado.explicacion)
    else:
        print(f"\n  ✗ Error: {resultado.error}")
