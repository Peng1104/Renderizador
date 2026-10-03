"""
Componente Geometry3D: Box, Sphere, Cone, Cylinder e IndexedFaceSet.
"""

from typing import TYPE_CHECKING

from ._campos import Element, MFInt32, SFFloat, SFVec3f
from ._contexto import contexto
from ._cores import get_colors
from ._geometria_base import X3DComposedGeometryNode, X3DGeometryNode
from ._registro import SFNode, registrar

if TYPE_CHECKING:
    from ._aparencia import Appearance

@registrar("X3DGeometryNode")
class Box(X3DGeometryNode):
    """
    Classe responsável por geometria Box, que é um paralelepípedo centro no (0,0,0).
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.size = SFVec3f(node, "size", [2, 2, 2])

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Box" not in contexto.renderer:
            raise Exception("Box não foi implementado.")

        colors = get_colors(appearance)
        if self.size:
            contexto.renderer["Box"](size=self.size, colors=colors,
                                current_texture=contexto.current_texture)


@registrar("X3DGeometryNode")
class Sphere(X3DGeometryNode):
    """
    Classe responsável por geometria Sphere, que é uma esfera com centro no (0,0,0).
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.radius = SFFloat(node, "radius", 1)

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Sphere" not in contexto.renderer:
            raise Exception("Sphere não foi implementado.")

        colors = get_colors(appearance)

        if self.radius:
            contexto.renderer["Sphere"](radius=self.radius, colors=colors,
                                   current_texture=contexto.current_texture)


@registrar("X3DGeometryNode")
class Cone(X3DGeometryNode):
    """
    Classe responsável por geometria Cone, que é um cone com centro no (0,0,0).
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.bottomRadius  = SFFloat(node, "bottomRadius", 1)
        self.height = SFFloat(node, "height", 2)

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Cone" not in contexto.renderer:
            raise Exception("Cone não foi implementado.")

        colors = get_colors(appearance)

        if self.height and self.bottomRadius:
            contexto.renderer["Cone"](bottomRadius=self.bottomRadius, height=self.height,
                                 colors=colors, current_texture=contexto.current_texture)


@registrar("X3DGeometryNode")
class Cylinder(X3DGeometryNode):
    """
    Classe responsável por geometria Cylinder, que é uma cilindro com centro no (0,0,0).
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.radius = SFFloat(node, "radius", 1)
        self.height = SFFloat(node, "height", 2)

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Cylinder" not in contexto.renderer:
            raise Exception("Cylinder não foi implementado.")

        colors = get_colors(appearance)
        
        if self.radius and self.height:
            contexto.renderer["Cylinder"](radius=self.radius, height=self.height, colors=colors,
                                     current_texture=contexto.current_texture)


@registrar("X3DGeometryNode")
class IndexedFaceSet(X3DComposedGeometryNode):
    """
    Classe responsável por geometria Indexed Face Set, que é uma malha de polígonos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.color = SFNode(node, "X3DColorNode", None)
        self.coordIndex = MFInt32(node, "coordIndex", [])
        self.colorIndex = MFInt32(node, "colorIndex", [])
        self.texCoordIndex = MFInt32(node, "texCoordIndex", [])

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "IndexedFaceSet" not in contexto.renderer:
            raise Exception("IndexedFaceSet não foi implementado.")

        ret_coord: list[float] | None = None
        ret_color: list[float] | None = None
        ret_texCoord: list[float] | None = None

        if self.coord:
            ret_coord = self.coord.point
        if self.color:
            ret_color = self.color.color
        if self.texCoord:
            ret_texCoord = self.texCoord.point

        colors = get_colors(appearance)

        if self.coordIndex:
            contexto.renderer["IndexedFaceSet"](coord=ret_coord, coordIndex=self.coordIndex,
                                           colorPerVertex=self.colorPerVertex, color=ret_color,
                                           colorIndex=self.colorIndex, texCoord=ret_texCoord,
                                           texCoordIndex=self.texCoordIndex,
                                           colors=colors,
                                           current_texture=contexto.current_texture)
