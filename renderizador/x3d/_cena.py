"""
Parser X3D: o arquivo (X3D) e a cena (Scene).

Desenvolvido por: Luciano Soares <lpsoares@insper.edu.br>
Disciplina: Computação Gráfica
Data: 31 de Agosto de 2020
"""

import xml.etree.ElementTree as ET
from typing import ClassVar

from ._agrupamento import Transform
from ._ambiente import Fog
from ._aparencia import Shape
from ._base import X3DNode
from ._campos import Element, clean
from ._contexto import Renderer, contexto
from ._iluminacao import DirectionalLight, PointLight
from ._interpoladores import OrientationInterpolator, SplinePositionInterpolator
from ._navegacao import NavigationInfo, Viewpoint
from ._preview import Preview
from ._rota import ROUTE
from ._tempo import TimeSensor


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
