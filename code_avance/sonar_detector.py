"""
=============================================================================
 sonar_detector.py - Detección de Code Smells con SonarQube
=============================================================================
 Primer Avance - Tesis Doctoral:
 "Refactorización automática de Code Smells mediante LLMs para la
  mitigación de la deuda técnica en proyectos de código abierto en Python"

 Descripción:
    Este módulo reemplaza al detector heurístico (smell_detector.py) por
    una integración completa con SonarQube Community Edition. Utiliza la
    API REST de SonarQube para obtener code smells detectados por el motor
    profesional de análisis estático, junto con métricas reales de deuda
    técnica (SQALE).

 Flujo:
    1. Arrancar el servidor SonarQube (si no está corriendo)
    2. Configurar autenticación (token o basic auth)
    3. Crear proyecto y ejecutar sonar-scanner
    4. Consultar la API REST para obtener issues y métricas
    5. Extraer código fuente asociado a cada issue

 Referencia:
    - SonarQube Web API: https://docs.sonarsource.com/sonarqube/latest/
    - SQALE Method: Software Quality Assessment based on Lifecycle Expectations
=============================================================================
"""

import os
import sys
import ast
import time
import json
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import base64
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

from setup_sonar_scanner import obtener_scanner


# =============================================================================
# Estructuras de datos
# =============================================================================

@dataclass
class CodeSmellSonar:
    """
    Representa un code smell detectado por SonarQube.

    Campos provenientes de la API /api/issues/search, enriquecidos
    con la extracción del código fuente original.
    """
    regla: str = ""                 # Ej: "python:S1192"
    mensaje: str = ""               # Descripción del problema
    archivo: str = ""               # Ruta del archivo relativa al proyecto
    linea: int = 0                  # Número de línea
    severidad: str = ""             # BLOCKER, CRITICAL, MAJOR, MINOR, INFO
    esfuerzo: str = ""              # Esfuerzo de remediación, ej: "15min"
    tipo_smell: str = ""            # Categoría mapeada (Long Method, etc.)
    codigo_fuente: str = ""         # Código fuente extraído del archivo
    nombre_funcion: str = ""        # Nombre de la función afectada
    key: str = ""                   # Identificador único de SonarQube
    tags: List[str] = field(default_factory=list)


@dataclass
class DeudaTecnica:
    """
    Métricas globales de deuda técnica del proyecto (SQALE).

    El modelo SQALE (Software Quality Assessment based on Lifecycle
    Expectations) cuantifica el esfuerzo de remediación necesario.
    """
    total_smells: int = 0           # Cantidad total de code smells
    deuda_minutos: int = 0          # Deuda en minutos (sqale_index)
    deuda_ratio: float = 0.0        # Porcentaje de deuda (sqale_debt_ratio)
    deuda_legible: str = ""         # Formato legible: "2h 30min"
    rating: str = ""                # Rating: A, B, C, D, E


# =============================================================================
# Mapeo de reglas SonarQube a tipos de smell conocidos
# =============================================================================

MAPA_REGLAS_SMELL = {
    "python:S138":  "Long Method",
    "python:S107":  "Long Parameter List",
    "python:S3776": "High Cyclomatic Complexity",
    "python:S1192": "Duplicated String Literals",
    "python:S1066": "Collapsible If Statements",
    "python:S1871": "Duplicated Code Branches",
    "python:S3358": "Nested Ternary Operators",
    "python:S1481": "Unused Local Variable",
    "python:S1144": "Unused Private Method",
    "python:S905":  "Dead Store",
    "python:S1542": "Function Naming Convention",
    "python:S117":  "Variable Naming Convention",
    "python:S1134": "FIXME Comment",
    "python:S1135": "TODO Comment",
}

# Orden de severidad de SonarQube para comparación
ORDEN_SEVERIDAD = {
    "BLOCKER": 5,
    "CRITICAL": 4,
    "MAJOR": 3,
    "MINOR": 2,
    "INFO": 1,
}


class SonarQubeDetector:
    """
    Detector de Code Smells profesional basado en SonarQube.

    Gestiona el ciclo de vida completo: arranque del servidor,
    ejecución del análisis, consulta de resultados y extracción
    de métricas de deuda técnica.
    """

    def __init__(self):
        """
        Inicializa el detector con la configuración de SonarQube.

        Lee las variables de entorno para la conexión al servidor
        y la autenticación.
        """
        self.sonar_url = os.getenv("SONARQUBE_URL", "http://localhost:9000")
        self.sonar_token = os.getenv("SONARQUBE_TOKEN", "")
        self.sonarqube_path = os.getenv(
            "SONARQUBE_PATH",
            r"C:\Users\edils\OneDrive\Documents\UNSA\sonar"
            r"\sonarqube-26.6.0.123539\sonarqube-26.6.0.123539"
        )
        self.scanner_path = None
        self.proceso_servidor = None

        # Credenciales por defecto de SonarQube (instalación nueva)
        self._usuario = "admin"
        self._password = "admin"

    # =========================================================================
    # Comunicación HTTP con la API
    # =========================================================================

    def _hacer_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict = None,
        data: dict = None,
        auth: tuple = None,
    ) -> dict:
        """
        Realiza una petición HTTP a la API REST de SonarQube.

        Usa urllib (librería estándar) para evitar dependencias externas.

        Args:
            endpoint: Ruta del endpoint (ej: "/api/system/status").
            method: Método HTTP (GET o POST).
            params: Parámetros de query string.
            data: Datos para POST (form-urlencoded).
            auth: Tupla (usuario, password) para Basic Auth.

        Returns:
            Diccionario con la respuesta JSON.
        """
        url = f"{self.sonar_url}{endpoint}"

        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        body = None
        if data:
            body = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Accept", "application/json")

        # Autenticación
        if auth:
            credenciales = base64.b64encode(
                f"{auth[0]}:{auth[1]}".encode()
            ).decode()
            req.add_header("Authorization", f"Basic {credenciales}")
        elif self.sonar_token:
            credenciales = base64.b64encode(
                f"{self.sonar_token}:".encode()
            ).decode()
            req.add_header("Authorization", f"Basic {credenciales}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                contenido = resp.read().decode("utf-8")
                if contenido:
                    return json.loads(contenido)
                return {}
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {e.code} en {endpoint}: {cuerpo}"
            )
        except urllib.error.URLError as e:
            raise ConnectionError(f"No se puede conectar a {url}: {e.reason}")

    # =========================================================================
    # Gestión del servidor SonarQube
    # =========================================================================

    def servidor_esta_activo(self) -> bool:
        """Verifica si el servidor SonarQube está respondiendo."""
        try:
            resp = self._hacer_request("/api/system/status")
            return resp.get("status") == "UP"
        except (ConnectionError, RuntimeError, Exception):
            return False

    def iniciar_servidor(self, timeout: int = 180) -> bool:
        """
        Arranca el servidor SonarQube si no está corriendo.

        Ejecuta StartSonar.bat como proceso en background y espera
        a que el servidor responda con status UP. Configura automáticamente
        el JRE bundled si es necesario.

        Args:
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            True si el servidor está operativo.
        """
        # Verificar si ya está corriendo
        if self.servidor_esta_activo():
            print("  ✓ SonarQube ya está corriendo")
            return True

        # Buscar el script de arranque
        start_script = os.path.join(
            self.sonarqube_path, "bin", "windows-x86-64", "StartSonar.bat"
        )

        if not os.path.isfile(start_script):
            print(f"  ✗ No se encontró StartSonar.bat en: {start_script}")
            print(f"    Verifica SONARQUBE_PATH en .env")
            return False

        # Configurar el JRE bundled
        java_path = self._configurar_jre()
        if not java_path:
            print("  ✗ No se pudo configurar Java para SonarQube")
            return False

        # Preparar entorno con SONAR_JAVA_PATH
        entorno = os.environ.copy()
        entorno["SONAR_JAVA_PATH"] = java_path

        # Arrancar el servidor
        print(f"  → Arrancando SonarQube desde: {start_script}")
        print(f"    Java: {java_path}")
        print(f"    Esto puede tardar 30-90 segundos...")

        try:
            self.proceso_servidor = subprocess.Popen(
                [start_script],
                cwd=os.path.dirname(start_script),
                env=entorno,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except OSError as e:
            print(f"  ✗ Error al arrancar SonarQube: {e}")
            return False

        # Esperar a que el servidor esté listo
        return self._esperar_servidor(timeout)

    def _configurar_jre(self) -> str | None:
        """
        Configura el JRE para SonarQube.

        Busca el JRE bundled en el directorio jres/ de SonarQube.
        Si el ZIP de Windows aún no está extraído, lo extrae automáticamente.

        Returns:
            Ruta al ejecutable java.exe, o None si no se encuentra.
        """
        jres_dir = os.path.join(self.sonarqube_path, "jres")

        if not os.path.isdir(jres_dir):
            print("  ⚠ No se encontró directorio jres/ en SonarQube")
            # Intentar con java del PATH
            import shutil
            java_en_path = shutil.which("java")
            if java_en_path:
                print(f"  → Usando Java del PATH: {java_en_path}")
                return java_en_path
            return None

        # Buscar un JRE ya extraído
        for entrada in os.listdir(jres_dir):
            ruta = os.path.join(jres_dir, entrada)
            if os.path.isdir(ruta) and ("jdk" in entrada.lower() or "jre" in entrada.lower()):
                java_exe = os.path.join(ruta, "bin", "java.exe")
                if os.path.isfile(java_exe):
                    print(f"  ✓ JRE encontrado: {java_exe}")
                    return java_exe

        # Si no hay JRE extraído, buscar el ZIP de Windows y extraerlo
        for entrada in os.listdir(jres_dir):
            if "windows" in entrada.lower() and entrada.endswith(".zip"):
                zip_path = os.path.join(jres_dir, entrada)
                print(f"  → Extrayendo JRE desde: {entrada}...")
                import zipfile
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(jres_dir)
                    print("  ✓ JRE extraído exitosamente")
                    # Buscar de nuevo
                    return self._configurar_jre()
                except Exception as e:
                    print(f"  ✗ Error al extraer JRE: {e}")
                    return None

        print("  ✗ No se encontró JRE para Windows en jres/")
        return None

    def _esperar_servidor(self, timeout: int = 180) -> bool:
        """
        Espera hasta que SonarQube responda con status UP.

        Realiza polling cada 5 segundos al endpoint /api/system/status.

        Args:
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            True si el servidor está operativo antes del timeout.
        """
        inicio = time.time()
        intentos = 0

        while time.time() - inicio < timeout:
            intentos += 1
            transcurrido = int(time.time() - inicio)
            sys.stdout.write(
                f"\r    Esperando al servidor... ({transcurrido}s / {timeout}s)"
            )
            sys.stdout.flush()

            try:
                resp = self._hacer_request("/api/system/status")
                status = resp.get("status", "")

                if status == "UP":
                    print(f"\n  ✓ SonarQube operativo (tardó {transcurrido}s)")
                    return True
                elif status in ("STARTING", "RESTARTING", "DB_MIGRATION_RUNNING"):
                    pass  # Continuar esperando
                elif status == "DOWN":
                    print(f"\n  ✗ SonarQube reportó estado DOWN")
                    return False
            except (ConnectionError, Exception):
                pass  # El servidor aún no responde

            time.sleep(5)

        print(f"\n  ✗ Timeout: SonarQube no arrancó en {timeout}s")
        return False

    # =========================================================================
    # Autenticación y configuración inicial
    # =========================================================================

    def configurar_autenticacion(self) -> bool:
        """
        Configura la autenticación con SonarQube.

        En una instalación nueva, las credenciales por defecto son
        admin/admin. Este método:
        1. Verifica si ya hay un token configurado en .env
        2. Si no, intenta autenticar con admin/admin
        3. Si se requiere cambio de contraseña, lo realiza
        4. Genera un token de acceso para futuras ejecuciones

        Returns:
            True si la autenticación fue exitosa.
        """
        # Si ya tenemos token, verificar que funcione
        if self.sonar_token:
            try:
                self._hacer_request("/api/authentication/validate")
                print("  ✓ Autenticación con token existente: OK")
                return True
            except Exception:
                print("  ⚠ Token existente no es válido, intentando reconfigurar...")
                self.sonar_token = ""

        # Intentar con credenciales por defecto
        print("  → Configurando autenticación con SonarQube...")

        try:
            # Intentar obtener información con admin/admin
            resp = self._hacer_request(
                "/api/authentication/validate",
                auth=(self._usuario, self._password)
            )

            if resp.get("valid", False):
                print("  ✓ Autenticación con credenciales por defecto: OK")

                # Generar un token para uso futuro
                return self._generar_token()
            else:
                print("  ⚠ Credenciales por defecto rechazadas")
                print("    Configura SONARQUBE_TOKEN en .env")
                return False

        except RuntimeError as e:
            if "401" in str(e):
                # La contraseña ya fue cambiada, necesitamos token
                print("  ⚠ La contraseña de admin fue cambiada.")
                print("    Genera un token en: http://localhost:9000/account/security")
                print("    Y configúralo como SONARQUBE_TOKEN en .env")
                return False
            raise

    def _generar_token(self) -> bool:
        """
        Genera un token de acceso para la API de SonarQube.

        Returns:
            True si el token fue generado exitosamente.
        """
        nombre_token = "pipeline-refactorizacion"

        try:
            # Primero, intentar revocar un token anterior con el mismo nombre
            try:
                self._hacer_request(
                    "/api/user_tokens/revoke",
                    method="POST",
                    data={"name": nombre_token},
                    auth=(self._usuario, self._password),
                )
            except Exception:
                pass  # No importa si no existe

            # Generar nuevo token
            resp = self._hacer_request(
                "/api/user_tokens/generate",
                method="POST",
                data={"name": nombre_token},
                auth=(self._usuario, self._password),
            )

            token = resp.get("token", "")
            if token:
                self.sonar_token = token
                print(f"  ✓ Token generado: {token[:8]}...")

                # Guardar el token en .env para futuros usos
                self._guardar_token_en_env(token)
                return True

        except RuntimeError as e:
            print(f"  ⚠ No se pudo generar token: {e}")

        # Usar basic auth como fallback
        print("  → Usando autenticación básica (admin/admin)")
        return True

    def _guardar_token_en_env(self, token: str):
        """Guarda el token generado en el archivo .env."""
        env_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".env"
        )

        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    contenido = f.read()

                if "SONARQUBE_TOKEN=" in contenido:
                    lineas = contenido.split("\n")
                    lineas = [
                        f"SONARQUBE_TOKEN={token}"
                        if l.startswith("SONARQUBE_TOKEN=") else l
                        for l in lineas
                    ]
                    contenido = "\n".join(lineas)
                else:
                    contenido += f"\nSONARQUBE_TOKEN={token}\n"

                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(contenido)

                print(f"  ✓ Token guardado en .env")
        except Exception as e:
            print(f"  ⚠ No se pudo guardar el token en .env: {e}")
            print(f"    Guárdalo manualmente: SONARQUBE_TOKEN={token}")

    # =========================================================================
    # Gestión de proyectos
    # =========================================================================

    def crear_proyecto(self, project_key: str, project_name: str) -> bool:
        """
        Crea un proyecto en SonarQube si no existe.

        Args:
            project_key: Clave única del proyecto.
            project_name: Nombre legible del proyecto.

        Returns:
            True si el proyecto existe o fue creado exitosamente.
        """
        # Verificar si ya existe
        try:
            resp = self._hacer_request(
                "/api/projects/search",
                params={"q": project_key}
            )
            proyectos = resp.get("components", [])
            for p in proyectos:
                if p.get("key") == project_key:
                    print(f"  ✓ Proyecto '{project_key}' ya existe en SonarQube")
                    return True
        except Exception:
            pass

        # Crear el proyecto
        try:
            self._hacer_request(
                "/api/projects/create",
                method="POST",
                data={
                    "project": project_key,
                    "name": project_name,
                },
            )
            print(f"  ✓ Proyecto '{project_key}' creado en SonarQube")
            return True
        except RuntimeError as e:
            if "already exist" in str(e).lower() or "400" in str(e):
                print(f"  ✓ Proyecto '{project_key}' ya existe")
                return True
            print(f"  ✗ Error al crear proyecto: {e}")
            return False

    # =========================================================================
    # Ejecución del análisis
    # =========================================================================

    def ejecutar_analisis(
        self, directorio_codigo: str, project_key: str
    ) -> bool:
        """
        Ejecuta el sonar-scanner sobre el código fuente del repositorio.

        El scanner envía el código al servidor SonarQube para su análisis
        estático completo (code smells, bugs, vulnerabilidades, etc.)

        Args:
            directorio_codigo: Ruta al directorio del repositorio clonado.
            project_key: Clave del proyecto en SonarQube.

        Returns:
            True si el análisis se ejecutó y completó exitosamente.
        """
        # Obtener la ruta del scanner
        if not self.scanner_path:
            print("  → Verificando Sonar Scanner CLI...")
            self.scanner_path = obtener_scanner()

        # Construir el comando del scanner
        # Excluimos carpetas que no aportan al análisis
        token_arg = self.sonar_token if self.sonar_token else ""
        auth_param = f"-Dsonar.token={token_arg}" if token_arg else (
            f"-Dsonar.login={self._usuario} -Dsonar.password={self._password}"
        )

        comando = (
            f'"{self.scanner_path}"'
            f" -Dsonar.projectKey={project_key}"
            f" -Dsonar.sources=."
            f" -Dsonar.host.url={self.sonar_url}"
            f" {auth_param}"
            f" -Dsonar.sourceEncoding=UTF-8"
            f" -Dsonar.exclusions="
            f"**/__pycache__/**,**/venv/**,**/.venv/**,"
            f"**/node_modules/**,**/.git/**,**/.tox/**,"
            f"**/tests/**,**/test/**,**/*.pyc"
        )

        print(f"  → Ejecutando análisis SonarQube...")
        print(f"    Directorio: {directorio_codigo}")
        print(f"    Proyecto: {project_key}")

        try:
            resultado = subprocess.run(
                comando,
                cwd=directorio_codigo,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos máximo
            )

            if resultado.returncode == 0:
                print("  ✓ Análisis SonarQube ejecutado exitosamente")
            else:
                print(f"  ✗ El scanner terminó con código {resultado.returncode}")
                if resultado.stderr:
                    # Mostrar las últimas líneas del error
                    lineas_error = resultado.stderr.strip().split("\n")
                    for linea in lineas_error[-5:]:
                        print(f"    {linea}")
                return False

        except subprocess.TimeoutExpired:
            print("  ✗ Timeout: el análisis tardó más de 5 minutos")
            return False
        except FileNotFoundError:
            print(f"  ✗ No se encontró el scanner: {self.scanner_path}")
            return False

        # Esperar a que el servidor procese el reporte
        return self._esperar_analisis_completado(project_key)

    def _esperar_analisis_completado(
        self, project_key: str, timeout: int = 120
    ) -> bool:
        """
        Espera a que SonarQube procese el reporte del análisis.

        El scanner solo envía los datos; el procesamiento ocurre
        asíncronamente en el servidor. Usamos /api/ce/activity
        para verificar el estado.

        Args:
            project_key: Clave del proyecto.
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            True si el análisis fue procesado exitosamente.
        """
        print("  → Esperando procesamiento del servidor...")
        inicio = time.time()

        while time.time() - inicio < timeout:
            try:
                resp = self._hacer_request(
                    "/api/ce/activity",
                    params={"component": project_key, "ps": 1},
                )

                tareas = resp.get("tasks", [])
                if tareas:
                    estado = tareas[0].get("status", "")
                    if estado == "SUCCESS":
                        print("  ✓ Análisis procesado exitosamente")
                        return True
                    elif estado == "FAILED":
                        error_msg = tareas[0].get("errorMessage", "desconocido")
                        print(f"  ✗ Error en el procesamiento: {error_msg}")
                        return False
                    elif estado in ("PENDING", "IN_PROGRESS"):
                        transcurrido = int(time.time() - inicio)
                        sys.stdout.write(
                            f"\r    Procesando... ({transcurrido}s)"
                        )
                        sys.stdout.flush()
            except Exception:
                pass

            time.sleep(3)

        print(f"\n  ✗ Timeout esperando procesamiento ({timeout}s)")
        return False

    # =========================================================================
    # Consulta de resultados
    # =========================================================================

    def obtener_code_smells(
        self, project_key: str, directorio_repo: str
    ) -> List[CodeSmellSonar]:
        """
        Obtiene todos los code smells detectados por SonarQube.

        Consulta la API /api/issues/search con paginación automática
        y enriquece cada issue con el código fuente extraído del archivo.

        Args:
            project_key: Clave del proyecto en SonarQube.
            directorio_repo: Ruta al repositorio clonado (para leer el código fuente).

        Returns:
            Lista de CodeSmellSonar ordenada por severidad.
        """
        print("  → Consultando code smells...")
        todos_los_smells = []
        pagina = 1
        tam_pagina = 500

        while True:
            try:
                resp = self._hacer_request(
                    "/api/issues/search",
                    params={
                        "componentKeys": project_key,
                        "types": "CODE_SMELL",
                        "ps": tam_pagina,
                        "p": pagina,
                        "statuses": "OPEN,CONFIRMED",
                    },
                )
            except RuntimeError as e:
                print(f"  ✗ Error al consultar issues: {e}")
                break

            issues = resp.get("issues", [])
            paging = resp.get("paging", {})
            total = paging.get("total", 0)

            for issue in issues:
                # Extraer el path relativo del componente
                componente = issue.get("component", "")
                # El formato es "project_key:path/to/file.py"
                archivo_relativo = componente.split(":", 1)[-1] if ":" in componente else componente

                # Determinar la severidad
                severidad = issue.get("severity", "MAJOR")

                # Mapear la regla a un tipo de smell conocido
                regla = issue.get("rule", "")
                tipo = MAPA_REGLAS_SMELL.get(regla, regla)

                smell = CodeSmellSonar(
                    regla=regla,
                    mensaje=issue.get("message", ""),
                    archivo=archivo_relativo,
                    linea=issue.get("line", 0),
                    severidad=severidad,
                    esfuerzo=issue.get("effort", issue.get("debt", "0min")),
                    tipo_smell=tipo,
                    key=issue.get("key", ""),
                    tags=issue.get("tags", []),
                )

                # Extraer el código fuente y nombre de función
                self._enriquecer_smell(smell, directorio_repo)
                todos_los_smells.append(smell)

            # Verificar paginación
            if pagina * tam_pagina >= total:
                break
            pagina += 1

        # Ordenar por severidad descendente
        todos_los_smells.sort(
            key=lambda s: ORDEN_SEVERIDAD.get(s.severidad, 0),
            reverse=True,
        )

        print(f"  ✓ Se encontraron {len(todos_los_smells)} code smells")
        return todos_los_smells

    def _enriquecer_smell(
        self, smell: CodeSmellSonar, directorio_repo: str
    ):
        """
        Enriquece un code smell con el código fuente y nombre de función.

        Lee el archivo original y usa AST para identificar la función
        que contiene la línea reportada por SonarQube.

        Args:
            smell: Code smell a enriquecer.
            directorio_repo: Ruta al repositorio clonado.
        """
        ruta_archivo = os.path.join(directorio_repo, smell.archivo)

        if not os.path.isfile(ruta_archivo):
            return

        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                contenido = f.read()
        except (UnicodeDecodeError, OSError):
            return

        # Usar AST para encontrar la función que contiene esta línea
        try:
            arbol = ast.parse(contenido)
        except SyntaxError:
            return

        lineas = contenido.split("\n")
        mejor_funcion = None
        mejor_inicio = -1

        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fin = getattr(nodo, "end_lineno", None) or len(lineas)
                if nodo.lineno <= smell.linea <= fin:
                    # Preferir la función más interna (más cercana a la línea)
                    if nodo.lineno > mejor_inicio:
                        mejor_funcion = nodo
                        mejor_inicio = nodo.lineno

        if mejor_funcion:
            smell.nombre_funcion = mejor_funcion.name
            inicio = mejor_funcion.lineno - 1
            fin = (
                getattr(mejor_funcion, "end_lineno", None)
                or len(lineas)
            )
            smell.codigo_fuente = "\n".join(lineas[inicio:fin])
        else:
            # Si no encontramos función, extraer contexto alrededor de la línea
            smell.nombre_funcion = f"<línea {smell.linea}>"
            inicio = max(0, smell.linea - 5)
            fin = min(len(lineas), smell.linea + 15)
            smell.codigo_fuente = "\n".join(lineas[inicio:fin])

    def obtener_deuda_tecnica(self, project_key: str) -> DeudaTecnica:
        """
        Obtiene las métricas globales de deuda técnica del proyecto.

        Consulta la API /api/measures/component con las métricas SQALE:
        - code_smells: cantidad total de code smells
        - sqale_index: deuda técnica total en minutos
        - sqale_debt_ratio: ratio de deuda técnica (%)
        - sqale_rating: rating de mantenibilidad (A-E)

        Args:
            project_key: Clave del proyecto en SonarQube.

        Returns:
            DeudaTecnica con las métricas calculadas.
        """
        print("  → Consultando métricas de deuda técnica...")
        deuda = DeudaTecnica()

        try:
            resp = self._hacer_request(
                "/api/measures/component",
                params={
                    "component": project_key,
                    "metricKeys": (
                        "code_smells,sqale_index,"
                        "sqale_debt_ratio,sqale_rating"
                    ),
                },
            )
        except RuntimeError as e:
            print(f"  ✗ Error al consultar métricas: {e}")
            return deuda

        medidas = resp.get("component", {}).get("measures", [])

        for medida in medidas:
            metrica = medida.get("metric", "")
            valor = medida.get("value", "0")

            if metrica == "code_smells":
                deuda.total_smells = int(valor)
            elif metrica == "sqale_index":
                deuda.deuda_minutos = int(valor)
                deuda.deuda_legible = self._minutos_a_legible(int(valor))
            elif metrica == "sqale_debt_ratio":
                deuda.deuda_ratio = float(valor)
            elif metrica == "sqale_rating":
                ratings = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}
                deuda.rating = ratings.get(valor, valor)

        print(f"  ✓ Deuda técnica: {deuda.deuda_legible} "
              f"(ratio: {deuda.deuda_ratio:.1f}%, rating: {deuda.rating})")
        return deuda

    @staticmethod
    def _minutos_a_legible(minutos: int) -> str:
        """Convierte minutos a formato legible (ej: '2d 3h 15min')."""
        if minutos < 60:
            return f"{minutos}min"

        horas = minutos // 60
        mins_restantes = minutos % 60

        if horas < 8:
            if mins_restantes:
                return f"{horas}h {mins_restantes}min"
            return f"{horas}h"

        dias = horas // 8  # 8 horas laborables por día
        horas_restantes = horas % 8

        partes = []
        if dias:
            partes.append(f"{dias}d")
        if horas_restantes:
            partes.append(f"{horas_restantes}h")
        if mins_restantes and not dias:
            partes.append(f"{mins_restantes}min")

        return " ".join(partes)

    # =========================================================================
    # Selección y reportes
    # =========================================================================

    def seleccionar_peor_smell(
        self, smells: List[CodeSmellSonar]
    ) -> Optional[CodeSmellSonar]:
        """
        Selecciona el code smell más severo de la lista.

        Prioriza por:
        1. Severidad (BLOCKER > CRITICAL > MAJOR > MINOR > INFO)
        2. Esfuerzo de remediación (mayor esfuerzo = peor)

        Excluye smells sin código fuente extraído, ya que no pueden
        ser refactorizados por el LLM.

        Args:
            smells: Lista de code smells detectados.

        Returns:
            El code smell más severo, o None si la lista está vacía.
        """
        # Filtrar smells que tengan código fuente extraído
        smells_con_codigo = [s for s in smells if s.codigo_fuente.strip()]

        if not smells_con_codigo:
            return None

        def _parsear_esfuerzo(esfuerzo: str) -> int:
            """Convierte '15min', '1h', '2h30min' a minutos."""
            total = 0
            esfuerzo = esfuerzo.lower()
            if "h" in esfuerzo:
                partes = esfuerzo.split("h")
                try:
                    total += int(partes[0].strip()) * 60
                except ValueError:
                    pass
                esfuerzo = partes[1] if len(partes) > 1 else ""
            if "min" in esfuerzo:
                try:
                    total += int(esfuerzo.replace("min", "").strip())
                except ValueError:
                    pass
            return total

        return max(
            smells_con_codigo,
            key=lambda s: (
                ORDEN_SEVERIDAD.get(s.severidad, 0),
                _parsear_esfuerzo(s.esfuerzo),
            ),
        )

    def generar_reporte(self, smells: List[CodeSmellSonar], deuda: DeudaTecnica) -> str:
        """
        Genera un reporte formateado de los code smells detectados.

        Args:
            smells: Lista de code smells.
            deuda: Métricas de deuda técnica.

        Returns:
            Reporte como cadena de texto formateada.
        """
        lineas = [
            "=" * 70,
            " REPORTE DE CODE SMELLS (SonarQube)",
            "=" * 70,
            f" Total de smells: {deuda.total_smells}",
            f" Deuda técnica: {deuda.deuda_legible}",
            f" Ratio de deuda: {deuda.deuda_ratio:.1f}%",
            f" Rating de mantenibilidad: {deuda.rating}",
            "-" * 70,
        ]

        # Mostrar los primeros 20 smells
        smells_mostrar = smells[:20]
        for i, smell in enumerate(smells_mostrar, 1):
            lineas.extend([
                f"\n  [{i}] {smell.tipo_smell}",
                f"      Regla: {smell.regla}",
                f"      Mensaje: {smell.mensaje}",
                f"      Archivo: {smell.archivo} (línea {smell.linea})",
                f"      Severidad: {smell.severidad}",
                f"      Esfuerzo: {smell.esfuerzo}",
                f"      Función: {smell.nombre_funcion}",
                "-" * 70,
            ])

        if len(smells) > 20:
            lineas.append(f"\n  ... y {len(smells) - 20} smells más.")

        return "\n".join(lineas)


# =============================================================================
# Bloque de prueba independiente
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" PRUEBA DEL DETECTOR SONARQUBE")
    print("=" * 70)

    detector = SonarQubeDetector()

    print("\n[1] Verificando servidor SonarQube...")
    if detector.servidor_esta_activo():
        print("    ✓ Servidor operativo")
    else:
        print("    → Intentando arrancar...")
        detector.iniciar_servidor()

    print("\n[2] Configurando autenticación...")
    detector.configurar_autenticacion()

    print("\nPrueba completada.")
