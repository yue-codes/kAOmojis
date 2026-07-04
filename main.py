"""
Koemojis - Selector de Kaomojis
================================

Aplicacion de escritorio minimalista para buscar y copiar kaomojis
(¯\\_(ツ)_/¯ , (╯°□°）╯︵ ┻━┻ , etc.) al portapapeles con un par de teclas.
Pensada para usarse como un "launcher" rapido tanto en Linux
(Wayland/KDE/Hyprland) como en Windows.

Decisiones de diseno relevantes (ver README.md para el detalle completo):
- Se usa PySide6 (Qt6) en lugar de PyQt6 por su licencia LGPL.
- El portapapeles se maneja con QApplication.clipboard(), NO con una
  libreria externa (pyclip/pyperclip): asi evitamos depender de binarios
  del sistema (xclip/wl-clipboard) que no siempre estan instalados, y
  usamos el soporte nativo de Wayland que ya trae Qt.
- Los kaomojis viven en kaomojis.json (no en este archivo) para poder
  agregarlos/editarlos sin tocar codigo.
- La busqueda filtra por "tags" (palabras clave) ademas del propio
  simbolo, porque buscar por el texto literal de un kaomoji rara vez
  sirve de algo (son secuencias de simbolos, no palabras).
- Cada ejecucion es un proceso nuevo: se abre, el usuario elige un
  kaomoji (o cancela) y el proceso termina. No hay bandeja del sistema
  ni proceso residente en este prototipo.

Uso:
    python main.py

Requisitos:
    pip install -r requirements.txt
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

# --------------------------------------------------------------------------
# Configuracion / constantes
# --------------------------------------------------------------------------

DATA_FILE = Path(__file__).resolve().parent / "kaomojis.json"

WINDOW_WIDTH = 480
WINDOW_HEIGHT = 420
GRID_COLUMNS = 3  # columnas de la cuadricula de kaomojis

# Hoja de estilo (QSS, similar a CSS) para el tema oscuro minimalista.
# Todo el "look" de la app vive aqui para no mezclar estilos con logica.
# Nota: "KaomojiButton" y "SearchBar" no son selectores de clase CSS
# (Qt no soporta esa sintaxis); son el nombre real de las clases Python
# definidas mas abajo, que Qt usa como selector de tipo en QSS.
STYLESHEET = """
#Container {
    background-color: #1e1e2e;
    border-radius: 14px;
    border: 1px solid #313244;
}

SearchBar {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
}

QTabBar::tab {
    background: transparent;
    color: #a6adc8;
    padding: 6px 14px;
    font-size: 12px;
}

QTabBar::tab:selected {
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}

KaomojiButton {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    font-size: 13px;
}

KaomojiButton:hover {
    background-color: #45475a;
}

KaomojiButton[selected="true"] {
    background-color: #89b4fa;
    color: #1e1e2e;
}

QLabel#EmptyLabel {
    color: #6c7086;
    font-size: 13px;
}
"""


def load_kaomojis():
    """Carga kaomojis.json y devuelve [(categoria, [entradas]), ...].

    Cada entrada es un dict {"kaomoji": str, "tags": [str, ...]}. Se
    preserva el orden del archivo (los dict de Python mantienen el
    orden de insercion desde 3.7+), asi las pestañas salen en el mismo
    orden en que estan escritas en el JSON.
    """
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return list(raw.items())


class SearchBar(QLineEdit):
    """QLineEdit especializado que convierte teclas de navegacion en
    señales, en vez de dejar que Qt las use para mover el cursor de
    texto.

    Es necesario porque el foco de teclado SIEMPRE esta en la barra de
    busqueda (asi lo pide el flujo tipo "launcher"), pero igual
    queremos que las flechas muevan la seleccion en la cuadricula de
    kaomojis en lugar del cursor de texto.
    """

    navigate = Signal(int, int)  # (dx, dy) para moverse en la cuadricula
    confirmed = Signal()  # Enter -> copiar la seleccion actual
    cancelled = Signal()  # Escape -> cerrar sin copiar
    next_tab = Signal()  # Tab -> siguiente categoria
    prev_tab = Signal()  # Shift+Tab -> categoria anterior

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Up:
            self.navigate.emit(0, -1)
        elif key == Qt.Key_Down:
            self.navigate.emit(0, 1)
        elif key == Qt.Key_Left:
            self.navigate.emit(-1, 0)
        elif key == Qt.Key_Right:
            self.navigate.emit(1, 0)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.confirmed.emit()
        elif key == Qt.Key_Escape:
            self.cancelled.emit()
        elif key == Qt.Key_Tab:
            self.next_tab.emit()
        elif key == Qt.Key_Backtab:  # Shift+Tab
            self.prev_tab.emit()
        else:
            # Cualquier otra tecla (letras, backspace, etc.) se
            # comporta como en un QLineEdit normal.
            super().keyPressEvent(event)


class DraggableContainer(QFrame):
    """QFrame que permite arrastrar la ventana haciendo clic y
    arrastrando cualquier zona vacia (no hay barra de titulo).

    Nota tecnica: en PySide6 no alcanza con asignar
    "instancia.mousePressEvent = alguna_funcion" sobre un QFrame
    comun, porque el despacho de eventos de Qt solo llama a un
    metodo Python si la CLASE fue definida en Python (subclaseada).
    Asignar el atributo despues, sobre una instancia de QFrame sin
    subclasificar, no lo engancha realmente. Por eso esto es una
    subclase real en vez de un parche sobre la instancia.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)


class KaomojiButton(QPushButton):
    """Boton individual para un kaomoji.

    Es una subclase minima de QPushButton que existe solo para poder
    aplicarle estilos QSS especificos via el selector de tipo
    "KaomojiButton" (ver STYLESHEET) sin tocar otros QPushButton.
    """

    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        # La navegacion por teclado se maneja a mano en KaomojiPicker
        # (ver _move_selection); el foco de Qt se queda siempre en la
        # barra de busqueda, estos botones solo reciben clicks.
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(42)


class KaomojiPicker(QWidget):
    """Ventana principal: barra de busqueda + pestañas + cuadricula.

    Flujo: escribis para filtrar (en TODAS las categorias a la vez) o
    navegas por pestañas cuando la busqueda esta vacia; con las
    flechas eliges un kaomoji y Enter (o clic) lo copia y cierra la
    app.
    """

    def __init__(self):
        super().__init__()

        self.categories = load_kaomojis()  # [(nombre, [entradas]), ...]

        # Pestaña "Todos": union de todas las categorias, se muestra
        # primera para que al abrir la app se vea todo el catalogo sin
        # tener que elegir una categoria puntual. self.categories NO
        # incluye esta pestaña (se sigue usando tal cual para la
        # busqueda global, ver _on_search_changed).
        all_entries = [entry for _name, entries in self.categories for entry in entries]
        self.tabs = [("Todos", all_entries)] + self.categories

        self.current_buttons = []  # botones visibles ahora mismo, en orden
        self.selected_index = 0
        self.is_searching = False

        self._build_ui()
        self._connect_signals()

        # Al abrir, se muestra la primera categoria (busqueda vacia).
        self._show_category(0)

    # -- construccion de la interfaz -------------------------------------

    def _build_ui(self):
        # Ventana sin bordes de SO, sin entrada en la barra de tareas
        # (Qt.Tool) y siempre por encima de otras ventanas.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)

        # Fondo transparente: se necesita para que las esquinas
        # redondeadas del contenedor interno (ver "#Container" en el
        # QSS) no queden "recortadas" por un rectangulo de fondo
        # cuadrado detras. Sin esto, una ventana frameless con
        # border-radius se ve con las esquinas mal en Linux y Windows.
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLESHEET)

        # Contenedor interno: es el que realmente pinta el fondo
        # oscuro y el borde redondeado (la ventana en si es
        # transparente, ver comentario de arriba). No usamos un
        # layout en "self" a proposito: este es el unico hijo directo
        # y ocupa toda la ventana.
        container = DraggableContainer(self)
        container.setObjectName("Container")
        container.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        self.search_bar = SearchBar()
        self.search_bar.setPlaceholderText("Buscar kaomoji... (ej: feliz, mesa, shrug)")
        layout.addWidget(self.search_bar)

        self.tab_bar = QTabBar()
        for name, _entries in self.tabs:
            self.tab_bar.addTab(name)
        layout.addWidget(self.tab_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        # Se fuerza transparencia en el area de scroll y su contenido
        # para que se vea el fondo oscuro del contenedor y no un
        # rectangulo claro/blanco por defecto detras de la cuadricula.
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        grid_host = QWidget()
        grid_host.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_host)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignTop)
        for col in range(GRID_COLUMNS):
            self.grid_layout.setColumnStretch(col, 1)

        self.scroll_area.setWidget(grid_host)
        layout.addWidget(self.scroll_area, stretch=1)

        self.empty_label = QLabel("Sin resultados")
        self.empty_label.setObjectName("EmptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

    def _connect_signals(self):
        self.search_bar.textChanged.connect(self._on_search_changed)
        self.search_bar.navigate.connect(self._move_selection)
        self.search_bar.confirmed.connect(self._confirm_selection)
        self.search_bar.cancelled.connect(self.close)
        self.search_bar.next_tab.connect(self._go_to_next_tab)
        self.search_bar.prev_tab.connect(self._go_to_prev_tab)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)

    # -- categorias / pestañas --------------------------------------------

    def _show_category(self, index):
        """Muestra la cuadricula completa de una pestaña ("Todos" o
        una categoria puntual), modo "navegar" cuando la busqueda
        esta vacia."""
        _name, entries = self.tabs[index]
        self._populate_grid(entries)

    def _on_tab_changed(self, index):
        # Mientras se esta buscando, la barra de pestañas esta oculta
        # y se ignoran los cambios (defensivo: no deberia dispararse).
        if self.is_searching or index < 0:
            return
        self._show_category(index)

    def _go_to_next_tab(self):
        if self.is_searching:
            return
        count = self.tab_bar.count()
        self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() + 1) % count)

    def _go_to_prev_tab(self):
        if self.is_searching:
            return
        count = self.tab_bar.count()
        self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() - 1) % count)

    # -- busqueda ----------------------------------------------------------

    def _on_search_changed(self, text):
        query = text.strip().lower()

        if not query:
            self.is_searching = False
            self.tab_bar.show()
            self._show_category(self.tab_bar.currentIndex())
            return

        # Buscando: se ignoran las pestañas y se combinan resultados de
        # TODAS las categorias. Se compara contra el propio kaomoji y
        # contra sus "tags" (palabras clave en español), porque el
        # simbolo en si mismo casi nunca coincide con lo que alguien
        # escribe en el teclado.
        self.is_searching = True
        self.tab_bar.hide()

        results = []
        for _name, entries in self.categories:
            for entry in entries:
                haystack = entry["kaomoji"].lower() + " " + " ".join(entry.get("tags", [])).lower()
                if query in haystack:
                    results.append(entry)

        self._populate_grid(results)

    # -- cuadricula de botones ---------------------------------------------

    def _populate_grid(self, entries):
        # Se limpia la cuadricula anterior antes de reconstruirla.
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.current_buttons = []
        self.empty_label.setVisible(len(entries) == 0)
        self.scroll_area.setVisible(len(entries) > 0)

        for index, entry in enumerate(entries):
            text = entry["kaomoji"]
            button = KaomojiButton(text)
            button.clicked.connect(lambda checked=False, t=text: self._copy_and_close(t))

            row, col = divmod(index, GRID_COLUMNS)
            self.grid_layout.addWidget(button, row, col)
            self.current_buttons.append(button)

        self.selected_index = 0
        self._refresh_selection_style()

    def _refresh_selection_style(self):
        """Repinta que boton esta "seleccionado" (resaltado) segun
        self.selected_index, y hace scroll para que quede visible."""
        for i, button in enumerate(self.current_buttons):
            is_selected = i == self.selected_index
            button.setProperty("selected", "true" if is_selected else "false")
            # Qt no reaplica el QSS solo porque cambio una property
            # dinamica; hay que forzarlo con unpolish/polish.
            button.style().unpolish(button)
            button.style().polish(button)

        if self.current_buttons:
            self.scroll_area.ensureWidgetVisible(self.current_buttons[self.selected_index])

    def _move_selection(self, dx, dy):
        if not self.current_buttons:
            return

        total = len(self.current_buttons)
        row, _col = divmod(self.selected_index, GRID_COLUMNS)

        if dx != 0:
            # Izquierda/derecha: se mueve dentro de la misma fila, sin
            # saltar a la fila de arriba/abajo en los extremos.
            new_index = self.selected_index + dx
            if 0 <= new_index < total and divmod(new_index, GRID_COLUMNS)[0] == row:
                self.selected_index = new_index
        elif dy != 0:
            new_index = self.selected_index + dy * GRID_COLUMNS
            if 0 <= new_index < total:
                self.selected_index = new_index

        self._refresh_selection_style()

    def _confirm_selection(self):
        if not self.current_buttons:
            return
        self.current_buttons[self.selected_index].click()

    # -- copiar y cerrar -----------------------------------------------------

    def _copy_and_close(self, text):
        # QApplication.clipboard() es el portapapeles nativo de Qt:
        # funciona igual en X11, Wayland (Hyprland/KDE) y Windows sin
        # depender de binarios externos como xclip o wl-clipboard.
        QApplication.clipboard().setText(text)
        self.close()


def main():
    app = QApplication(sys.argv)

    picker = KaomojiPicker()

    # Centrar la ventana en la pantalla principal.
    screen = QGuiApplication.primaryScreen().availableGeometry()
    x = screen.center().x() - picker.width() // 2
    y = screen.center().y() - picker.height() // 2
    picker.move(x, y)

    picker.show()
    picker.search_bar.setFocus()  # foco automatico en la busqueda

    # QApplication cierra el event loop solo cuando se cierra la
    # ultima ventana visible (comportamiento por defecto de Qt), asi
    # que basta con picker.close() en cualquier punto de la app.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
