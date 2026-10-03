"""
Nós X3D de geometria 2D: pontos, linhas, círculo e triângulos.
"""

import math

import numpy as np
import numpy.typing as npt

from ._cores import piso, to_rgb8
from ._primitivas2d import draw_points, draw_points_blend, line_points
from ._tipos import Colors
from ._varredura import scan_triangle

# Matrizes de reflexão e rotação usadas para gerar
# os 8 octantes simétricos de um círculo a partir de um único octante calculado.
CIRCLE_OCTANT_REFLECTIONS: npt.NDArray[np.float64] = np.array([
    [[1, 0], [0, 1]], [[0, 1], [1, 0]],
    [[0, -1], [1, 0]], [[-1, 0], [0, 1]],
    [[-1, 0], [0, -1]], [[0, -1], [-1, 0]],
    [[0, 1], [-1, 0]], [[1, 0], [0, -1]],
], dtype=np.float64)


def polypoint2D(point: list[float], colors: Colors) -> None:
    """
    Renderiza Polypoint2D: uma lista de pontos 2D isolados.

    Parameters
    ----------
    point : list[float]
        Coordenadas dos pontos no formato [x0, y0, x1, y1, ...], em
        coordenadas de tela.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor dos pontos.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); o resultado
        retorno.
    """
    cor = to_rgb8(colors["emissiveColor"])
    pontos = piso(np.asarray(point).reshape(-1, 2)).astype(np.int64)

    draw_points(pontos[:, 0], pontos[:, 1], cor)


def polyline2D(lineSegments: list[float], colors: Colors) -> None:
    """
    Renderiza Polyline2D: uma sequência de segmentos de reta conectados.

    Parameters
    ----------
    lineSegments : list[float]
        Coordenadas dos vértices da polilinha no formato
        [x0, y0, x1, y1, ...], em coordenadas de tela. Cada par
        consecutivo de vértices forma um segmento.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor das linhas.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    cor = to_rgb8(colors["emissiveColor"])
    pontos = np.asarray(lineSegments, dtype=np.float64).reshape(-1, 2)

    for (x0, y0), (x1, y1) in zip(pontos[:-1].tolist(), pontos[1:].tolist()):
        xs, ys, cobertura = line_points(x0, y0, x1, y1)
        draw_points_blend(xs, ys, cor, cobertura)


def circle2D(radius: float, colors: Colors) -> None:
    """
    Renderiza Circle2D: o contorno de um círculo centrado na origem local.

    Parameters
    ----------
    radius : float
        Raio do círculo, em unidades de tela.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor do contorno.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    cor = to_rgb8(colors["emissiveColor"])
    r = round(radius)

    # Sem For: Calcula octante aplica as matrizes identidade e
    # gera o circulo completo 

    # Calcula um único octante (0 <= x <= y)
    xs_octant = np.arange(0, int(r / math.sqrt(2)) + 1, dtype=np.float64)
    ys_octant = piso(np.sqrt(r ** 2 - xs_octant ** 2))

    octant = np.stack([xs_octant, ys_octant], axis=1)  # (N, 2)

    # Aplica as 8 matrizes de reflexão para gerar todos os octantes do círculo
    all_points = np.concatenate([octant @ m.T for m in CIRCLE_OCTANT_REFLECTIONS])

    draw_points(all_points[:, 0].astype(np.int64), all_points[:, 1].astype(np.int64), cor)


def triangleSet2D(vertices: list[float], colors: Colors) -> None:
    """
    Renderiza TriangleSet2D: uma lista de triângulos 2D independentes.

    Parameters
    ----------
    vertices : list[float]
        Coordenadas dos vértices no formato [x0, y0, x1, y1, x2, y2, ...],
        em coordenadas de tela. Cada grupo de 3 vértices (6 floats) forma
        um triângulo independente.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor de preenchimento (flat shading).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    cor = to_rgb8(colors["emissiveColor"])

    for i in range(0, len(vertices) - 5, 6):

        scan_triangle(vertices[i], vertices[i + 1],
                          vertices[i + 2], vertices[i + 3],
                          vertices[i + 4], vertices[i + 5], cor)
