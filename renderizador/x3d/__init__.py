"""
Parser X3D.

Única entrada pública do pacote: o resto vive em módulos internos, um por
componente do padrão X3D (agrupamento, aparência, geometrias, luzes, ...).
"""

from ._cores import Colors, get_colors
from ._nos import NOS_SUPORTADOS
from ._nucleo import X3D
from ._preview import Circulo, Linha, Poligono, Ponto, Preview

__all__ = [
    "X3D",
    "Circulo",
    "Colors",
    "Linha",
    "NOS_SUPORTADOS",
    "Poligono",
    "Ponto",
    "Preview",
    "get_colors",
]
