"""
Propriedades de geometria: Coordinate, Color e TextureCoordinate.
"""

from ._base import X3DNode
from ._campos import Element, MFColor, MFVec2f, MFVec3f
from ._registro import registrar


class X3DGeometricPropertyNode(X3DNode):
    """
    Nó base para todos os tipos de nós de propriedades geométricas definidos no X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DCoordinateNode(X3DGeometricPropertyNode):
    """
    Nó base para todos os tipos de nós de coordenadas em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DColorNode(X3DGeometricPropertyNode):
    """
    Nó básico para especificações de cores no X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


@registrar("X3DCoordinateNode")
class Coordinate(X3DCoordinateNode):
    """
    Define um conjunto de coordenadas 3D para nós de geometria baseada em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec3f(node, "point", [])


@registrar("X3DColorNode")
class Color(X3DColorNode):
    """
    Define um conjunto de cores RGB a serem usadas nos campos de outro nó.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.color = MFColor(node, "color", [])


class X3DTextureCoordinateNode(X3DGeometricPropertyNode):
    """
    Nó abstrato base para todos os tipos de nó que especificam coordenadas de textura.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai


@registrar("X3DTextureCoordinateNode")
class TextureCoordinate(X3DTextureCoordinateNode):
    """
    Conjunto de coordenadas de textura 2D usadas por nós de geometria baseados em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec2f(node, "point", [])

    def render(self) -> None:
        """
        Rotina de renderização.
        """
