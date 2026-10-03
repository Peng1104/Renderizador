"""
Tipos compartilhados pelos módulos do pacote gl: cores, luzes, malhas e vértices projetados.
"""

from typing import TypedDict

import numpy as np
import numpy.typing as npt

# Um vértice de triângulo já projetado em coordenadas de tela: (x, y, w, z),
# onde w é o componente w do espaço de clip e z o componente z de NDC
# (ambos devolvidos por project_points). Agrupar os 4 valores por
# vértice numa tupla, em vez de 4 parâmetros soltos por vértice, mantém as
# funções de varredura de triângulo dentro do limite de parâmetros por
# método.
VerticeProjetado = tuple[float, float, float, float]


# Malha de triângulos indexada, em coordenadas de objeto: (posições (N, 3),
# normais por vértice (N, 3), triângulos (T, 3) com índices de vértice em
# ordem anti-horária vista de fora, coordenadas de textura UV por vértice
# (N, 2)). É o que as primitivas (Box, Sphere, Cone, Cylinder) geram e
# draw_mesh consome.
Malha = tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.int64],
              npt.NDArray[np.float64]]


# Textura de uma malha: (cadeia de mipmaps, coordenadas UV (N, 2), uma por vértice).
Textura = tuple[list[npt.NDArray[np.uint8]], npt.NDArray[np.float64]]


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


class Luz(TypedDict):
    """
    Fonte de luz direcional ativa no frame, já em coordenadas de mundo.
    """

    direcao: npt.NDArray[np.float64]  # unitário, sentido em que a luz viaja
    cor: npt.NDArray[np.float64]
    intensidade: float
    ambiente: float


class Pointo2D:
    """
    Classe que representa um ponto 2D.
    """

    x: int
    y: int
