"""
Componente Geometry2D: Polypoint2D, Polyline2D, Circle2D e TriangleSet2D.
"""

from typing import TYPE_CHECKING

from ._campos import Element, MFVec2f, SFBool, SFFloat
from ._contexto import contexto
from ._cores import get_colors
from ._geometria_base import X3DGeometryNode
from ._registro import registrar

if TYPE_CHECKING:
    from ._aparencia import Appearance

@registrar("X3DGeometryNode")
class Polypoint2D(X3DGeometryNode):
    """
    Pontos exibidos por um conjunto de vértices no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec2f(node, "point", [])

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.point), 2):
                points.append([self.point[i], self.point[i+1]])
            contexto.preview.pontos.append({'appearance': contexto.current_appearance,
                                       'points': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Polypoint2D" not in contexto.renderer:
            raise Exception("Polypoint2D não foi implementado.")

        colors = get_colors(appearance)
        if self.point:
            contexto.renderer["Polypoint2D"](point=self.point, colors=colors)


@registrar("X3DGeometryNode")
class Polyline2D(X3DGeometryNode):
    """
    Série de segmentos de linha contíguos no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.lineSegments = MFVec2f(node, "lineSegments", [])

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.lineSegments), 2):
                points.append([self.lineSegments[i], self.lineSegments[i+1]])
            contexto.preview.linhas.append({'appearance': contexto.current_appearance,
                                       'lines': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Polyline2D" not in contexto.renderer:
            raise Exception("Polyline2D não foi implementado.")

        colors = get_colors(appearance)
        if self.lineSegments:
            contexto.renderer["Polyline2D"](lineSegments=self.lineSegments, colors=colors)


@registrar("X3DGeometryNode")
class Circle2D(X3DGeometryNode):
    """
    Uma linha que forma um círculo no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.radius = SFFloat(node, "radius", 1)

        # Preview
        if contexto.preview:
            radius = self.radius
            contexto.preview.circulos.append({'appearance': contexto.current_appearance,
                                         'radius': radius})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Circle2D" not in contexto.renderer:
            raise Exception("Circle2D não foi implementado.")

        colors = get_colors(appearance)
        if self.radius:
            contexto.renderer["Circle2D"](radius=self.radius, colors=colors)


@registrar("X3DGeometryNode")
class TriangleSet2D(X3DGeometryNode):
    """
    Especifica um conjunto de triângulos no sistema de coordenadas 2D local.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.vertices = MFVec2f(node, "vertices", [])
        self.solid = SFBool(node, "solid", False)

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.vertices), 2):
                points.append([self.vertices[i], self.vertices[i+1]])
            contexto.preview.poligonos.append({'appearance': contexto.current_appearance,
                                          'vertices': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleSet2D" not in contexto.renderer:
            raise Exception("TriangleSet2D não foi implementado.")

        colors = get_colors(appearance)
        if self.vertices:
            contexto.renderer["TriangleSet2D"](vertices=self.vertices, colors=colors)
