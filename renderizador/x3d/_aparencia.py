"""
Componente Shape: Shape, Appearance, Material e ImageTexture.
"""

from ._base import X3DChildNode, X3DNode
from ._campos import Element, MFString, SFBool, SFColor, SFFloat
from ._contexto import contexto
from ._registro import MFNode, SFNode, registrar


class X3DShapeNode(X3DChildNode):
    """
    Este é o tipo de nó base para todos os nós do tipo Shape.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3d.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.appearance = SFNode(node, "X3DAppearanceNode", None) if node is not None else None
        self.geometry = SFNode(node, "X3DGeometryNode", None) if node is not None else None


class X3DAppearanceNode(X3DNode):
    """
    Este é o tipo de nó básico para todos os nós do tipo Appearance.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DAppearanceChildNode(X3DNode):
    """
    Este é o tipo de nó básico para todos os nós do tipo X3DAppearanceNode.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DMaterialNode(X3DAppearanceChildNode):
    """
    Este é o tipo de nó básico para todos os nós do tipo Material.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


@registrar("X3DMaterialNode")
class Material(X3DMaterialNode):
    """
    Especifica propriedades do material de superfícies para nós de geometria associados.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.ambientIntensity = SFFloat(node, "ambientIntensity", 0.2)
        self.diffuseColor = SFColor(node, "diffuseColor", [0.8, 0.8, 0.8])
        self.emissiveColor = SFColor(node, "emissiveColor", [0.0, 0.0, 0.0])
        self.specularColor = SFColor(node, "specularColor", [0.0, 0.0, 0.0])
        self.shininess = SFFloat(node, "shininess", 0.2)
        self.transparency = SFFloat(node, "transparency", 0.0)

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        contexto.current_color["ambientIntensity"] = self.ambientIntensity
        contexto.current_color["diffuseColor"] = self.diffuseColor
        contexto.current_color["emissiveColor"] = self.emissiveColor
        contexto.current_color["specularColor"] = self.specularColor
        contexto.current_color["shininess"] = self.shininess
        contexto.current_color["transparency"] = self.transparency


class X3DTextureNode(X3DAppearanceChildNode):
    """
    Nó abstrato base para todos os tipos de nó que especificam imagens de textura.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DTexture2DNode(X3DTextureNode):
    """
    Nó abstrato base para todos os tipos de nó que especificam imagens 2D de textura.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


@registrar("X3DTextureNode")
class ImageTexture(X3DTexture2DNode):
    """
    Define mapa de textura para um arquivo de imagem e parâmetros gerais de mapeamento.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.url = MFString(node, "url", [])
        self.repeatS = SFBool(node, "repeatS", True)
        self.repeatT = SFBool(node, "repeatT", True)

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        contexto.current_texture = self.url


@registrar("X3DAppearanceNode")
class Appearance(X3DAppearanceNode):
    """
    Especifica as propriedades visuais da geometria.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai

        self.fillProperties = SFNode(node, "FillProperties", None)
        self.lineProperties = SFNode(node, "LineProperties", None)
        self.material = SFNode(node, "X3DMaterialNode", None)
        self.shaders: list[object] = MFNode(node, "X3DShaderNode", [])
        self.texture = SFNode(node, "X3DTextureNode", None)
        self.textureTransform = SFNode(node, "X3DTextureTransformNode", None)
        contexto.current_appearance = self

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        if self.material:
            self.material.render()
        if self.texture:
            self.texture.render()


@registrar("X3DChildNode")
class Shape(X3DShapeNode):
    """
    Define aparência e geometria, que são usados para criar objetos renderizados.
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
        contexto.current_texture = []  # a textura vale só para a Shape cuja Appearance a define
        if self.appearance:
            self.appearance.render()
        if self.geometry:
            self.geometry.render(self.appearance)
