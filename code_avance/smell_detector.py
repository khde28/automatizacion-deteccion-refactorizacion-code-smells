"""
=============================================================================
 smell_detector.py - Módulo de Detección de Code Smells
=============================================================================
 Primer Avance - Tesis Doctoral:
 "Refactorización automática de Code Smells mediante LLMs para la
  mitigación de la deuda técnica en proyectos de código abierto en Python"

 Descripción:
    Este módulo implementa la detección de code smells en código Python
    utilizando tanto heurísticas propias como la librería Radon para
    métricas de complejidad ciclomática.

 Code Smells detectados:
    1. Long Method (Función Larga): funciones con demasiadas líneas de código
    2. Long Parameter List (Lista de Parámetros Excesiva): funciones con
       demasiados parámetros
    3. High Cyclomatic Complexity (Complejidad Ciclomática Alta): funciones
       con demasiadas ramas condicionales
    4. Deeply Nested Code (Código Profundamente Anidado): bloques con
       indentación excesiva

 Referencia teórica:
    - Fowler, M. (2018). Refactoring: Improving the Design of Existing Code.
    - Lacerda et al. (2020). Code smells and refactoring: A tertiary review.
=============================================================================
"""

import ast
import textwrap
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# Radon para análisis de complejidad ciclomática
try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
    RADON_DISPONIBLE = True
except ImportError:
    RADON_DISPONIBLE = False
    print("  ⚠ Radon no instalado. Instalar con: pip install radon")


# =============================================================================
# Estructura de datos para representar un Code Smell detectado
# =============================================================================

@dataclass
class CodeSmellDetectado:
    """
    Representa un code smell identificado en el código fuente.
    
    Esta estructura almacena toda la información necesaria para que
    el motor de refactorización (refactor_engine.py) pueda procesar
    el smell y generar una versión refactorizada.
    
    Atributos:
        tipo: Tipo de code smell (ej: "Long Method", "Long Parameter List")
        nombre_funcion: Nombre de la función/clase donde se detectó
        archivo: Ruta del archivo fuente
        linea_inicio: Número de línea donde comienza el smell
        codigo_fuente: Código fuente completo del fragmento afectado
        severidad: Nivel de severidad ("baja", "media", "alta", "crítica")
        metricas: Métricas cuantitativas que justifican la detección
        descripcion: Descripción legible del problema encontrado
    """
    tipo: str
    nombre_funcion: str
    archivo: str = ""
    linea_inicio: int = 0
    codigo_fuente: str = ""
    severidad: str = "media"
    metricas: Dict[str, float] = field(default_factory=dict)
    descripcion: str = ""


# =============================================================================
# Umbrales de detección (configurables según la literatura)
# =============================================================================

# Estos umbrales están basados en la literatura de ingeniería de software
# y pueden ajustarse según el contexto del proyecto analizado.

UMBRALES = {
    # Una función con más de 20 líneas se considera "Long Method"
    # Referencia: Fowler (2018) sugiere que funciones cortas son preferibles
    "max_lineas_funcion": 20,

    # Una función con más de 4 parámetros tiene "Long Parameter List"
    # Referencia: Clean Code (Martin, 2008) recomienda máximo 3
    "max_parametros": 4,

    # Complejidad ciclomática > 10 indica código difícil de mantener
    # Referencia: McCabe (1976) propuso el umbral original de 10
    "max_complejidad_ciclomatica": 10,

    # Más de 4 niveles de indentación indica "Deep Nesting"
    # Referencia: Linux kernel coding style recomienda máximo 3
    "max_profundidad_anidamiento": 4,
}


class DetectorDeSmells:
    """
    Clase principal para la detección de code smells en código Python.
    
    Implementa múltiples estrategias de detección combinando análisis
    del AST (Abstract Syntax Tree) de Python con heurísticas basadas
    en métricas de código y la librería Radon.
    
    El detector analiza funciones individuales dentro de un archivo
    y reporta los code smells encontrados con sus métricas asociadas.
    """

    def __init__(self, umbrales: Optional[Dict[str, int]] = None):
        """
        Inicializa el detector con umbrales configurables.

        Args:
            umbrales: Diccionario con umbrales personalizados.
                      Si es None, se usan los umbrales por defecto.
        """
        self.umbrales = umbrales or UMBRALES.copy()
        print(f"  ✓ Detector inicializado con umbrales: {self.umbrales}")

    def analizar_codigo(self, codigo_fuente: str, archivo: str = "<desconocido>") -> List[CodeSmellDetectado]:
        """
        Analiza un fragmento de código Python y detecta todos los code smells.
        
        Este es el método principal que orquesta todas las verificaciones
        de code smells sobre el código proporcionado.

        Args:
            codigo_fuente: Código fuente Python como cadena de texto.
            archivo: Nombre del archivo (para referencia en los reportes).

        Returns:
            Lista de CodeSmellDetectado encontrados en el código.
        """
        smells_detectados: List[CodeSmellDetectado] = []

        try:
            # Parsear el código fuente a un AST (Árbol de Sintaxis Abstracta)
            arbol = ast.parse(codigo_fuente)
        except SyntaxError as e:
            print(f"  ✗ Error de sintaxis al analizar {archivo}: {e}")
            return smells_detectados

        # Recorrer todas las definiciones de funciones en el AST
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Extraer el código fuente de esta función específica
                codigo_funcion = self._extraer_codigo_funcion(codigo_fuente, nodo)

                # Aplicar cada detector de smell a la función
                # 1. Verificar si es una función larga (Long Method)
                smell_long = self._detectar_funcion_larga(nodo, codigo_funcion, archivo)
                if smell_long:
                    smells_detectados.append(smell_long)

                # 2. Verificar si tiene demasiados parámetros
                smell_params = self._detectar_parametros_excesivos(nodo, codigo_funcion, archivo)
                if smell_params:
                    smells_detectados.append(smell_params)

                # 3. Verificar complejidad ciclomática con Radon
                smell_complex = self._detectar_complejidad_alta(nodo, codigo_funcion, archivo)
                if smell_complex:
                    smells_detectados.append(smell_complex)

                # 4. Verificar anidamiento profundo
                smell_nesting = self._detectar_anidamiento_profundo(nodo, codigo_funcion, archivo)
                if smell_nesting:
                    smells_detectados.append(smell_nesting)

        return smells_detectados

    def _extraer_codigo_funcion(self, codigo_completo: str, nodo: ast.FunctionDef) -> str:
        """
        Extrae el código fuente de una función a partir de su nodo AST.
        
        Usa los números de línea del AST para localizar la función
        dentro del código fuente completo.

        Args:
            codigo_completo: Código fuente completo del archivo.
            nodo: Nodo AST de la función.

        Returns:
            Código fuente de la función como string.
        """
        lineas = codigo_completo.split('\n')
        inicio = nodo.lineno - 1  # AST usa indexación desde 1
        fin = nodo.end_lineno if hasattr(nodo, 'end_lineno') and nodo.end_lineno else len(lineas)
        return '\n'.join(lineas[inicio:fin])

    def _detectar_funcion_larga(
        self, nodo: ast.FunctionDef, codigo: str, archivo: str
    ) -> Optional[CodeSmellDetectado]:
        """
        Detecta el smell "Long Method" (Función Larga).
        
        Una función se considera larga cuando excede el umbral de líneas
        configurado. Las funciones largas son más difíciles de entender,
        probar y mantener.
        
        Refactorización sugerida: Extract Method (Extraer Método)

        Args:
            nodo: Nodo AST de la función.
            codigo: Código fuente de la función.
            archivo: Ruta del archivo.

        Returns:
            CodeSmellDetectado si se detecta el smell, None en caso contrario.
        """
        # Contar líneas de código (excluyendo líneas vacías y comentarios)
        lineas = [
            l for l in codigo.split('\n')
            if l.strip() and not l.strip().startswith('#')
        ]
        num_lineas = len(lineas)

        if num_lineas > self.umbrales["max_lineas_funcion"]:
            severidad = self._calcular_severidad_lineas(num_lineas)
            return CodeSmellDetectado(
                tipo="Long Method",
                nombre_funcion=nodo.name,
                archivo=archivo,
                linea_inicio=nodo.lineno,
                codigo_fuente=codigo,
                severidad=severidad,
                metricas={
                    "lineas_codigo": num_lineas,
                    "umbral": self.umbrales["max_lineas_funcion"],
                    "exceso": num_lineas - self.umbrales["max_lineas_funcion"]
                },
                descripcion=(
                    f"La función '{nodo.name}' tiene {num_lineas} líneas de código, "
                    f"excediendo el umbral de {self.umbrales['max_lineas_funcion']}. "
                    f"Se recomienda aplicar 'Extract Method' para dividirla en "
                    f"funciones más pequeñas y cohesivas."
                )
            )
        return None

    def _detectar_parametros_excesivos(
        self, nodo: ast.FunctionDef, codigo: str, archivo: str
    ) -> Optional[CodeSmellDetectado]:
        """
        Detecta el smell "Long Parameter List" (Lista de Parámetros Excesiva).
        
        Demasiados parámetros indican que la función puede estar haciendo
        más de una cosa, o que los parámetros deberían agruparse en un
        objeto (Introduce Parameter Object).
        
        Nota: Se excluye 'self' y 'cls' del conteo para métodos de clase.

        Args:
            nodo: Nodo AST de la función.
            codigo: Código fuente de la función.
            archivo: Ruta del archivo.

        Returns:
            CodeSmellDetectado si se detecta el smell, None en caso contrario.
        """
        # Obtener la lista de parámetros, excluyendo self/cls
        parametros = [
            arg.arg for arg in nodo.args.args
            if arg.arg not in ('self', 'cls')
        ]
        num_parametros = len(parametros)

        if num_parametros > self.umbrales["max_parametros"]:
            return CodeSmellDetectado(
                tipo="Long Parameter List",
                nombre_funcion=nodo.name,
                archivo=archivo,
                linea_inicio=nodo.lineno,
                codigo_fuente=codigo,
                severidad="media" if num_parametros <= 6 else "alta",
                metricas={
                    "num_parametros": num_parametros,
                    "umbral": self.umbrales["max_parametros"],
                    "parametros": parametros  # type: ignore
                },
                descripcion=(
                    f"La función '{nodo.name}' tiene {num_parametros} parámetros "
                    f"({', '.join(parametros)}), excediendo el umbral de "
                    f"{self.umbrales['max_parametros']}. Se recomienda aplicar "
                    f"'Introduce Parameter Object' o 'Preserve Whole Object'."
                )
            )
        return None

    def _detectar_complejidad_alta(
        self, nodo: ast.FunctionDef, codigo: str, archivo: str
    ) -> Optional[CodeSmellDetectado]:
        """
        Detecta el smell "High Cyclomatic Complexity" usando Radon.
        
        La complejidad ciclomática (McCabe, 1976) mide el número de caminos
        independientes a través de una función. Una complejidad alta indica
        código difícil de probar y mantener.
        
        Escala de Radon:
            A (1-5):   Baja - Simple, poco riesgo
            B (6-10):  Media - Moderada complejidad
            C (11-15): Alta - Más difícil de probar
            D (16-20): Muy Alta - Código propenso a errores
            E (21-30): Extrema - Inestable
            F (31+):   Catastrófica - No mantenible

        Args:
            nodo: Nodo AST de la función.
            codigo: Código fuente de la función.
            archivo: Ruta del archivo.

        Returns:
            CodeSmellDetectado si se detecta el smell, None en caso contrario.
        """
        if not RADON_DISPONIBLE:
            return None

        try:
            # Dedent el código para que Radon pueda analizarlo correctamente
            codigo_dedent = textwrap.dedent(codigo)
            resultados = cc_visit(codigo_dedent)

            for resultado in resultados:
                if (resultado.name == nodo.name and
                    resultado.complexity > self.umbrales["max_complejidad_ciclomatica"]):
                    
                    return CodeSmellDetectado(
                        tipo="High Cyclomatic Complexity",
                        nombre_funcion=nodo.name,
                        archivo=archivo,
                        linea_inicio=nodo.lineno,
                        codigo_fuente=codigo,
                        severidad=self._severidad_complejidad(resultado.complexity),
                        metricas={
                            "complejidad_ciclomatica": resultado.complexity,
                            "grado_radon": resultado.letter,
                            "umbral": self.umbrales["max_complejidad_ciclomatica"]
                        },
                        descripcion=(
                            f"La función '{nodo.name}' tiene complejidad ciclomática "
                            f"de {resultado.complexity} (grado '{resultado.letter}'), "
                            f"excediendo el umbral de "
                            f"{self.umbrales['max_complejidad_ciclomatica']}. "
                            f"Se recomienda simplificar las condiciones o aplicar "
                            f"'Replace Conditional with Polymorphism'."
                        )
                    )
        except Exception as e:
            print(f"  ⚠ Error al calcular complejidad de {nodo.name}: {e}")

        return None

    def _detectar_anidamiento_profundo(
        self, nodo: ast.FunctionDef, codigo: str, archivo: str
    ) -> Optional[CodeSmellDetectado]:
        """
        Detecta el smell "Deeply Nested Code" (Código Profundamente Anidado).
        
        El anidamiento profundo (if dentro de if dentro de for, etc.) reduce
        drásticamente la legibilidad. Se mide contando los niveles de
        indentación en el código fuente.
        
        Refactorización sugerida: 
            - Guard Clauses (retornos tempranos)
            - Extract Method

        Args:
            nodo: Nodo AST de la función.
            codigo: Código fuente de la función.
            archivo: Ruta del archivo.

        Returns:
            CodeSmellDetectado si se detecta el smell, None en caso contrario.
        """
        max_profundidad = 0
        lineas = codigo.split('\n')

        # Determinar la indentación base de la función
        primera_linea = lineas[0] if lineas else ""
        indentacion_base = len(primera_linea) - len(primera_linea.lstrip())

        for linea in lineas:
            if linea.strip():  # Ignorar líneas vacías
                indentacion_actual = len(linea) - len(linea.lstrip())
                # Calcular profundidad relativa a la base de la función
                profundidad_relativa = (indentacion_actual - indentacion_base) // 4
                max_profundidad = max(max_profundidad, profundidad_relativa)

        if max_profundidad > self.umbrales["max_profundidad_anidamiento"]:
            return CodeSmellDetectado(
                tipo="Deep Nesting",
                nombre_funcion=nodo.name,
                archivo=archivo,
                linea_inicio=nodo.lineno,
                codigo_fuente=codigo,
                severidad="media" if max_profundidad <= 6 else "alta",
                metricas={
                    "profundidad_maxima": max_profundidad,
                    "umbral": self.umbrales["max_profundidad_anidamiento"]
                },
                descripcion=(
                    f"La función '{nodo.name}' tiene un anidamiento máximo de "
                    f"{max_profundidad} niveles, excediendo el umbral de "
                    f"{self.umbrales['max_profundidad_anidamiento']}. "
                    f"Se recomienda usar 'Guard Clauses' (retornos tempranos) "
                    f"o 'Extract Method' para reducir el anidamiento."
                )
            )
        return None

    # =========================================================================
    # Métodos auxiliares para calcular severidad
    # =========================================================================

    def _calcular_severidad_lineas(self, num_lineas: int) -> str:
        """Calcula la severidad del smell Long Method según cantidad de líneas."""
        umbral = self.umbrales["max_lineas_funcion"]
        if num_lineas > umbral * 3:
            return "crítica"
        elif num_lineas > umbral * 2:
            return "alta"
        elif num_lineas > umbral * 1.5:
            return "media"
        return "baja"

    def _severidad_complejidad(self, complejidad: int) -> str:
        """Calcula la severidad basada en complejidad ciclomática (escala McCabe)."""
        if complejidad > 30:
            return "crítica"
        elif complejidad > 20:
            return "alta"
        elif complejidad > 15:
            return "media"
        return "baja"

    def generar_reporte(self, smells: List[CodeSmellDetectado]) -> str:
        """
        Genera un reporte legible de todos los code smells detectados.
        
        Útil para la presentación del avance de tesis, ya que muestra
        de forma clara qué problemas se encontraron y dónde.

        Args:
            smells: Lista de code smells detectados.

        Returns:
            Reporte formateado como cadena de texto.
        """
        if not smells:
            return "  ✓ No se detectaron code smells en el código analizado."

        lineas = [
            "=" * 70,
            " REPORTE DE CODE SMELLS DETECTADOS",
            "=" * 70,
            f" Total de smells encontrados: {len(smells)}",
            "-" * 70,
        ]

        for i, smell in enumerate(smells, 1):
            lineas.extend([
                f"\n  [{i}] {smell.tipo}",
                f"      Función: {smell.nombre_funcion}",
                f"      Archivo: {smell.archivo} (línea {smell.linea_inicio})",
                f"      Severidad: {smell.severidad.upper()}",
                f"      Métricas: {smell.metricas}",
                f"      Descripción: {smell.descripcion}",
                "-" * 70,
            ])

        return '\n'.join(lineas)

    def seleccionar_peor_smell(self, smells: List[CodeSmellDetectado]) -> Optional[CodeSmellDetectado]:
        """
        Selecciona el code smell más severo de la lista para refactorizar.
        
        Prioriza por severidad y luego por tipo de smell, dando preferencia
        a los que tienen mayor impacto en la mantenibilidad.

        Args:
            smells: Lista de code smells detectados.

        Returns:
            El code smell más severo, o None si la lista está vacía.
        """
        if not smells:
            return None

        # Orden de severidad para comparación
        orden_severidad = {"crítica": 4, "alta": 3, "media": 2, "baja": 1}
        
        return max(
            smells,
            key=lambda s: orden_severidad.get(s.severidad, 0)
        )


# =============================================================================
# Bloque de prueba independiente
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" PRUEBA DEL MÓDULO DETECTOR DE CODE SMELLS")
    print("=" * 70)

    # Código de ejemplo con múltiples code smells para demostración
    codigo_prueba = '''
def procesar_datos_usuario(nombre, apellido, edad, email, telefono, 
                           direccion, ciudad, pais, codigo_postal):
    """Función con demasiados parámetros y código largo."""
    resultado = {}
    
    if nombre and apellido:
        nombre_completo = nombre + " " + apellido
        resultado["nombre"] = nombre_completo
        
        if edad > 0:
            if edad < 18:
                resultado["categoria"] = "menor"
                if pais == "Peru":
                    resultado["requiere_tutor"] = True
                    if ciudad == "Lima":
                        resultado["zona"] = "capital"
                    else:
                        resultado["zona"] = "provincia"
            elif edad < 65:
                resultado["categoria"] = "adulto"
            else:
                resultado["categoria"] = "adulto_mayor"
    
    if email:
        if "@" in email:
            if "." in email:
                resultado["email_valido"] = True
            else:
                resultado["email_valido"] = False
        else:
            resultado["email_valido"] = False
    
    if telefono:
        telefono_limpio = telefono.replace("-", "").replace(" ", "")
        if len(telefono_limpio) >= 9:
            resultado["telefono"] = telefono_limpio
    
    if direccion:
        resultado["direccion_completa"] = f"{direccion}, {ciudad}, {pais} {codigo_postal}"
    
    return resultado
'''

    print("\n[1] Inicializando detector...")
    detector = DetectorDeSmells()

    print("\n[2] Analizando código de prueba...")
    smells = detector.analizar_codigo(codigo_prueba, "ejemplo.py")

    print("\n[3] Reporte de resultados:")
    print(detector.generar_reporte(smells))

    print("\n[4] Smell más severo seleccionado:")
    peor = detector.seleccionar_peor_smell(smells)
    if peor:
        print(f"    → {peor.tipo} en '{peor.nombre_funcion}' (severidad: {peor.severidad})")
