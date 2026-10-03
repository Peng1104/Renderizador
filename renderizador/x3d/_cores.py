"""
Cores resolvidas de um Appearance/Material.
"""

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ._nucleo import Appearance

class Colors(TypedDict):
    """
    Conjunto de cores resolvidas a partir de um nó Appearance/Material.
    """

    diffuseColor: list[float]
    emissiveColor: list[float]
    specularColor: list[float]
    shininess: float
    transparency: float
    ambientIntensity: float


def get_colors(appearance: "Appearance | None") -> Colors:
    """
    Método de apoio para recuperar cores de um nó Appearance.
    """
    colors: Colors = {
        "diffuseColor": [0.8, 0.8, 0.8],  # Valor padrão
        "emissiveColor": [0.0, 0.0, 0.0],  # Valor padrão
        "specularColor": [0.0, 0.0, 0.0],  # Valor padrão
        "shininess": 0.2,  # Valor padrão
        "transparency": 0.0,  # Valor padrão
        "ambientIntensity": 0.2,  # Valor padrão
    }
    if appearance and appearance.material:
        colors["diffuseColor"] = appearance.material.diffuseColor
        colors["emissiveColor"] = appearance.material.emissiveColor
        colors["specularColor"] = appearance.material.specularColor
        colors["shininess"] = appearance.material.shininess
        colors["transparency"] = appearance.material.transparency
        colors["ambientIntensity"] = appearance.material.ambientIntensity

    return colors
