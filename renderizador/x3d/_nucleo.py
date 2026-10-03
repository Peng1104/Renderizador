"""
Parser X3D.

Desenvolvido por: Luciano Soares <lpsoares@insper.edu.br>
Disciplina: Computação Gráfica
Data: 31 de Agosto de 2020
"""

import math
import xml.etree.ElementTree as ET
from typing import ClassVar

from ._campos import (
    Element,
    MFColor,
    MFFloat,
    MFInt32,
    MFString,
    MFVec2f,
    MFVec3f,
    SFBool,
    SFColor,
    SFFloat,
    SFRotation,
    SFString,
    SFTime,
    SFVec3f,
    clean,
)
from ._contexto import Renderer, contexto
from ._cores import get_colors
from ._preview import Preview
from ._registro import ChildNode, MFNode, SFNode, registrar


class X3D:
    """
    Classe responsável por fazer o Parse do arquivo X3D.

    ...

    Atributos
    ----------
    root : Element
        raiz do grafo de cena X3D em XMl

    renderer : dict (static)
        dicionário dos métodos de renderização (o mesmo de `Contexto.renderer`)

    Métodos
    -------
    parse():
        Realiza o parse e já realiza as rotinas de renderização.
    """

    # dicionario dos métodos de renderização (o mesmo dict de Contexto.renderer)
    renderer: ClassVar[dict[str, Renderer]] = contexto.renderer

    def __init__(self, filename: str) -> None:
        """
        Constroi o atributo para a raiz do grafo X3D.
        """
        self.root = ET.parse(filename).getroot()
        self.scene: Scene | None = None  # Referência para o objeto da cena
        self.width = 0
        self.height = 0

    def set_preview(self, preview: Preview) -> None:
        """
        Armazena as rotinas para fazer o render da cena.
        """
        contexto.preview = preview

    def viewport(self, width: int, height: int) -> None:
        """
        Armazena a largura e altura de janela de renderização.
        """
        self.width = width
        self.height = height

    def parse(self) -> None:
        """
        Leitura da cena começando da raiz do X3D.
        """
        for child in self.root:
            clean(child) # remove namespace
            if child.tag == "Scene":
                self.scene = Scene(child)

    def render(self) -> None:
        """
        Renderização da cena começando da raiz do X3D.
        """
        assert self.scene is not None
        self.scene.render()


class Scene:
    """
    O nó Scene acomoda a cena X3D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        self.children: list[object] = []
        self.nodes_eventos: list[object] = []  # TimeSensors e interpoladores
        self.routes: list[ROUTE] = []
        lights: list[DirectionalLight | PointLight] = []
        viewpoint: Viewpoint | None = None
        navigation_info: NavigationInfo | None = None
        fog: Fog | None = None

        for child in node:
            clean(child)  # remove namespace
            if child.tag == "Transform":
                self.children.append(Transform(child))
            elif child.tag == "Shape":
                self.children.append(Shape(child))
            elif child.tag == "TimeSensor":
                self.nodes_eventos.append(TimeSensor(child))
            elif child.tag == "SplinePositionInterpolator":
                self.nodes_eventos.append(SplinePositionInterpolator(child))
            elif child.tag == "OrientationInterpolator":
                self.nodes_eventos.append(OrientationInterpolator(child))
            elif child.tag == "ROUTE":
                self.routes.append(ROUTE(child))
            elif child.tag == "DirectionalLight":
                lights.append(DirectionalLight(child))
            elif child.tag == "PointLight":
                lights.append(PointLight(child))
            elif child.tag == "Viewpoint":
                viewpoint = Viewpoint(child)
            elif child.tag == "NavigationInfo":
                navigation_info = NavigationInfo(child)
            elif child.tag == "Fog":
                fog = Fog(child)

        self.children = list(lights) + self.children  # deixa luzes primeiro

        if navigation_info:  # garante tratar o Viewpoint antes dos outros nós
            self.children.insert(0, navigation_info)
        else:  # cria um navigation_info se não definido
            self.children.insert(0, NavigationInfo())

        if viewpoint:  # garante tratar o Viewpoint primeiro que tudo
            self.children.insert(0, viewpoint)
        else:  # cria um viewpoint se não definido
            self.children.insert(0, Viewpoint())

        if fog:  # garante que fog seja o último nó
            self.children.append(fog)

    def _resolve_events(self, nome: str, feitos: set[str]) -> None:
        """
        Atualiza um nó nomeado depois dos eventos que chegam nele.

        Antes de atualizar o nó, resolve recursivamente a origem de cada ROUTE
        que chega nele e propaga o valor. Assim a cadeia relógio, interpolador
        e Transform sai correta no mesmo frame, em qualquer ordem no arquivo.
        Cada nó é resolvido uma única vez por frame, o que também impede
        laços entre ROUTEs.

        Parameters
        ----------
        nome : str
            Nome (DEF) do nó a atualizar.
        feitos : set[str]
            Nomes já resolvidos neste frame.
        """
        if nome in feitos:
            return
        feitos.add(nome)

        for rota in self.routes:
            if rota.toNode == nome:
                self._resolve_events(rota.fromNode, feitos)
                rota.render()

        no = X3DNode.named_nodes.get(nome)
        if no in self.nodes_eventos:
            no.render()  # type: ignore[attr-defined]

    def render(self) -> None:
        """
        Rotina de renderização.
        """
        feitos: set[str] = set()
        for rota in self.routes:
            self._resolve_events(rota.toNode, feitos)

        for child in self.children:
            child.render()  # type: ignore[attr-defined]


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


class X3DGeometryNode(X3DNode):
    """
    Este é o tipo de nó base para todas as geometrias em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização (sobrescrita pelas subclasses concretas).
        """


class X3DComposedGeometryNode(X3DGeometryNode):
    """
    Este é o tipo de nó base para toda a geometria 3D composta em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai
        self.coord = SFNode(node, "X3DCoordinateNode", None) if node is not None else None
        self.attrib: list[object] = (
            MFNode(node, "X3DVertexAttributeNode", []) if node is not None else [])
        self.fogCoord = SFNode(node, "FogCoordinate", None) if node is not None else None
        self.normal = SFNode(node, "X3DNormalNode", None) if node is not None else None
        self.texCoord = SFNode(node, "X3DTextureCoordinateNode", None) if node is not None else None
        self.ccw = SFBool(node, "ccw", True)
        self.colorPerVertex = SFBool(node, "colorPerVertex", True)
        self.normalPerVertex = SFBool(node, "normalPerVertex", True)
        self.solid = SFBool(node, "solid", True)


class X3DGeometricPropertyNode(X3DNode):
    """
    Nó base para todos os tipos de nós de propriedades geométricas definidos no X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DCoordinateNode(X3DGeometricPropertyNode):
    """
    Nó base para todos os tipos de nós de coordenadas em X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


class X3DColorNode(X3DGeometricPropertyNode):
    """
    Nó básico para especificações de cores no X3D.
    """

    def __init__(self, node: Element | None = None) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node)  # Chama construtor da classe pai


@registrar("X3DCoordinateNode")
class Coordinate(X3DCoordinateNode):
    """
    Define um conjunto de coordenadas 3D para nós de geometria baseada em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec3f(node, "point", [])


@registrar("X3DColorNode")
class Color(X3DColorNode):
    """
    Define um conjunto de cores RGB a serem usadas nos campos de outro nó.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.color = MFColor(node, "color", [])


@registrar("X3DGeometryNode")
class TriangleSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D que representa uma coleção de triângulos individuais.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.vertices = MFVec2f(node, "vertices", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleSet" not in contexto.renderer:
            raise Exception("TriangleSet não foi implementado.")

        colors = get_colors(appearance)
        if self.coord and self.coord.point:
            # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
            contexto.renderer["TriangleSet"](point=self.coord.point, colors=colors)


@registrar("X3DGeometryNode")
class TriangleStripSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D composta por faixas de triângulos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.stripCount = MFInt32(node, "stripCount", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleStripSet" not in contexto.renderer:
            raise Exception("TriangleStripSet não foi implementado.")

        colors = get_colors(appearance)
        if self.coord and self.coord.point and self.stripCount:
            # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
            contexto.renderer["TriangleStripSet"](point=self.coord.point,
                                             stripCount=self.stripCount,
                                             colors=colors)


@registrar("X3DGeometryNode")
class IndexedTriangleStripSet(X3DComposedGeometryNode):
    """
    Representa uma forma 3D composta de tiras de triângulos.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.index = MFInt32(node, "index", [])

        # Preview
        # Implemente se desejar

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "IndexedTriangleStripSet" not in contexto.renderer:
            raise Exception("IndexedTriangleStripSet não foi implementado.")

        colors = get_colors(appearance)
        if "IndexedTriangleStripSet" in contexto.renderer:
            if self.coord and self.coord.point and self.index:
                # NO FUTURO MANDAR O OBJETO INTEIRO COM SEUS PARAMETROS ENCAPSULADOS
                contexto.renderer["IndexedTriangleStripSet"](point=self.coord.point,
                                                        index=self.index,
                                                        colors=colors)


@registrar("X3DGeometryNode")
class Polypoint2D(X3DGeometryNode):
    """
    Pontos exibidos por um conjunto de vértices no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec2f(node, "point", [])

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.point), 2):
                points.append([self.point[i], self.point[i+1]])
            contexto.preview.pontos.append({'appearance': contexto.current_appearance,
                                       'points': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Polypoint2D" not in contexto.renderer:
            raise Exception("Polypoint2D não foi implementado.")

        colors = get_colors(appearance)
        if self.point:
            contexto.renderer["Polypoint2D"](point=self.point, colors=colors)


@registrar("X3DGeometryNode")
class Polyline2D(X3DGeometryNode):
    """
    Série de segmentos de linha contíguos no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.lineSegments = MFVec2f(node, "lineSegments", [])

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.lineSegments), 2):
                points.append([self.lineSegments[i], self.lineSegments[i+1]])
            contexto.preview.linhas.append({'appearance': contexto.current_appearance,
                                       'lines': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Polyline2D" not in contexto.renderer:
            raise Exception("Polyline2D não foi implementado.")

        colors = get_colors(appearance)
        if self.lineSegments:
            contexto.renderer["Polyline2D"](lineSegments=self.lineSegments, colors=colors)


@registrar("X3DGeometryNode")
class Circle2D(X3DGeometryNode):
    """
    Uma linha que forma um círculo no sistema de coordenadas 2D.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.radius = SFFloat(node, "radius", 1)

        # Preview
        if contexto.preview:
            radius = self.radius
            contexto.preview.circulos.append({'appearance': contexto.current_appearance,
                                         'radius': radius})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "Circle2D" not in contexto.renderer:
            raise Exception("Circle2D não foi implementado.")

        colors = get_colors(appearance)
        if self.radius:
            contexto.renderer["Circle2D"](radius=self.radius, colors=colors)


@registrar("X3DGeometryNode")
class TriangleSet2D(X3DGeometryNode):
    """
    Especifica um conjunto de triângulos no sistema de coordenadas 2D local.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.vertices = MFVec2f(node, "vertices", [])
        self.solid = SFBool(node, "solid", False)

        # Preview
        if contexto.preview:
            points: list[list[float]] = []
            for i in range(0, len(self.vertices), 2):
                points.append([self.vertices[i], self.vertices[i+1]])
            contexto.preview.poligonos.append({'appearance': contexto.current_appearance,
                                          'vertices': points})

    def render(self, appearance: "Appearance | None" = None) -> None:
        """
        Rotina de renderização.
        """
        if "TriangleSet2D" not in contexto.renderer:
            raise Exception("TriangleSet2D não foi implementado.")

        colors = get_colors(appearance)
        if self.vertices:
            contexto.renderer["TriangleSet2D"](vertices=self.vertices, colors=colors)


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


class X3DTextureCoordinateNode(X3DGeometricPropertyNode):
    """
    Nó abstrato base para todos os tipos de nó que especificam coordenadas de textura.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai


@registrar("X3DTextureCoordinateNode")
class TextureCoordinate(X3DTextureCoordinateNode):
    """
    Conjunto de coordenadas de textura 2D usadas por nós de geometria baseados em vértices.
    """

    def __init__(self, node: Element) -> None:
        """
        Parse do nó X3D.
        """
        super().__init__(node) # Chama construtor da classe pai
        self.point = MFVec2f(node, "point", [])

    def render(self) -> None:
        """
        Rotina de renderização.
        """


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
