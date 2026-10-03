"""
Componente Navigation: NavigationInfo e Viewpoint.
"""

import math

from ._base import X3DBindableNode
from ._campos import Element, SFBool, SFFloat, SFRotation, SFString, SFVec3f
from ._contexto import contexto


class NavigationInfo(X3DBindableNode):
    """
    Características físicas do avatar do visualizador e do modelo de visualização.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.headlight = SFBool(node, "headlight", True)  # Valor padrão

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "NavigationInfo" not in contexto.renderer:
            raise Exception("NavigationInfo não foi implementado.")

        contexto.renderer["NavigationInfo"](headlight=self.headlight)


class X3DViewpointNode(X3DBindableNode):
    """
    Define localização no sistema de coordenadas local para visualização.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.jump = SFBool(node, "jump", True)
        self.description = SFString(node, "description", "")
        self.retainUserOffsets = SFBool(node, "retainUserOffsets", False)
        self.centerOfRotation = SFVec3f(node, "centerOfRotation", [0.0, 0.0, 0.0])
        self.position = SFVec3f(node, "position", [0, 0, 10])
        self.orientation = SFRotation(node, "orientation", [0, 0, 1, 0])


class Viewpoint(X3DViewpointNode):
    """
    Define um ponto de vista que fornece uma vista em perspectiva da cena.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.fieldOfView = SFFloat(node, "fieldOfView", math.pi/4)
        if (self.fieldOfView < 0) or (self.fieldOfView > math.pi):
            self.fieldOfView = math.pi/4

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "Viewpoint" not in contexto.renderer:
            raise Exception("Viewpoint não foi implementado.")

        contexto.renderer["Viewpoint"](position=self.position,
                                  orientation=self.orientation,
                                  fieldOfView=self.fieldOfView)
