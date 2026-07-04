# Koemojis — Selector de Kaomojis

Selector de kaomojis minimalista, pensado para usarse casi enteramente con
el teclado, con soporte real de portapapeles en Linux (X11 y Wayland:
Hyprland, KDE) y en Windows.

## Decisiones de arquitectura (por qué esta stack)

- **PySide6** en vez de PyQt6: misma API de Qt6, pero licencia LGPL (más
  libertad si algún día se quiere distribuir un binario cerrado).
- **Sin `pyclip`/`pyperclip`**: se usa `QApplication.clipboard()`, el
  portapapeles nativo de Qt. Evita depender de binarios externos como
  `xclip` o `wl-clipboard`, que no siempre están instalados, y usa el
  soporte nativo de Wayland que ya trae Qt.
- **Qt sobre Tkinter**: Qt tiene un backend nativo de Wayland (plugin QPA
  `wayland`); Tkinter depende de XWayland, menos confiable para una
  ventana flotante sin bordes en Hyprland/KDE.
- **Datos en `kaomojis.json`**, no en el código: se pueden agregar o editar
  kaomojis sin tocar `main.py`.
- **Búsqueda por tags**: cada kaomoji tiene palabras clave asociadas
  (`tags`) porque buscar por el símbolo literal casi nunca sirve de nada
  (son secuencias de caracteres, no palabras).
- **Un proceso por uso**: cada vez que se abre la app es un proceso nuevo
  que termina al copiar o cancelar. No hay bandeja del sistema ni proceso
  residente en este prototipo (se puede añadir más adelante si el arranque
  en frío resulta muy lento).

## Requisitos

- Python 3.10+
- PySide6

## Instalación y ejecución

### Linux

```bash
python -m venv venv
source venv/bin/activate      # bash/zsh
# source venv/bin/activate.fish   (si tu shell es fish)
pip install -r requirements.txt
python main.py
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Controles

- Pestaña "Todos": muestra la unión de todas las categorías; es la que se
  abre por defecto. Las demás pestañas ("Felices", "Enojados", "Clásicos")
  filtran solo esa categoría.
- Escribir: filtra en tiempo real en **todas** las categorías (por el
  texto del kaomoji o por sus tags), sin importar la pestaña activa.
- Flechas (↑ ↓ ← →): mover la selección dentro de la cuadrícula visible.
- Tab / Shift+Tab: cambiar de categoría (solo cuando la búsqueda está
  vacía).
- Enter: copiar el kaomoji seleccionado y cerrar la app.
- Clic en un kaomoji: copiarlo y cerrar la app.
- Escape: cerrar sin copiar nada.
- Arrastrar desde cualquier zona vacía de la ventana: mover la ventana (no
  tiene barra de título).

## Agregar más kaomojis

Editar `kaomojis.json`. Cada categoría es una lista de objetos con esta
forma:

```json
{"kaomoji": "(^_^)", "tags": ["feliz", "sonrisa"]}
```

No hace falta tocar `main.py` ni reiniciar nada más que la app.

## Pendiente (fuera de este prototipo, a propósito)

- Atajo de teclado global / proceso residente en bandeja del sistema para
  invocación instantánea.
- Empaquetado como ejecutable (PyInstaller, AppImage, instalador de
  Windows).
- Pegado automático en la ventana anterior (frágil en Wayland sin permisos
  especiales del compositor).
- Persistencia de estado entre sesiones (última categoría, posición de
  ventana).
