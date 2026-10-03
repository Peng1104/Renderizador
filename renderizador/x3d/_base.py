"""
Nós abstratos do núcleo do X3D.
"""

from typing import ClassVar

from ._campos import Element


class X3DNode:
    """
    Nó abstrato que é o tipo base para todos os nós no sistema X3D.
    """

    named_nodes: ClassVar[dict[str, "X3DNode"]] = {}  # Dicionário com todos os nós X3D nomeados

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        if node is not None and "DEF" in node.attrib:
            self.name = node.attrib["DEF"].strip()
            X3DNode.named_nodes[self.name] = self


class X3DChildNode(X3DNode):
    """
    Nó abstrato como base para campos children, addChildren, and removeChildren.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DBindableNode(X3DChildNode):
    """
    X3DBindableNode é o tipo base abstrato para certos tipos de objetos.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DSensorNode(X3DChildNode):
    """
    X3DSensorNode é o tipo base abstrato para todos tipos de sensores.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DTimeDependentNode(X3DChildNode):
    """
    Nó abstrato que todos os tipos que dependem de tempo derivam.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
