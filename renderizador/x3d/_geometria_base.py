"""
Nós abstratos de geometria.
"""

from typing import TYPE_CHECKING

from ._base import X3DNode
from ._campos import Element, SFBool
from ._registro import MFNode, SFNode

if TYPE_CHECKING:
    from ._aparencia import Appearance

class X3DGeometryNode(X3DNode):
    """
    Este é o tipo de nó base para todas as geometrias em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização (sobrescrita pelas subclasses concretas).
        """


class X3DComposedGeometryNode(X3DGeometryNode):
    """
    Este é o tipo de nó base para toda a geometria 3D composta em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.coord = SFNode(node, "X3DCoordinateNode", None) if node is not None else None
        self.attrib: list[object] = (
            MFNode(node, "X3DVertexAttributeNode", []) if node is not None else [])
        self.fogCoord = SFNode(node, "FogCoordinate", None) if node is not None else None
        self.normal = SFNode(node, "X3DNormalNode", None) if node is not None else None
        self.texCoord = SFNode(node, "X3DTextureCoordinateNode", None) if node is not None else None
        self.ccw = SFBool(node, "ccw", True)
        self.colorPerVertex = SFBool(node, "colorPerVertex", True)
        self.normalPerVertex = SFBool(node, "normalPerVertex", True)
        self.solid = SFBool(node, "solid", True)
