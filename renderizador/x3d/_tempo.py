"""
Componente Time: TimeSensor.
"""

from ._base import X3DSensorNode, X3DTimeDependentNode
from ._campos import Element, SFBool, SFTime
from ._contexto import contexto


class TimeSensor(X3DTimeDependentNode, X3DSensorNode):
    """
    Gera eventos conforme o tempo passa.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.cycleInterval = SFTime(node, "cycleInterval", 1)
        self.loop = SFBool(node, "loop", False)
        self.fraction_changed: float = 0

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if "TimeSensor" not in contexto.renderer:
            raise Exception("TimeSensor não foi implementado.")

        # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
        self.fraction_changed = contexto.renderer["TimeSensor"](cycleInterval=self.cycleInterval,  # type: ignore[assignment]
                                                           loop=self.loop)
