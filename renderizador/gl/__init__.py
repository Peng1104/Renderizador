"""
Biblioteca gráfica (Graphics Library) do renderizador.

Única entrada pública do pacote: o resto vive em módulos internos, um por
domínio (matrizes, rasterização, texturas, iluminação, nós X3D, animação).
"""

from ._animacao import definir_relogio
from ._nucleo import GL
from ._tipos import Colors

__all__ = ["GL", "Colors", "definir_relogio"]
