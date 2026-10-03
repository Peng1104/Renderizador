"""
ROUTE: liga a saída de um nó à entrada de outro.
"""

from ._base import X3DNode
from ._campos import Element, SFString


class ROUTE:
    """
    .
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__() # Chama construtor da classe pai
        self.fromNode = SFString(node, "fromNode", '')
        self.fromField = SFString(node, "fromField", '')
        self.toNode = SFString(node, "toNode", '')
        self.toField = SFString(node, "toField", '')

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        fromNode = X3DNode.named_nodes[self.fromNode]
        value = getattr(fromNode, self.fromField)
        toNode = X3DNode.named_nodes[self.toNode]
        setattr(toNode, self.toField, value)
