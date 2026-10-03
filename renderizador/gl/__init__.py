"""
Biblioteca gráfica (Graphics Library) do renderizador.

Única entrada pública do pacote: o resto vive em módulos internos, um por
domínio (matrizes, rasterização, texturas, iluminação, nós X3D, animação).
"""

from ._nucleo import GL, Colors, definir_relogio

__all__ = ["GL", "Colors", "definir_relogio"]
