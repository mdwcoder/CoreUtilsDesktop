[Español](README.es.md) | [English](README.en.md)

---

# Core Utils Desktop

Instalador local para el ecosistema Core Utils, creado con Python y Flet.

## Ejecutar

```bash
cd core-utils-projects/CoreUtilsDesktop
./init.sh
```

`init.sh` crea `.venv`, actualiza `pip`, instala dependencias, registra el lanzador de escritorio/menu y arranca la app.

Despues de la primera instalacion puedes ejecutar directamente:

```bash
.venv/bin/python main.py
```

## Que hace

- Carga las herramientas instalables del registro `core-utils`.
- Descarga repositorios en `~/.core-utils-desktop/tools`.
- Instala herramientas Python con `pipx install --force .` cuando es posible.
- Usa scripts locales o `pip install` como fallback.
- Detecta dependencias desde `requirements.txt`, `pyproject.toml` y necesidades conocidas.
- Instala paquetes de sistema en Fedora, Debian/Ubuntu y Arch cuando corresponde.
- Muestra informes de dependencias desde el boton `Dependencias` / `Dependencies`.
- Lanza apps de escritorio desde el hub.
- Muestra README locales en un dialogo Markdown.
- Anade una seccion Forge conectada a `api.core-utils.dev` para ver conversaciones y comentarios de herramientas.
- Permite iniciar sesion con GitHub desde la app de escritorio para comentar en hilos de Forge.
- Actualiza herramientas con `git pull --ff-only` y reinstalacion.
- Desinstala con `pipx uninstall`, `pip uninstall` y eliminacion del clon gestionado.
- Instala lanzadores e iconos de escritorio.

## Estado local

La aplicacion guarda su estado en:

```text
~/.core-utils-desktop/state.json
```
