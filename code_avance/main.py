"""
=============================================================================
 main.py - Orquestador Principal del Pipeline de Refactorización
=============================================================================
 Primer Avance - Tesis Doctoral:
 "Refactorización automática de Code Smells mediante LLMs para la
  mitigación de la deuda técnica en proyectos de código abierto en Python"

 Descripción:
    Este es el script principal que orquesta todo el flujo del pipeline
    de refactorización automática:
    
    1. Clonar un repositorio Python de código abierto (extractor.py)
    2. Analizar el código con SonarQube (sonar_detector.py)
    3. Refactorizar el peor smell usando Gemini LLM (refactor_engine.py)
    4. Mostrar y guardar los resultados (antes vs. después)

 Uso:
    python main.py                  # Ejecutar con SonarQube + API de Gemini
    python main.py --demo           # Ejecutar en modo demostración (sin APIs)
    python main.py --repo URL       # Usar un repositorio específico
    python main.py --archivo RUTA   # Analizar un archivo específico
    python main.py --sin-sonar      # Usar detector heurístico (sin SonarQube)

 Ejemplo:
    python main.py --demo
    python main.py --repo https://github.com/psf/requests.git
=============================================================================
"""

import os
import sys
import argparse
from datetime import datetime

# Configurar la codificación de salida para evitar errores con caracteres Unicode
# en consolas de Windows que usan cp1252 en lugar de UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Cargar variables de entorno ANTES de importar los módulos del proyecto
from dotenv import load_dotenv
load_dotenv()

# Importar los módulos del pipeline
from extractor import ExtractorDeCodigo
from sonar_detector import SonarQubeDetector, CodeSmellSonar, DeudaTecnica
from smell_detector import DetectorDeSmells, CodeSmellDetectado
from refactor_engine import MotorDeRefactorizacion, ResultadoRefactorizacion


# =============================================================================
# Configuración por defecto
# =============================================================================

# Repositorio a analizar por defecto
# 'requests' es ideal porque es un proyecto Python conocido y bien mantenido
REPO_POR_DEFECTO = os.getenv(
    "GITHUB_REPO_URL",
    "https://github.com/psf/requests.git"
)

# Directorio donde se clonan los repositorios
DIR_CLONES = os.getenv("CLONE_DIR", "./repos_clonados")

# Directorio donde se guardan los resultados
DIR_RESULTADOS = "./resultados"

# Archivos prioritarios a analizar (contienen code smells conocidos)
# Estos archivos fueron pre-seleccionados por contener funciones complejas
ARCHIVOS_PRIORITARIOS = [
    "src/requests/utils.py",       # Utilidades con funciones largas
    "src/requests/models.py",      # Modelos con complejidad alta
    "src/requests/sessions.py",    # Sesiones con parámetros excesivos
    "src/requests/adapters.py",    # Adaptadores con lógica compleja
    "requests/utils.py",           # Versión alternativa de la ruta
    "requests/models.py",
    "requests/sessions.py",
    "requests/adapters.py",
]


def configurar_argumentos() -> argparse.Namespace:
    """
    Configura y parsea los argumentos de línea de comandos.
    
    Permite al usuario personalizar la ejecución del pipeline
    sin modificar el código fuente.

    Returns:
        Namespace con los argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Pipeline de refactorización automática de Code Smells "
            "usando SonarQube + LLMs (Gemini) con Few-Shot Prompting"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos de uso:\n"
            "  python main.py --demo                    # Modo demostración\n"
            "  python main.py --repo https://github.com/user/repo.git\n"
            "  python main.py --sin-sonar               # Sin SonarQube\n"
        )
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ejecutar en modo demostración sin llamar a las APIs"
    )

    parser.add_argument(
        "--repo",
        type=str,
        default=REPO_POR_DEFECTO,
        help=f"URL del repositorio Git a analizar (default: {REPO_POR_DEFECTO})"
    )

    parser.add_argument(
        "--archivo",
        type=str,
        default=None,
        help="Ruta relativa del archivo específico a analizar dentro del repo"
    )

    parser.add_argument(
        "--sin-sonar",
        action="store_true",
        help="Usar detector heurístico en lugar de SonarQube"
    )

    parser.add_argument(
        "--guardar",
        action="store_true",
        default=True,
        help="Guardar los resultados en archivos (activado por defecto)"
    )

    return parser.parse_args()


def imprimir_banner():
    """Imprime el banner de bienvenida del pipeline."""
    print("\n" + "=" * 70)
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║  PIPELINE DE REFACTORIZACIÓN AUTOMÁTICA DE CODE SMELLS     ║")
    print("  ║  SonarQube + Gemini LLM con Few-Shot Prompting             ║")
    print("  ╠══════════════════════════════════════════════════════════════╣")
    print("  ║  Primer Avance - Tesis Doctoral                            ║")
    print("  ║  Universidad Nacional de San Agustín (UNSA)                ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print("=" * 70)
    print(f"  Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def encontrar_archivo_analizable(extractor: ExtractorDeCodigo, archivo_especifico: str = None) -> str:
    """
    Encuentra un archivo Python adecuado para analizar en busca de smells.
    
    Si se especifica un archivo, lo usa directamente. Si no, busca entre
    los archivos prioritarios o selecciona el más grande.

    Args:
        extractor: Instancia del extractor de código.
        archivo_especifico: Ruta relativa del archivo específico a analizar.

    Returns:
        Ruta relativa del archivo seleccionado.

    Raises:
        FileNotFoundError: Si no se encuentra ningún archivo analizable.
    """
    if archivo_especifico:
        print(f"  → Usando archivo especificado: {archivo_especifico}")
        return archivo_especifico

    # Listar todos los archivos Python del repositorio
    archivos = extractor.listar_archivos_python()

    if not archivos:
        raise FileNotFoundError("No se encontraron archivos Python en el repositorio")

    # Intentar usar archivos prioritarios (conocidos por tener smells)
    for archivo_prio in ARCHIVOS_PRIORITARIOS:
        if archivo_prio in archivos:
            print(f"  ✓ Archivo prioritario encontrado: {archivo_prio}")
            return archivo_prio

    # Si no hay archivos prioritarios, seleccionar el archivo .py más grande
    # (los archivos más grandes tienden a tener más code smells)
    mejor_archivo = None
    mayor_tamano = 0

    for archivo in archivos:
        ruta_completa = os.path.join(extractor.directorio_clon, archivo)
        try:
            tamano = os.path.getsize(ruta_completa)
            if tamano > mayor_tamano:
                mayor_tamano = tamano
                mejor_archivo = archivo
        except OSError:
            continue

    if mejor_archivo:
        print(f"  ✓ Archivo más grande seleccionado: {mejor_archivo} ({mayor_tamano} bytes)")
        return mejor_archivo

    # Último recurso: usar el primer archivo
    print(f"  ⚠ Usando el primer archivo disponible: {archivos[0]}")
    return archivos[0]


def guardar_resultados(
    resultado: ResultadoRefactorizacion,
    smell_info: dict,
    info_repo: dict,
    deuda: DeudaTecnica = None,
    directorio: str = DIR_RESULTADOS
):
    """
    Guarda los resultados de la refactorización en archivos para comparación.
    
    Genera tres archivos:
    1. codigo_original.py - El código fuente original con el smell
    2. codigo_refactorizado.py - El código después de la refactorización
    3. reporte_refactorizacion.txt - Reporte completo con la explicación

    Args:
        resultado: Resultado de la refactorización.
        smell_info: Diccionario con información del smell detectado.
        info_repo: Información del repositorio analizado.
        deuda: Métricas de deuda técnica (SonarQube).
        directorio: Directorio donde guardar los archivos.
    """
    # Crear directorio de resultados si no existe
    os.makedirs(directorio, exist_ok=True)

    # Timestamp para identificar la ejecución
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # =========================================================================
    # 1. Guardar código original
    # =========================================================================
    ruta_original = os.path.join(directorio, f"codigo_original_{timestamp}.py")
    with open(ruta_original, 'w', encoding='utf-8') as f:
        f.write(f'"""\n')
        f.write(f'Código Original - Extraído de: {info_repo.get("nombre", "desconocido")}\n')
        f.write(f'Archivo: {smell_info.get("archivo", "N/A")}\n')
        f.write(f'Función: {smell_info.get("nombre_funcion", "N/A")}\n')
        f.write(f'Code Smell: {smell_info.get("tipo", "N/A")} '
                f'(Severidad: {smell_info.get("severidad", "N/A")})\n')
        f.write(f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'"""\n\n')
        f.write(resultado.codigo_original)
    print(f"  ✓ Código original guardado en: {ruta_original}")

    # =========================================================================
    # 2. Guardar código refactorizado
    # =========================================================================
    ruta_refactorizado = os.path.join(directorio, f"codigo_refactorizado_{timestamp}.py")
    with open(ruta_refactorizado, 'w', encoding='utf-8') as f:
        f.write(f'"""\n')
        f.write(f'Código Refactorizado por Gemini LLM\n')
        f.write(f'Modelo: {resultado.modelo_usado}\n')
        f.write(f'Smell refactorizado: {resultado.tipo_smell}\n')
        f.write(f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'"""\n\n')
        f.write(resultado.codigo_refactorizado)
    print(f"  ✓ Código refactorizado guardado en: {ruta_refactorizado}")

    # =========================================================================
    # 3. Guardar reporte completo
    # =========================================================================
    ruta_reporte = os.path.join(directorio, f"reporte_refactorizacion_{timestamp}.txt")
    with open(ruta_reporte, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(" REPORTE DE REFACTORIZACIÓN AUTOMÁTICA\n")
        f.write(" Primer Avance - Tesis Doctoral (UNSA)\n")
        f.write("=" * 70 + "\n\n")

        f.write("INFORMACIÓN DEL REPOSITORIO:\n")
        f.write("-" * 40 + "\n")
        for clave, valor in info_repo.items():
            f.write(f"  {clave}: {valor}\n")
        f.write("\n")

        # Deuda técnica si está disponible
        if deuda and deuda.total_smells > 0:
            f.write("DEUDA TÉCNICA (SonarQube SQALE):\n")
            f.write("-" * 40 + "\n")
            f.write(f"  Total code smells: {deuda.total_smells}\n")
            f.write(f"  Deuda técnica: {deuda.deuda_legible}\n")
            f.write(f"  Ratio de deuda: {deuda.deuda_ratio:.1f}%\n")
            f.write(f"  Rating mantenibilidad: {deuda.rating}\n\n")

        f.write("CODE SMELL DETECTADO:\n")
        f.write("-" * 40 + "\n")
        for clave, valor in smell_info.items():
            f.write(f"  {clave}: {valor}\n")
        f.write("\n")

        f.write("CÓDIGO ORIGINAL:\n")
        f.write("-" * 40 + "\n")
        f.write(resultado.codigo_original + "\n\n")

        f.write("CÓDIGO REFACTORIZADO:\n")
        f.write("-" * 40 + "\n")
        f.write(resultado.codigo_refactorizado + "\n\n")

        f.write("EXPLICACIÓN DEL LLM:\n")
        f.write("-" * 40 + "\n")
        f.write(resultado.explicacion + "\n\n")

        f.write("DETALLES DE LA EJECUCIÓN:\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Modelo: {resultado.modelo_usado}\n")
        f.write(f"  Tokens usados: {resultado.tokens_usados}\n")
        f.write(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"  ✓ Reporte completo guardado en: {ruta_reporte}")

    return ruta_original, ruta_refactorizado, ruta_reporte


# =============================================================================
# FLUJO CON SONARQUBE (principal)
# =============================================================================

def ejecutar_fase2_sonarqube(extractor, nombre_repo):
    """
    Ejecuta la Fase 2 usando SonarQube como motor de detección.

    Arranca el servidor, ejecuta el análisis completo del repositorio
    y consulta la API REST para obtener issues y deuda técnica.

    Args:
        extractor: Instancia del ExtractorDeCodigo (con repo clonado).
        nombre_repo: Nombre del repositorio (para el project_key).

    Returns:
        Tupla (smells, deuda, smell_objetivo) o None si falla.
    """
    print("\n" + "=" * 70)
    print(" FASE 2: DETECCIÓN DE CODE SMELLS CON SONARQUBE")
    print("=" * 70)

    detector = SonarQubeDetector()

    # Paso 2.1: Arrancar el servidor
    print("\n[2.1] Verificando servidor SonarQube...")
    if not detector.iniciar_servidor():
        print("\n  ✗ No se pudo arrancar SonarQube.")
        return None

    # Paso 2.2: Configurar autenticación
    print("\n[2.2] Configurando autenticación...")
    if not detector.configurar_autenticacion():
        print("\n  ✗ No se pudo autenticar con SonarQube.")
        return None

    # Paso 2.3: Crear proyecto
    project_key = nombre_repo.replace("-", "_").replace(".", "_")
    print(f"\n[2.3] Configurando proyecto '{project_key}'...")
    if not detector.crear_proyecto(project_key, nombre_repo):
        print("\n  ✗ No se pudo crear el proyecto en SonarQube.")
        return None

    # Paso 2.4: Ejecutar el análisis
    print(f"\n[2.4] Ejecutando análisis estático con SonarQube...")
    if not detector.ejecutar_analisis(extractor.directorio_clon, project_key):
        print("\n  ✗ El análisis de SonarQube falló.")
        return None

    # Paso 2.5: Obtener resultados
    print(f"\n[2.5] Obteniendo resultados del análisis...")
    smells = detector.obtener_code_smells(project_key, extractor.directorio_clon)
    deuda = detector.obtener_deuda_tecnica(project_key)

    # Mostrar reporte
    print(f"\n[2.6] Reporte de resultados:")
    print(detector.generar_reporte(smells, deuda))

    if not smells:
        print("\n  ℹ No se detectaron code smells con SonarQube.")
        return None

    # Seleccionar el peor smell
    print(f"\n[2.7] Seleccionando smell más severo...")
    smell_objetivo = detector.seleccionar_peor_smell(smells)

    if smell_objetivo:
        print(f"  → Seleccionado: {smell_objetivo.tipo_smell}")
        print(f"    Regla: {smell_objetivo.regla}")
        print(f"    Función: {smell_objetivo.nombre_funcion}")
        print(f"    Archivo: {smell_objetivo.archivo} (línea {smell_objetivo.linea})")
        print(f"    Severidad: {smell_objetivo.severidad}")
        print(f"    Esfuerzo: {smell_objetivo.esfuerzo}")
    else:
        print("  ✗ No se pudo seleccionar un smell con código fuente.")
        return None

    return smells, deuda, smell_objetivo


# =============================================================================
# FLUJO CON DETECTOR HEURÍSTICO (fallback)
# =============================================================================

def ejecutar_fase2_heuristico(extractor, archivo_seleccionado):
    """
    Ejecuta la Fase 2 usando el detector heurístico simple (fallback).

    Este es el flujo original basado en AST + Radon, usado cuando
    SonarQube no está disponible.

    Args:
        extractor: Instancia del ExtractorDeCodigo.
        archivo_seleccionado: Archivo a analizar.

    Returns:
        Tupla (smells_info, None, smell_objetivo_info) o None si falla.
    """
    print("\n" + "=" * 70)
    print(" FASE 2: DETECCIÓN DE CODE SMELLS (Detector Heurístico)")
    print("=" * 70)
    print("  ⚠ Usando detector heurístico (AST + Radon) en lugar de SonarQube")

    detector = DetectorDeSmells()

    print(f"\n[2.1] Leyendo archivo: {archivo_seleccionado}")
    try:
        codigo_fuente = extractor.leer_archivo(archivo_seleccionado)
    except FileNotFoundError:
        print(f"  ✗ Archivo no encontrado: {archivo_seleccionado}")
        return None

    print(f"\n[2.2] Analizando {archivo_seleccionado}...")
    smells = detector.analizar_codigo(codigo_fuente, archivo_seleccionado)

    print(f"\n[2.3] Resultados del análisis:")
    print(detector.generar_reporte(smells))

    if not smells:
        print("\n  ℹ No se detectaron code smells.")
        return None

    print(f"\n[2.4] Seleccionando smell más severo...")
    smell_objetivo = detector.seleccionar_peor_smell(smells)
    print(f"  → Seleccionado: {smell_objetivo.tipo} en '{smell_objetivo.nombre_funcion}'")
    print(f"    Severidad: {smell_objetivo.severidad}")

    return smells, None, smell_objetivo


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================

def ejecutar_pipeline(args: argparse.Namespace):
    """
    Ejecuta el pipeline completo de refactorización automática.
    
    Flujo: Extracción → Detección (SonarQube o heurístico) → 
           Refactorización (Gemini) → Resultados

    Args:
        args: Argumentos de línea de comandos parseados.
    """

    # =========================================================================
    # FASE 1: EXTRACCIÓN DE CÓDIGO FUENTE
    # =========================================================================
    print("\n" + "=" * 70)
    print(" FASE 1: EXTRACCIÓN DE CÓDIGO FUENTE")
    print("=" * 70)

    # Crear el extractor y clonar el repositorio
    extractor = ExtractorDeCodigo(
        url_repositorio=args.repo,
        directorio_clon=DIR_CLONES
    )

    print("\n[1.1] Clonando repositorio...")
    try:
        extractor.clonar_repositorio()
    except Exception as e:
        print(f"\n  ✗ Error fatal al clonar: {e}")
        print("  Verifica la URL del repositorio y tu conexión a internet.")
        sys.exit(1)

    # Obtener información del repositorio para el reporte
    info_repo = extractor.obtener_info_repositorio()
    nombre_repo = info_repo.get("nombre", "proyecto")

    # =========================================================================
    # FASE 2: DETECCIÓN DE CODE SMELLS
    # =========================================================================
    resultado_fase2 = None
    usar_sonar = not args.sin_sonar and not args.demo

    if usar_sonar:
        resultado_fase2 = ejecutar_fase2_sonarqube(extractor, nombre_repo)

        if resultado_fase2 is None:
            print("\n  → Cayendo al detector heurístico como respaldo...")
            usar_sonar = False

    if not usar_sonar or resultado_fase2 is None:
        # Usar detector heurístico (fallback)
        print("\n[1.2] Buscando archivo para analizar...")
        try:
            archivo_seleccionado = encontrar_archivo_analizable(
                extractor, args.archivo
            )
        except FileNotFoundError as e:
            print(f"\n  ✗ {e}")
            sys.exit(1)

        resultado_fase2 = ejecutar_fase2_heuristico(extractor, archivo_seleccionado)
        if resultado_fase2 is None:
            print("\n  ✗ No se detectaron code smells. Abortando.")
            sys.exit(0)

    smells, deuda, smell_objetivo = resultado_fase2

    # Preparar información del smell para uso uniforme
    if isinstance(smell_objetivo, CodeSmellSonar):
        # Viene de SonarQube
        tipo_smell = smell_objetivo.tipo_smell
        codigo_smell = smell_objetivo.codigo_fuente
        smell_info = {
            "tipo": smell_objetivo.tipo_smell,
            "regla": smell_objetivo.regla,
            "nombre_funcion": smell_objetivo.nombre_funcion,
            "archivo": smell_objetivo.archivo,
            "linea": smell_objetivo.linea,
            "severidad": smell_objetivo.severidad,
            "esfuerzo": smell_objetivo.esfuerzo,
            "mensaje": smell_objetivo.mensaje,
        }
        total_smells = deuda.total_smells if deuda else len(smells)
    else:
        # Viene del detector heurístico
        tipo_smell = smell_objetivo.tipo
        codigo_smell = smell_objetivo.codigo_fuente
        smell_info = {
            "tipo": smell_objetivo.tipo,
            "nombre_funcion": smell_objetivo.nombre_funcion,
            "archivo": smell_objetivo.archivo,
            "severidad": smell_objetivo.severidad,
            "metricas": str(smell_objetivo.metricas),
            "descripcion": smell_objetivo.descripcion,
        }
        total_smells = len(smells)
        deuda = None

    # =========================================================================
    # FASE 3: REFACTORIZACIÓN CON Gemini LLM
    # =========================================================================
    print("\n" + "=" * 70)
    print(" FASE 3: REFACTORIZACIÓN CON Gemini LLM (Few-Shot Prompting)")
    print("=" * 70)

    motor = MotorDeRefactorizacion()

    print(f"\n[3.1] Preparando refactorización...")
    print(f"  Tipo de smell: {tipo_smell}")
    print(f"  Función objetivo: {smell_info.get('nombre_funcion', 'N/A')}")
    print(f"  Modo: {'DEMO (sin API)' if args.demo else 'API de Gemini'}")

    # Ejecutar la refactorización (modo demo o API real)
    print(f"\n[3.2] Ejecutando refactorización...")
    if args.demo:
        resultado = motor.refactorizar_demo(codigo_smell, tipo_smell)
    else:
        resultado = motor.refactorizar(codigo_smell, tipo_smell)

    # =========================================================================
    # FASE 4: PRESENTACIÓN DE RESULTADOS
    # =========================================================================
    print("\n" + "=" * 70)
    print(" FASE 4: RESULTADOS DE LA REFACTORIZACIÓN")
    print("=" * 70)

    if resultado.exitoso:
        # Mostrar código ORIGINAL
        print("\n┌─────────────────────────────────────────────────────────────────┐")
        print("│  CÓDIGO ORIGINAL (con code smell)                              │")
        print("├─────────────────────────────────────────────────────────────────┤")
        print(resultado.codigo_original)
        print("└─────────────────────────────────────────────────────────────────┘")

        # Mostrar código REFACTORIZADO
        print("\n┌─────────────────────────────────────────────────────────────────┐")
        print("│  CÓDIGO REFACTORIZADO (por Gemini LLM)                         │")
        print("├─────────────────────────────────────────────────────────────────┤")
        print(resultado.codigo_refactorizado)
        print("└─────────────────────────────────────────────────────────────────┘")

        # Mostrar la explicación del LLM
        print("\n┌─────────────────────────────────────────────────────────────────┐")
        print("│  EXPLICACIÓN DEL LLM                                           │")
        print("├─────────────────────────────────────────────────────────────────┤")
        print(resultado.explicacion)
        print("└─────────────────────────────────────────────────────────────────┘")

        # Guardar resultados en archivos
        if args.guardar:
            print("\n[4.1] Guardando resultados...")
            rutas = guardar_resultados(resultado, smell_info, info_repo, deuda)
            print(f"\n  Archivos generados:")
            for ruta in rutas:
                print(f"    📄 {ruta}")

    else:
        print(f"\n  ✗ La refactorización NO fue exitosa.")
        print(f"  Error: {resultado.error}")
        if "API Key" in resultado.error:
            print("\n  Para configurar la API Key:")
            print("    1. Copia .env.example como .env")
            print("    2. Edita .env y agrega tu GEMINI_API_KEY")
            print("    3. O ejecuta con --demo para modo demostración")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    print("\n" + "=" * 70)
    print(" RESUMEN DE EJECUCIÓN")
    print("=" * 70)
    print(f"  Repositorio: {info_repo.get('nombre', 'N/A')}")
    print(f"  Motor de detección: {'SonarQube' if deuda else 'Heurístico (AST+Radon)'}")
    print(f"  Smells detectados: {total_smells}")

    if deuda and deuda.total_smells > 0:
        print(f"  ┌─ DEUDA TÉCNICA (SQALE) ─────────────────────────────┐")
        print(f"  │  Total smells:   {deuda.total_smells:<38}│")
        print(f"  │  Deuda técnica:  {deuda.deuda_legible:<38}│")
        print(f"  │  Ratio:          {deuda.deuda_ratio:.1f}%{' ' * (36 - len(f'{deuda.deuda_ratio:.1f}%'))}│")
        print(f"  │  Rating:         {deuda.rating:<38}│")
        print(f"  └─────────────────────────────────────────────────────┘")

    print(f"  Smell refactorizado: {tipo_smell} ({smell_info.get('severidad', 'N/A')})")
    print(f"  Modelo LLM: {resultado.modelo_usado}")
    print(f"  Tokens usados: {resultado.tokens_usados}")
    print(f"  Resultado: {'✓ Exitoso' if resultado.exitoso else '✗ Fallido'}")
    print("=" * 70 + "\n")


# =============================================================================
# Punto de entrada principal
# =============================================================================
if __name__ == "__main__":
    imprimir_banner()
    args = configurar_argumentos()

    try:
        ejecutar_pipeline(args)
    except KeyboardInterrupt:
        print("\n\n  ⚠ Ejecución interrumpida por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ✗ Error inesperado: {e}")
        print("  Revisa la configuración y vuelve a intentar.")
        import traceback
        traceback.print_exc()
        sys.exit(1)
