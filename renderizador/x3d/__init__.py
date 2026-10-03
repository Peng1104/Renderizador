"""
Parser X3D.

Única entrada pública do pacote: o resto vive em módulos internos, um por
componente do padrão X3D (agrupamento, aparência, geometrias, luzes, ...).
"""

from ._nucleo import X3D, Circulo, Colors, Linha, Poligono, Ponto, Preview, get_colors

__all__ = ["X3D", "Circulo", "Colors", "Linha", "Poligono", "Ponto", "Preview", "get_colors"]
