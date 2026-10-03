"""
Componente Environmental effects: Fog.
"""

from ._base import X3DBindableNode
from ._campos import Element, SFColor, SFFloat, SFString
from ._contexto import contexto


class X3DFogObject:
    """
    Ttipo abstrato que descreve um nó que influencia a equação de iluminação de Fog.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__() # Chama construtor da classe pai
        self.color = SFColor(node, "color", [1.0, 1.0, 1.0])
        self.fogType = SFString(node, "fogType", "LINEAR")
        self.visibilityRange = SFFloat(node, "visibilityRange", 0)


class Fog(X3DBindableNode, X3DFogObject):
    """
    Simula efeitos atmosféricos combinando objetos com a cor especificada.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "Fog" not in contexto.renderer:
            raise Exception("Fog não foi implementado.")

        contexto.renderer["Fog"](visibilityRange=self.visibilityRange,
                            color=self.color)
