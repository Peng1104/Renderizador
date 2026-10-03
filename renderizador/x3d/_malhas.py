"""
Componente Rendering: TriangleSet, TriangleStripSet e IndexedTriangleStripSet.
"""

from typing import TYPE_CHECKING

from ._campos import Element, MFInt32, MFVec2f
from ._contexto import contexto
from ._cores import get_colors
from ._geometria_base import X3DComposedGeometryNode
from ._registro import registrar

if TYPE_CHECKING:
    from ._aparencia import Appearance

@registrar("X3DGeometryNode")
class TriangleSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D que representa uma coleção de triângulos individuais.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.vertices = MFVec2f(node, "vertices", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleSet" not in contexto.renderer:
            raise Exception("TriangleSet não foi implementado.")

        colors = get_colors(appearance)
        if self.coord and self.coord.point:
            # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
            contexto.renderer["TriangleSet"](point=self.coord.point, colors=colors)


@registrar("X3DGeometryNode")
class TriangleStripSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D composta por faixas de triângulos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.stripCount = MFInt32(node, "stripCount", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleStripSet" not in contexto.renderer:
            raise Exception("TriangleStripSet não foi implementado.")

        colors = get_colors(appearance)
        if self.coord and self.coord.point and self.stripCount:
            # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
            contexto.renderer["TriangleStripSet"](point=self.coord.point,
                                             stripCount=self.stripCount,
                                             colors=colors)


@registrar("X3DGeometryNode")
class IndexedTriangleStripSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D composta de tiras de triângulos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.index = MFInt32(node, "index", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "IndexedTriangleStripSet" not in contexto.renderer:
            raise Exception("IndexedTriangleStripSet não foi implementado.")

        colors = get_colors(appearance)
        if "IndexedTriangleStripSet" in contexto.renderer:
            if self.coord and self.coord.point and self.index:
                # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
                contexto.renderer["IndexedTriangleStripSet"](point=self.coord.point,
                                                        index=self.index,
                                                        colors=colors)
