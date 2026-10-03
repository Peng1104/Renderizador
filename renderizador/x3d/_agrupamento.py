"""
Componente Grouping: Transform.
"""

from ._base import X3DChildNode
from ._campos import Element, SFRotation, SFVec3f
from ._contexto import contexto
from ._registro import ChildNode, MFNode, registrar


class X3DGroupingNode(X3DChildNode):
    """
    Nó abstrato indica que os tipos de nós concretos derivados dele contêm nós filhos.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3d.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.children: list[ChildNode] = (
            MFNode(node, "X3DChildNode", []) if node is not None else [])
        self.bboxCenter = SFVec3f(node, "bboxCenter", [0, 0, 0])
        self.bboxSize = SFVec3f(node, "bboxSize", [-1, -1, -1])


@registrar("X3DChildNode")
class Transform(X3DGroupingNode):
    """
    Nó de agrupamento que define um sistema de coordenadas para seus nós filhos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3d.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.rotation = SFRotation(node, "rotation", [0, 0, 1, 0])
        self.scale = SFVec3f(node, "scale", [1, 1, 1])
        self.translation = SFVec3f(node, "translation", [0, 0, 0])
        self.center = SFVec3f(node, "center", [0, 0, 0])
        self.scaleOrientation = SFRotation(node, "scaleOrientation", [0, 0, 1, 0])

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if not all(func in contexto.renderer for func in ("Transform_in", "Transform_out")):
            raise Exception("Transform(s) não foram implementados.")

        # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
        contexto.renderer["Transform_in"](translation=self.translation,
                                     scale=self.scale,
                                     rotation=self.rotation)

        for child in self.children:
            child.render()

        contexto.renderer["Transform_out"]()  # Tira a transformação da pilha
