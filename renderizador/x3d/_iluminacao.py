"""
Componente Lighting: DirectionalLight e PointLight.
"""

from ._base import X3DChildNode
from ._campos import Element, SFBool, SFColor, SFFloat, SFVec3f
from ._contexto import contexto


class X3DLightNode(X3DChildNode):
    """
    Nó abstrato base para todos os tipos de luzes.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.ambientIntensity = SFFloat(node, "ambientIntensity", 0)
        self.color = SFColor(node, "color", [1.0, 1.0, 1.0])
        self.intensity = SFFloat(node, "intensity", 1)
        self.on = SFBool(node, "on", True)


class DirectionalLight(X3DLightNode):
    """
    Conjunto de coordenadas de textura 2D usadas por nós de geometria baseados em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.direction = SFVec3f(node, "direction", [0.0, 0.0, -1.0])

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "DirectionalLight" not in contexto.renderer:
            raise Exception("DirectionalLight não foi implementado.")

        if not self.on:
            return

        contexto.renderer["DirectionalLight"](ambientIntensity=self.ambientIntensity,
                                         color=self.color,
                                         intensity=self.intensity,
                                         direction=self.direction)


class PointLight(X3DLightNode):
    """
    Conjunto de coordenadas de textura 2D usadas por nós de geometria baseados em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.location = SFVec3f(node, "location", [0.0, 0.0, 0.0])

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "PointLight" not in contexto.renderer:
            raise Exception("PointLight não foi implementado.")

        contexto.renderer["PointLight"](ambientIntensity=self.ambientIntensity,
                                   color=self.color,
                                   intensity=self.intensity,
                                   location=self.location)
