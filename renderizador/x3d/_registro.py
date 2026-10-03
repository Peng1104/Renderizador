"""
Registro de classes de nó por tag e as fábricas SFNode e MFNode.
"""

from typing import TYPE_CHECKING, Callable, Literal, TypeVar, cast, overload

from ._campos import Element, clean

if TYPE_CHECKING:
    from ._agrupamento import Transform
    from ._aparencia import Appearance, ImageTexture, Material, Shape
    from ._nucleo import (
        Box,
        Circle2D,
        Cone,
        Cylinder,
        IndexedFaceSet,
        IndexedTriangleStripSet,
        Polyline2D,
        Polypoint2D,
        Sphere,
        TriangleSet,
        TriangleSet2D,
        TriangleStripSet,
    )
    from ._propriedades import Color, Coordinate, TextureCoordinate

Fabrica = Callable[[Element], object]


_REGISTRO: dict[str, dict[str, Fabrica]] = {}


ClasseT = TypeVar("ClasseT", bound=type)


def registrar(categoria: str) -> Callable[[ClasseT], ClasseT]:
    """
    Registra uma classe de nó, pelo nome, numa categoria de campo (ex: X3DGeometryNode).

    Parameters
    ----------
    categoria : str
        Categoria de campo em que a classe pode aparecer (a que SFNode e MFNode recebem).

    Returns
    -------
    Callable[[ClasseT], ClasseT]
        Decorador que registra a classe e a devolve sem alterá-la.
    """
    def decorador(classe: ClasseT) -> ClasseT:
        _REGISTRO.setdefault(categoria, {})[classe.__name__] = classe
        return classe
    return decorador


type ChildNode = Shape | Transform


NodeT = TypeVar("NodeT")


@overload
def MFNode(node: Element, name: Literal["X3DChildNode"],
           default: list[ChildNode]) -> list[ChildNode]: ...


@overload
def MFNode(node: Element, name: str, default: list[NodeT]) -> list[NodeT]: ...


def MFNode(node: Element, name: str,
          default: list[ChildNode] | list[NodeT]) -> list[ChildNode] | list[NodeT]:
    """
    Especifica zero ou mais nós X3D.
    """
    fabricas = _REGISTRO.get(name)
    filhos: list[object] = []
    for child in node:
        clean(child) # remove namespace
        if fabricas is not None and child.tag in fabricas:
            filhos.append(fabricas[child.tag](child))

    return cast("list[ChildNode]", filhos) if fabricas is not None else default


DefaultT = TypeVar("DefaultT")


type GeometryNode = (
    Polypoint2D | Polyline2D | Circle2D | TriangleSet2D | TriangleSet |
    TriangleStripSet | IndexedTriangleStripSet | Box | Sphere | Cone |
    Cylinder | IndexedFaceSet
)


@overload
def SFNode(node: Element, name: Literal["X3DAppearanceNode"],
           default: DefaultT) -> "Appearance | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DGeometryNode"],
           default: DefaultT) -> "GeometryNode | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DMaterialNode"],
           default: DefaultT) -> "Material | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DTextureNode"],
           default: DefaultT) -> "ImageTexture | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DCoordinateNode"],
           default: DefaultT) -> "Coordinate | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DColorNode"],
           default: DefaultT) -> "Color | DefaultT": ...


@overload
def SFNode(node: Element, name: Literal["X3DTextureCoordinateNode"],
           default: DefaultT) -> "TextureCoordinate | DefaultT": ...


@overload
def SFNode(node: Element, name: str, default: DefaultT) -> DefaultT: ...


def SFNode(node: Element, name: str, default: object) -> object:
    """
    Especifica um nó X3D.
    """
    fabricas = _REGISTRO.get(name, {})
    for child in node:
        clean(child) # remove namespace
        fabrica = fabricas.get(child.tag)
        if fabrica is not None:
            return fabrica(child)

    return default
