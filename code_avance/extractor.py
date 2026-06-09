"""
=============================================================================
 extractor.py - Módulo de Extracción de Código Fuente
=============================================================================
 Primer Avance - Tesis:

 Descripción:
    Este módulo se encarga de clonar un repositorio Python de código abierto
    usando la librería GitPython, y extraer archivos .py para su posterior
    análisis de code smells.

 Funcionalidades:
    - Clonar un repositorio Git desde una URL
    - Listar todos los archivos Python (.py) del repositorio
    - Leer y retornar el contenido de archivos específicos
    - Extraer funciones/clases individuales como cadenas de texto
=============================================================================
"""

import os
import shutil
from typing import List, Dict, Optional

# GitPython para clonar y gestionar repositorios
from git import Repo, InvalidGitRepositoryError, GitCommandError


class ExtractorDeCodigo:
    """
    Clase encargada de clonar repositorios Git y extraer código fuente Python.
    
    Esta clase implementa el primer paso del pipeline de refactorización:
    obtener el código fuente de un proyecto real de código abierto para
    analizarlo en busca de code smells.
    
    Atributos:
        url_repositorio (str): URL del repositorio Git a clonar.
        directorio_clon (str): Ruta local donde se clonará el repositorio.
        repositorio (Repo): Instancia del repositorio clonado (GitPython).
    """

    def __init__(self, url_repositorio: str, directorio_clon: str = "./repos_clonados"):
        """
        Inicializa el extractor con la URL del repositorio objetivo.

        Args:
            url_repositorio: URL completa del repositorio Git
                             (ej: https://github.com/psf/requests.git)
            directorio_clon: Directorio base donde se almacenarán los clones.
                             Por defecto: ./repos_clonados
        """
        self.url_repositorio = url_repositorio
        # Extraer el nombre del repositorio de la URL para crear un subdirectorio
        self.nombre_repo = url_repositorio.rstrip("/").split("/")[-1].replace(".git", "")
        self.directorio_clon = os.path.join(directorio_clon, self.nombre_repo)
        self.repositorio: Optional[Repo] = None

    def clonar_repositorio(self, profundidad: int = 1) -> str:
        """
        Clona el repositorio Git en el directorio local especificado.
        
        Usa un clon superficial (shallow clone) por defecto para ahorrar
        tiempo y espacio en disco, ya que solo necesitamos el código actual,
        no el historial completo.

        Args:
            profundidad: Profundidad del clon (1 = solo último commit).
                         Un clon superficial es suficiente para análisis estático.

        Returns:
            str: Ruta absoluta del directorio donde se clonó el repositorio.

        Raises:
            GitCommandError: Si ocurre un error durante la clonación
                             (ej: URL inválida, sin conexión a internet).
        """
        # Si ya existe el directorio, verificar si es un repositorio válido
        if os.path.exists(self.directorio_clon):
            try:
                self.repositorio = Repo(self.directorio_clon)
                print(f"  ✓ Repositorio ya existe en: {self.directorio_clon}")
                print(f"    Último commit: {self.repositorio.head.commit.hexsha[:8]}")
                return self.directorio_clon
            except InvalidGitRepositoryError:
                # El directorio existe pero no es un repo válido; eliminarlo
                print(f"  ⚠ Directorio corrupto, re-clonando...")
                shutil.rmtree(self.directorio_clon)

        try:
            print(f"  → Clonando repositorio: {self.url_repositorio}")
            print(f"    Destino: {self.directorio_clon}")
            print(f"    Profundidad: {profundidad} (clon superficial)")

            # Clonar con profundidad limitada para eficiencia
            self.repositorio = Repo.clone_from(
                url=self.url_repositorio,
                to_path=self.directorio_clon,
                depth=profundidad  # Solo el último commit
            )

            print(f"  ✓ Clonación exitosa")
            print(f"    Commit: {self.repositorio.head.commit.hexsha[:8]}")
            print(f"    Autor: {self.repositorio.head.commit.author.name}")
            return self.directorio_clon

        except GitCommandError as e:
            print(f"  ✗ Error al clonar el repositorio: {e}")
            raise

    def listar_archivos_python(self) -> List[str]:
        """
        Lista todos los archivos .py encontrados en el repositorio clonado.
        
        Recorre recursivamente el directorio del repositorio buscando
        archivos con extensión .py, excluyendo directorios comunes que
        no contienen código fuente relevante (tests, migraciones, etc.).

        Returns:
            Lista de rutas relativas a archivos Python encontrados.
        """
        archivos_python = []
        
        # Directorios a excluir del análisis (no relevantes para code smells)
        directorios_excluidos = {
            '__pycache__', '.git', '.tox', '.eggs', 'node_modules',
            'venv', '.venv', 'env', 'migrations', '.github'
        }

        for raiz, directorios, archivos in os.walk(self.directorio_clon):
            # Filtrar directorios excluidos para no recorrerlos
            directorios[:] = [
                d for d in directorios if d not in directorios_excluidos
            ]

            for archivo in archivos:
                if archivo.endswith('.py'):
                    ruta_completa = os.path.join(raiz, archivo)
                    # Guardar ruta relativa al repositorio para legibilidad
                    ruta_relativa = os.path.relpath(ruta_completa, self.directorio_clon)
                    archivos_python.append(ruta_relativa)

        print(f"  ✓ Se encontraron {len(archivos_python)} archivos Python")
        return sorted(archivos_python)

    def leer_archivo(self, ruta_relativa: str) -> str:
        """
        Lee y retorna el contenido completo de un archivo Python.

        Args:
            ruta_relativa: Ruta relativa al archivo dentro del repositorio.

        Returns:
            Contenido del archivo como cadena de texto.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            UnicodeDecodeError: Si el archivo no puede ser decodificado como UTF-8.
        """
        ruta_completa = os.path.join(self.directorio_clon, ruta_relativa)

        if not os.path.exists(ruta_completa):
            raise FileNotFoundError(
                f"Archivo no encontrado: {ruta_relativa}"
            )

        try:
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                contenido = f.read()
            print(f"  ✓ Archivo leído: {ruta_relativa} ({len(contenido)} caracteres)")
            return contenido
        except UnicodeDecodeError:
            # Algunos archivos pueden tener codificación diferente
            with open(ruta_completa, 'r', encoding='latin-1') as f:
                contenido = f.read()
            print(f"  ⚠ Archivo leído con codificación latin-1: {ruta_relativa}")
            return contenido

    def extraer_fragmento(self, contenido: str, nombre_funcion: str) -> Optional[str]:
        """
        Extrae una función o clase específica del contenido de un archivo.
        
        Utiliza un análisis simple basado en indentación para identificar
        los límites de funciones y clases Python.

        Args:
            contenido: Código fuente completo del archivo.
            nombre_funcion: Nombre de la función o clase a extraer.

        Returns:
            Código de la función/clase como string, o None si no se encuentra.
        
        Nota:
            Este método usa heurísticas de indentación. Para un análisis
            más robusto se podría usar el módulo `ast` de Python.
        """
        lineas = contenido.split('\n')
        inicio = None
        indentacion_base = None
        fragmento = []

        for i, linea in enumerate(lineas):
            # Buscar la definición de la función o clase
            linea_stripped = linea.strip()
            if (linea_stripped.startswith(f'def {nombre_funcion}(') or
                linea_stripped.startswith(f'def {nombre_funcion} (') or
                linea_stripped.startswith(f'class {nombre_funcion}(') or
                linea_stripped.startswith(f'class {nombre_funcion}:') or
                linea_stripped.startswith(f'class {nombre_funcion} (')):
                
                inicio = i
                # Calcular la indentación base de la definición
                indentacion_base = len(linea) - len(linea.lstrip())
                fragmento.append(linea)
                continue

            if inicio is not None and i > inicio:
                # Verificar si la línea pertenece al bloque de la función/clase
                if linea.strip() == '':
                    # Las líneas vacías dentro del bloque se incluyen
                    fragmento.append(linea)
                elif (len(linea) - len(linea.lstrip())) > indentacion_base:
                    # Línea con mayor indentación = parte del bloque
                    fragmento.append(linea)
                else:
                    # Línea con igual o menor indentación = fin del bloque
                    break

        if fragmento:
            # Eliminar líneas vacías al final del fragmento
            while fragmento and fragmento[-1].strip() == '':
                fragmento.pop()
            resultado = '\n'.join(fragmento)
            print(f"  ✓ Fragmento extraído: '{nombre_funcion}' ({len(fragmento)} líneas)")
            return resultado
        
        print(f"  ✗ No se encontró el fragmento: '{nombre_funcion}'")
        return None

    def obtener_info_repositorio(self) -> Dict[str, str]:
        """
        Retorna información básica del repositorio clonado.
        Útil para el reporte de resultados del avance.

        Returns:
            Diccionario con metadatos del repositorio.
        """
        if self.repositorio is None:
            return {"error": "Repositorio no clonado aún"}

        commit = self.repositorio.head.commit
        return {
            "nombre": self.nombre_repo,
            "url": self.url_repositorio,
            "commit": commit.hexsha[:8],
            "autor_commit": str(commit.author),
            "fecha_commit": str(commit.committed_datetime),
            "mensaje_commit": commit.message.strip(),
        }


# =============================================================================
# Bloque de prueba independiente
# Permite ejecutar este módulo de forma aislada para verificar su funcionamiento
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" PRUEBA DEL MÓDULO EXTRACTOR DE CÓDIGO")
    print("=" * 70)

    # Ejemplo: clonar el repositorio 'requests' de Kenneth Reitz
    extractor = ExtractorDeCodigo(
        url_repositorio="https://github.com/psf/requests.git",
        directorio_clon="./repos_clonados"
    )

    print("\n[1] Clonando repositorio...")
    extractor.clonar_repositorio()

    print("\n[2] Listando archivos Python...")
    archivos = extractor.listar_archivos_python()
    for archivo in archivos[:10]:  # Mostrar solo los primeros 10
        print(f"    - {archivo}")
    if len(archivos) > 10:
        print(f"    ... y {len(archivos) - 10} archivos más")

    print("\n[3] Información del repositorio:")
    info = extractor.obtener_info_repositorio()
    for clave, valor in info.items():
        print(f"    {clave}: {valor}")
