"""
Projeção de pontos para a tela, back-face culling e espaço de mundo.
"""

import numpy as np
import numpy.typing as npt

from ._estado import estado


def project_points(point: list[float]
                    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64],
                               npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Projeta uma lista de pontos 3D (objeto) para coordenadas de tela.

    Aplica a matriz completa objeto -> mundo -> câmera -> clip (usando o
    topo da pilha de transformações corrente), Em seguida, divide por W
    (divisão de perspectiva) para obter as coordenadas normalizadas
    (NDC em [-1, 1]) e, por fim, converte esse espaço normalizado para
    pixels na tela (viewport).

    Parameters
    ----------
    point : list[float]
        Coordenadas dos pontos no formato [x0, y0, z0, x1, y1, z1, ...],
        em coordenadas de objeto (espaço local).

    Returns
    -------
    NDArray[float64]
        Coordenadas x de cada ponto, em coordenadas de tela.
    NDArray[float64]
        Coordenadas y de cada ponto, em coordenadas de tela, mesmo
        tamanho do primeiro retorno.
    NDArray[float64]
        Componente w do espaço de clip de cada ponto (proporcional à
        profundidade do ponto na câmera), mesmo tamanho dos dois
        retornos anteriores. Usado para interpolação de atributos
        (cor, textura) corrigida pela perspectiva, já que a
        interpolação linear direta em coordenadas de tela distorce
        qualquer atributo por vértice quando os vértices de um mesmo
        triângulo têm profundidades bem diferentes.
    NDArray[float64]
        Componente z de NDC de cada ponto, em [-1, 1] (near=-1, far=1),
        mesmo tamanho dos retornos anteriores. Usado como profundidade
        no teste de z-buffer (ver `triangle_coverage`): ao contrário
        de cor/textura, o z de NDC já é afim nas coordenadas de tela
        (propriedade da projeção perspectiva usada aqui), então pode ser
        interpolado com os pesos baricêntricos brutos, sem correção de
        perspectiva.
    """
    # Matriz completa: objeto -> mundo -> câmera -> clip.
    transformacao = estado.perspective_matrix @ estado.view_matrix @ estado.transform_stack[-1]

    pontos = np.asarray(point, dtype=np.float64).reshape(-1, 3)
    homogeneos = np.hstack([pontos, np.ones((pontos.shape[0], 1))])

    clip = (transformacao @ homogeneos.T).T
    # Divisão de perspectiva: normaliza pelo componente w.
    ndc = clip[:, :3] / clip[:, 3:4]

    # Mapeia de NDC ([-1, 1]) para coordenadas de tela (eixo y invertido).
    tela_x = (ndc[:, 0] + 1) / 2 * estado.width
    tela_y = (1 - ndc[:, 1]) / 2 * estado.height

    return tela_x, tela_y, clip[:, 3], ndc[:, 2]


def front_facing_mask(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
                       i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                       i2: npt.NDArray[np.int64]) -> npt.NDArray[np.bool_]:
    """
    Calcula, para vários triângulos de uma vez, quais estão de frente para a câmera.

    Todo triângulo 3D deste projeto segue a convenção anti-horária (CCW), em coordenadas
    coordenadas de câmera/NDC o y é para cima). Um triângulo de costas (ou degenerado,
    área ~0) é descartado antes da varedura, evitando o custo de _scan_triangle para
    metade das faces de qualquer malha fechada.

    Parameters
    ----------
    tela_x : NDArray[float64]
        Coordenadas x de todos os vértices envolvidos, em coordenadas de
        tela (tipicamente o retorno de project_points).
    tela_y : NDArray[float64]
        Coordenadas y de todos os vértices envolvidos, em coordenadas de
        tela, mesmo tamanho de `tela_x`.
    i0 : NDArray[int64]
        Índices do primeiro vértice de cada triângulo, em `tela_x`/`tela_y`.
    i1 : NDArray[int64]
        Índices do segundo vértice de cada triângulo, mesmo tamanho de `i0`.
    i2 : NDArray[int64]
        Índices do terceiro vértice de cada triângulo, mesmo tamanho de `i0`.

    Returns
    -------
    NDArray[bool_]
        Máscara booleana, mesmo tamanho de `i0`: True onde o triângulo
        está de frente para a câmera (deve ser rasterizado).
    """
    x0, y0 = tela_x[i0], tela_y[i0]
    x1, y1 = tela_x[i1], tela_y[i1]
    x2, y2 = tela_x[i2], tela_y[i2]

    area_assinada = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
    return area_assinada < 0


def to_world(posicoes: npt.NDArray[np.float64], normais: npt.NDArray[np.float64] | None
              ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64] | None]:
    """
    Leva posições e normais de coordenadas de objeto para coordenadas de mundo.

    As posições usam a matriz de modelo corrente (topo da pilha). As
    normais usam a inversa transposta dela, para que escalas não
    uniformes não as deformem, e são renormalizadas.

    Parameters
    ----------
    posicoes : NDArray[float64]
        Posições (N, 3) em coordenadas de objeto.
    normais : NDArray[float64] or None
        Normais (N, 3) em coordenadas de objeto, ou None se só as
        posições interessam.

    Returns
    -------
    NDArray[float64]
        Posições (N, 3) em coordenadas de mundo.
    NDArray[float64] or None
        Normais unitárias (N, 3) em coordenadas de mundo, ou None.
    """
    modelo = estado.transform_stack[-1]
    mundo = posicoes @ modelo[:3, :3].T + modelo[:3, 3]
    if normais is None:
        return mundo, None
    n = normais @ np.linalg.inv(modelo)[:3, :3]
    comprimento = np.linalg.norm(n, axis=1, keepdims=True)
    return mundo, n / np.where(comprimento == 0, 1.0, comprimento)
