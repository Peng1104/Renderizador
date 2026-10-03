"""
Contexto compartilhado do parse e da renderização (cores, textura, preview, renderer).
"""

from typing import TYPE_CHECKING, Callable

from ._cores import Colors
from ._preview import Preview

if TYPE_CHECKING:
    from ._aparencia import Appearance

Renderer = Callable[..., object]


class Contexto:
    """
    Contexto compartilhado durante o parse e a renderização da cena.

    Atributos
    ----------
    current_color : Colors
        cores usadas no momento (diffuseColor, emissiveColor, ...) e transparência
    current_appearance : Appearance or None
        objeto de aparência em X3D
    current_texture : list[str]
        URL das texturas
    preview : Preview or None
        sistema de preview para geometrias 2D simples
    renderer : dict
        dicionário dos métodos de renderização
    """

    current_color: Colors = {  # controle de cor instantânea
        "diffuseColor": [0.8, 0.8, 0.8],
        "emissiveColor": [0.0, 0.0, 0.0],
        "specularColor": [0.0, 0.0, 0.0],
        "shininess": 0.2,
        "transparency": 0.0,
        "ambientIntensity": 0.2,
    }
    current_appearance: "Appearance | None" = None  # objeto de aparencia atual
    current_texture: list[str] = []  # controle de texturas instantâneas
    preview: Preview | None = None  # atributo que aponta para o sistema de preview
    renderer: dict[str, Renderer] = {}  # dicionario dos métodos de renderização


contexto = Contexto()
