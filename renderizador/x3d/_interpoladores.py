"""
Componente Interpolation: SplinePositionInterpolator e OrientationInterpolator.
"""

from ._base import X3DChildNode
from ._campos import Element, MFFloat, SFBool, SFFloat
from ._contexto import contexto


class X3DInterpolatorNode(X3DChildNode):
    """
    Base para todos os tipos de interpoladores.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.set_fraction = SFFloat(node, "set_fraction", 0)
        self.key = MFFloat(node, "key", [])  # MF<type>     [in,out] keyValue      []
        self.keyValue = MFFloat(node, "keyValue", None)
        self.value_changed: list[float] | None = None  #   [S|M]F<type> [out]    value_changed


class SplinePositionInterpolator(X3DInterpolatorNode):
    """
    Interpola não linearmente entre uma lista de vetores 3D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.closed = SFBool(node, "closed", False)

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "SplinePositionInterpolator" not in contexto.renderer:
            raise Exception("SplinePositionInterpolator não foi implementado.")

        self.value_changed = contexto.renderer["SplinePositionInterpolator"]\
            (set_fraction=self.set_fraction,  # type: ignore[assignment]
             key=self.key,
             keyValue=self.keyValue,
             closed=self.closed)


class OrientationInterpolator(X3DInterpolatorNode):
    """
    Interpola entre uma lista de valores de rotação especificados no campo keyValue.
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
        if "OrientationInterpolator" not in contexto.renderer:
            raise Exception("OrientationInterpolator não foi implementado.")

        self.value_changed = contexto.renderer["OrientationInterpolator"](  # type: ignore[assignment]
            set_fraction=self.set_fraction, key=self.key, keyValue=self.keyValue)
