"""
Tipos do sistema de pré-visualização das geometrias 2D.
"""

from typing import TYPE_CHECKING, ClassVar, Protocol, TypedDict

if TYPE_CHECKING:
    from ._nucleo import Appearance

class Ponto(TypedDict):
    """
    Ponto (Polypoint2D) coletado durante o parse do X3D para pré-visualização.
    """

    appearance: "Appearance | None"
    points: list[list[float]]


class Linha(TypedDict):
    """
    Linha (Polyline2D) coletada durante o parse do X3D para pré-visualização.
    """

    appearance: "Appearance | None"
    lines: list[list[float]]


class Circulo(TypedDict):
    """
    Círculo (Circle2D) coletado durante o parse do X3D para pré-visualização.
    """

    appearance: "Appearance | None"
    radius: float


class Poligono(TypedDict):
    """
    Triângulo (TriangleSet2D) coletado durante o parse do X3D para pré-visualização.
    """

    appearance: "Appearance | None"
    vertices: list[list[float]]


class Preview(Protocol):
    """
    Interface mínima esperada de um sistema de pré-visualização (ver interface.Interface).
    """

    pontos: ClassVar[list[Ponto]]
    linhas: ClassVar[list[Linha]]
    circulos: ClassVar[list[Circulo]]
    poligonos: ClassVar[list[Poligono]]
