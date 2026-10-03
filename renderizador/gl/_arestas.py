"""
Coeficientes de aresta e bounding box dos triângulos.
"""

import numpy as np
import numpy.typing as npt

from ._constantes import LOTE_MINIMO
from ._estado import estado


def batch_edges_and_bbox(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
                          i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                          i2: npt.NDArray[np.int64]
                          ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64],
                                     npt.NDArray[np.int64], npt.NDArray[np.int64],
                                     npt.NDArray[np.int64]]:
    """
    Pré-calcula os coeficientes de aresta e a bounding box de todos os T triângulos de uma vez.

    `triangle_coverage` precisa dos coeficientes de aresta e da
    bounding box de cada triângulo antes de rasterizá-lo, mas essas
    duas quantidades dependem só das coordenadas $(x, y)$ de tela dos
    3 vértices, o mesmo cálculo repetido triângulo a triângulo dentro
    do laço Python de varredura de uma malha. Calculá-las aqui, para
    todos os T triângulos de uma vez via operações vetorizadas de
    array, evita essa repetição: o laço por triângulo passa a só
    indexar o resultado já pronto (ver documento de rasterização por
    função de aresta para a derivação das fórmulas).

    Parameters
    ----------
    tela_x, tela_y : NDArray[float64]
        Coordenadas de tela de todos os vértices envolvidos, mesmo
        tamanho (tipicamente o retorno de `project_points`).
    i0, i1, i2 : NDArray[int64]
        Índices do primeiro, segundo e terceiro vértice de cada
        triângulo, em `tela_x`/`tela_y`, mesmo tamanho T entre si.

    Returns
    -------
    NDArray[float64]
        `arestas`: coeficientes (dy, -dx, ay*dx - ax*dy) das 3 arestas
        de cada triângulo, array (T, 3, 3), na mesma ordem usada por
        `triangle_coverage` (edge0 = v0->v1, edge1 = v1->v2,
        edge2 = v2->v0).
    NDArray[int64]
        `min_x` de cada triângulo, já recortado a [0, largura - 1],
        array (T,).
    NDArray[int64]
        `max_x` de cada triângulo, já recortado a [0, largura - 1].
    NDArray[int64]
        `min_y` de cada triângulo, já recortado a [0, altura - 1].
    NDArray[int64]
        `max_y` de cada triângulo, já recortado a [0, altura - 1].
    """
    x0, y0 = tela_x[i0], tela_y[i0]
    x1, y1 = tela_x[i1], tela_y[i1]
    x2, y2 = tela_x[i2], tela_y[i2]

    ax = np.stack([x0, x1, x2], axis=1)  # (T, 3)
    ay = np.stack([y0, y1, y2], axis=1)
    bx = np.roll(ax, -1, axis=1)
    by = np.roll(ay, -1, axis=1)
    dx = bx - ax
    dy = by - ay

    arestas = np.stack([dy, -dx, ay * dx - ax * dy], axis=2)  # (T, 3, 3)

    min_x = np.maximum(0, np.floor(np.minimum(np.minimum(x0, x1), x2))).astype(np.int64)
    max_x = np.minimum(estado.width - 1,
                       np.ceil(np.maximum(np.maximum(x0, x1), x2))).astype(np.int64)
    min_y = np.maximum(0, np.floor(np.minimum(np.minimum(y0, y1), y2))).astype(np.int64)
    max_y = np.minimum(estado.height - 1,
                       np.ceil(np.maximum(np.maximum(y0, y1), y2))).astype(np.int64)

    return arestas, min_x, max_x, min_y, max_y


def prepare_edges_and_bbox(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
                            i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                            i2: npt.NDArray[np.int64]
                            ) -> tuple[list[npt.NDArray[np.float64] | None],
                                       list[tuple[int, int, int, int] | None]]:
    """
    Decide se compensa pré-calcular arestas/bbox em lote para um draw call.

    `batch_edges_and_bbox` tem um custo fixo por chamada (montar os
    arrays `(T, 3)`/`(T, 3, 3)`, fazer os `roll`, converter os arrays de
    bbox para listas Python) que só compensa quando amortizado sobre
    vários triângulos: para um draw call com poucos triângulos (ex: um
    `TriangleSet` de um triângulo só, comum em cenas com muitos objetos
    pequenos separados), esse custo fixo é maior que simplesmente deixar
    `triangle_coverage` calcular a aresta/bbox daquele único
    triângulo inline, como fazia antes da vetorização em lote existir.
    Por isso, abaixo de `LOTE_MINIMO` triângulos, devolve listas de
    `None`: `triangle_coverage` recebe `None` em `arestas`/`bbox` e
    calcula os dois na hora, por triângulo, sem o overhead da
    vetorização em lote.

    Parameters
    ----------
    tela_x, tela_y : NDArray[float64]
        Coordenadas de tela de todos os vértices envolvidos, mesmo
        tamanho (tipicamente o retorno de `project_points`).
    i0, i1, i2 : NDArray[int64]
        Índices do primeiro, segundo e terceiro vértice de cada
        triângulo, em `tela_x`/`tela_y`, mesmo tamanho T entre si.

    Returns
    -------
    list[NDArray[float64] | None]
        `arestas_l`: um item por triângulo (mesma ordem de
        `i0`/`i1`/`i2`); cada item é o array (3, 3) de coeficientes de
        aresta daquele triângulo, ou `None` se o lote foi pequeno
        demais para compensar o pré-cálculo em lote.
    list[tuple[int, int, int, int] | None]
        `bboxes`: um item por triângulo, cada um a bounding box
        `(min_x, max_x, min_y, max_y)` daquele triângulo, ou `None`
        pelo mesmo motivo de `arestas_l` (sempre `None` junto com o
        `arestas_l` correspondente, nunca só um dos dois).
    """
    t = int(i0.size)

    if t < LOTE_MINIMO:
        return [None] * t, [None] * t

    arestas_t, min_x, max_x, min_y, max_y = batch_edges_and_bbox(tela_x, tela_y, i0, i1, i2)
    arestas_l: list[npt.NDArray[np.float64] | None] = list(arestas_t)
    bboxes: list[tuple[int, int, int, int] | None] = list(
        zip(min_x.tolist(), max_x.tolist(), min_y.tolist(), max_y.tolist()))

    return arestas_l, bboxes
