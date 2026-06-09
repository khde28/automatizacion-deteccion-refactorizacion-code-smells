"""
=============================================================================
 setup_sonar_scanner.py - Descarga y Configuración del Sonar Scanner CLI
=============================================================================
 Primer Avance - Tesis Doctoral:
 "Refactorización automática de Code Smells mediante LLMs para la
  mitigación de la deuda técnica en proyectos de código abierto en Python"

 Descripción:
    Este módulo descarga y configura automáticamente el Sonar Scanner CLI,
    necesario para enviar el código fuente al servidor SonarQube para su
    análisis estático.
=============================================================================
"""

import os
import sys
import zipfile
import urllib.request
import shutil


# =============================================================================
# Configuración del Sonar Scanner
# =============================================================================

# Versión del scanner a descargar
SCANNER_VERSION = "7.0.2.4839"

# URL oficial de descarga de SonarSource
SCANNER_DOWNLOAD_URL = (
    f"https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/"
    f"sonar-scanner-cli-{SCANNER_VERSION}-windows-x64.zip"
)

# Nombre del directorio extraído
SCANNER_DIR_NAME = f"sonar-scanner-{SCANNER_VERSION}-windows-x64"

# Directorio por defecto donde se instalará
SONAR_BASE_DIR = os.getenv(
    "SONAR_BASE_DIR",
    r"C:\Users\edils\OneDrive\Documents\UNSA\sonar"
)


def buscar_scanner_existente(directorio_base: str = SONAR_BASE_DIR) -> str | None:
    """
    Busca si el sonar-scanner ya está instalado en el sistema.

    Revisa:
    1. La variable de entorno SONAR_SCANNER_PATH
    2. El directorio base de sonar
    3. Subcarpetas comunes

    Args:
        directorio_base: Directorio raíz donde buscar.

    Returns:
        Ruta al ejecutable sonar-scanner.bat, o None si no se encuentra.
    """
    # 1. Verificar variable de entorno
    ruta_env = os.getenv("SONAR_SCANNER_PATH", "")
    if ruta_env and os.path.isfile(ruta_env):
        print(f"  ✓ Scanner encontrado via env: {ruta_env}")
        return ruta_env

    # 2. Buscar en directorio base
    if not os.path.isdir(directorio_base):
        return None

    for entrada in os.listdir(directorio_base):
        ruta_candidata = os.path.join(directorio_base, entrada)
        if os.path.isdir(ruta_candidata) and "sonar-scanner" in entrada.lower():
            bat_path = os.path.join(ruta_candidata, "bin", "sonar-scanner.bat")
            if os.path.isfile(bat_path):
                print(f"  ✓ Scanner encontrado: {bat_path}")
                return bat_path

    return None


def descargar_scanner(directorio_destino: str = SONAR_BASE_DIR) -> str:
    """
    Descarga e instala el Sonar Scanner CLI desde los binarios oficiales.

    Args:
        directorio_destino: Directorio donde instalar el scanner.

    Returns:
        Ruta al ejecutable sonar-scanner.bat.

    Raises:
        RuntimeError: Si la descarga o extracción falla.
    """
    os.makedirs(directorio_destino, exist_ok=True)

    ruta_zip = os.path.join(directorio_destino, f"sonar-scanner-cli-{SCANNER_VERSION}.zip")
    ruta_extraida = os.path.join(directorio_destino, SCANNER_DIR_NAME)
    ruta_ejecutable = os.path.join(ruta_extraida, "bin", "sonar-scanner.bat")

    # Si ya existe el directorio extraído, verificar el ejecutable
    if os.path.isfile(ruta_ejecutable):
        print(f"  ✓ Scanner ya instalado en: {ruta_ejecutable}")
        return ruta_ejecutable

    # Descargar el ZIP
    print(f"  → Descargando Sonar Scanner CLI v{SCANNER_VERSION}...")
    print(f"    URL: {SCANNER_DOWNLOAD_URL}")
    print(f"    Destino: {ruta_zip}")
    print(f"    (Esto puede tomar unos minutos dependiendo de tu conexión)")

    try:
        def _progreso(bloques, tam_bloque, tam_total):
            descargado = bloques * tam_bloque
            if tam_total > 0:
                porcentaje = min(100, descargado * 100 // tam_total)
                mb_descargado = descargado / (1024 * 1024)
                mb_total = tam_total / (1024 * 1024)
                sys.stdout.write(
                    f"\r    Progreso: {porcentaje}% ({mb_descargado:.1f}/{mb_total:.1f} MB)"
                )
                sys.stdout.flush()

        urllib.request.urlretrieve(SCANNER_DOWNLOAD_URL, ruta_zip, _progreso)
        print()  # Nueva línea después de la barra de progreso

    except Exception as e:
        raise RuntimeError(
            f"Error al descargar Sonar Scanner: {e}\n"
            f"Descarga manual: {SCANNER_DOWNLOAD_URL}\n"
            f"Extrae en: {directorio_destino}"
        )

    # Extraer el ZIP
    print(f"  → Extrayendo archivo ZIP...")
    try:
        with zipfile.ZipFile(ruta_zip, 'r') as zip_ref:
            zip_ref.extractall(directorio_destino)
        print(f"  ✓ Extracción completada")
    except zipfile.BadZipFile:
        raise RuntimeError(
            f"El archivo descargado está corrupto: {ruta_zip}\n"
            f"Elimínalo y vuelve a intentar."
        )

    # Limpiar el ZIP descargado
    try:
        os.remove(ruta_zip)
        print(f"  ✓ Archivo ZIP temporal eliminado")
    except OSError:
        pass  # No es crítico si no se puede eliminar

    # Verificar que el ejecutable existe
    if not os.path.isfile(ruta_ejecutable):
        # Intentar buscar el bat en subdirectorios
        for raiz, dirs, archivos in os.walk(directorio_destino):
            for archivo in archivos:
                if archivo == "sonar-scanner.bat":
                    ruta_ejecutable = os.path.join(raiz, archivo)
                    print(f"  ✓ Scanner instalado en: {ruta_ejecutable}")
                    return ruta_ejecutable

        raise RuntimeError(
            f"No se encontró sonar-scanner.bat después de la extracción.\n"
            f"Verifica el contenido de: {directorio_destino}"
        )

    print(f"  ✓ Scanner instalado en: {ruta_ejecutable}")
    return ruta_ejecutable


def obtener_scanner() -> str:
    """
    Obtiene la ruta al sonar-scanner, descargándolo si es necesario.

    Returns:
        Ruta al ejecutable sonar-scanner.bat.
    """
    # Primero buscar si ya existe
    ruta = buscar_scanner_existente()
    if ruta:
        return ruta

    # Si no existe, descargar
    print("  ⚠ Sonar Scanner no encontrado. Descargando...")
    return descargar_scanner()


# =============================================================================
# Bloque de prueba independiente
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" CONFIGURACIÓN DEL SONAR SCANNER CLI")
    print("=" * 70)

    try:
        ruta = obtener_scanner()
        print(f"\n  Resultado: {ruta}")
    except RuntimeError as e:
        print(f"\n  ✗ Error: {e}")
