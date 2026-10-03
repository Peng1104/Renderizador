"""
Rasterização em lote de todos os triângulos opacos de um draw call, com iluminação Phong.
"""

import numpy as np
import numpy.typing as npt

from ._arestas import batch_edges_and_bbox
from ._constantes import MSAA_AMOSTRAS
from ._cores import piso
from ._estado import estado
from ._iluminacao import shade
from ._tipos import Colors

# Máximo de subamostras candidatas processadas por vez, para limitar a memória quando os
# triângulos do draw call são grandes. Os grupos de triângulos são resolvidos em sequência.
MAX_CANDIDATAS = 1_500_000


def _candidatas(contagens: npt.NDArray[np.int64], tris: npt.NDArray[np.int64],
                min_x: npt.NDArray[np.int64], min_y: npt.NDArray[np.int64],
                colunas: npt.NDArray[np.int64]
                ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], npt.NDArray[np.int64],
                           npt.NDArray[np.int64], npt.NDArray[np.int64],
                           npt.NDArray[np.float64]]:
    """
    Gera todas as subamostras da bounding box de cada triângulo de um grupo.

    A ordem é a mesma de uma varredura triângulo a triângulo: dentro de cada
    triângulo, linha por linha de subamostras.

    Parameters
    ----------
    contagens : NDArray[int64]
        Quantidade de subamostras da bounding box de cada triângulo do grupo.
    tris : NDArray[int64]
        Índice de cada triângulo do grupo.
    min_x, min_y : NDArray[int64]
        Canto da bounding box de cada triângulo (todos), em pixels.
    colunas : NDArray[int64]
        Quantidade de colunas de subamostras da bounding box de cada triângulo (todos).

    Returns
    -------
    NDArray[int64]
        Triângulo de cada subamostra candidata.
    NDArray[int64]
        Linha de pixel (y) de cada subamostra.
    NDArray[int64]
        Coluna de pixel (x) de cada subamostra.
    NDArray[int64]
        Subamostra dentro do pixel, em y.
    NDArray[int64]
        Subamostra dentro do pixel, em x.
    NDArray[float64]
        Coordenadas (x, y) de tela de cada subamostra, array (2, K).
    """
    m = MSAA_AMOSTRAS
    desloc = (np.arange(m) + 0.5) / m
    dono = np.repeat(np.arange(len(tris)), contagens)
    inicio = np.cumsum(contagens) - contagens
    k = np.arange(int(contagens.sum())) - inicio[dono]
    ncol = colunas[tris][dono]
    linha, coluna = k // ncol, k % ncol

    ys = min_y[tris][dono] + linha // m
    xs = min_x[tris][dono] + coluna // m
    sy, sx = linha % m, coluna % m
    x = xs + desloc[sx]
    y = ys + desloc[sy]
    return tris[dono], ys, xs, sy, sx, np.stack([x, y])


def _interpolar(pesos: npt.NDArray[np.float64], atributo: npt.NDArray[np.float64],
                tri: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
    """
    Interpola um atributo dos três vértices de cada triângulo com os pesos de cada subamostra.

    Parameters
    ----------
    pesos : NDArray[float64]
        Pesos baricêntricos perspectiva-corretos, array (3, K).
    atributo : NDArray[float64]
        Valor do atributo nos três vértices de cada triângulo, array (T, 3, 3).
    tri : NDArray[int64]
        Triângulo de cada uma das K subamostras.

    Returns
    -------
    NDArray[float64]
        Atributo interpolado, array (K, 3).
    """
    return (pesos[0][:, None] * atributo[tri, 0] + pesos[1][:, None] * atributo[tri, 1]
            + pesos[2][:, None] * atributo[tri, 2])


def _resolver_grupo(vertices: npt.NDArray[np.float64],
                    indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                   npt.NDArray[np.int64]],
                    arestas: npt.NDArray[np.float64], tris: npt.NDArray[np.int64],
                    contagens: npt.NDArray[np.int64], caixa: tuple[npt.NDArray[np.int64], ...],
                    atributos: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
                    colors: Colors) -> None:
    """
    Resolve cobertura, z-buffer e cor de um grupo de triângulos e escreve o resultado.

    Em cada subamostra vence o candidato de menor profundidade, e o último em
    caso de empate; é o mesmo resultado de testar os triângulos um a um com
    `profundidade <= buffer`. Só as subamostras vencedoras são sombreadas.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.
    arestas : NDArray[float64]
        Coeficientes de aresta de cada triângulo, array (T, 3, 3).
    tris : NDArray[int64]
        Triângulos do grupo.
    contagens : NDArray[int64]
        Quantidade de subamostras da bounding box de cada triângulo do grupo.
    caixa : tuple[NDArray[int64], ...]
        (min_x, min_y, colunas) de cada triângulo do grupo.
    atributos : tuple[NDArray[float64], NDArray[float64]]
        Posição e normal de mundo dos três vértices de cada triângulo, arrays (T, 3, 3).
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    """
    i0, i1, i2 = indices
    pos_tri, n_tri = atributos
    tri, ys, xs, sy, sx, pontos = _candidatas(contagens, tris, caixa[0], caixa[1], caixa[2])

    # Mesma multiplicação de matrizes por triângulo de antes, para que as bordas caiam nos
    # mesmos pixels; o que sobra do trabalho é vetorizado.
    bari = np.empty((3, tri.size))
    inicio = np.cumsum(contagens) - contagens
    pontos3 = np.vstack([pontos, np.ones(tri.size)])
    for t, a, n in zip(tris.tolist(), inicio.tolist(), contagens.tolist()):
        bari[:, a:a + n] = arestas[t] @ np.ascontiguousarray(pontos3[:, a:a + n])

    dentro = np.nonzero(np.all(bari >= 0, axis=0) | np.all(bari <= 0, axis=0))[0]
    if dentro.size == 0:
        return
    tri, ys, xs, sy, sx = tri[dentro], ys[dentro], xs[dentro], sy[dentro], sx[dentro]
    sel = bari[:, dentro]
    total = sel.sum(axis=0)
    pesos = np.stack([sel[1] / total, sel[2] / total, sel[0] / total])

    prof = (pesos[0] * vertices[i0[tri], 3] + pesos[1] * vertices[i1[tri], 3]
            + pesos[2] * vertices[i2[tri], 3])
    aprovado = prof <= estado.depth_buffer[ys, xs, sy, sx]
    if not np.any(aprovado):
        return
    tri, ys, xs, sy, sx = tri[aprovado], ys[aprovado], xs[aprovado], sy[aprovado], sx[aprovado]
    pesos, prof = pesos[:, aprovado], prof[aprovado]

    m = MSAA_AMOSTRAS
    sid = ((ys * estado.width + xs) * m + sy) * m + sx
    ordem = np.lexsort((-np.arange(sid.size), prof, sid))
    primeiro = np.concatenate(([True], sid[ordem][1:] != sid[ordem][:-1]))
    venc = ordem[primeiro]
    tri, ys, xs, sy, sx = tri[venc], ys[venc], xs[venc], sy[venc], sx[venc]
    pesos, prof = pesos[:, venc], prof[venc]
    estado.depth_buffer[ys, xs, sy, sx] = prof

    w = np.stack([vertices[i0[tri], 2], vertices[i1[tri], 2], vertices[i2[tri], 2]])
    pesos = pesos / w
    pesos /= pesos.sum(axis=0)

    pos = _interpolar(pesos, pos_tri, tri)
    normal = _interpolar(pesos, n_tri, tri)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    cor = shade(pos, normal, colors)
    estado.ms_buffer[ys, xs, sy, sx] = np.clip(piso(cor * 255), 0, 255).astype(np.uint8)


def fill_lit_batch(vertices: npt.NDArray[np.float64],
                   indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                  npt.NDArray[np.int64]],
                   pos_tri: npt.NDArray[np.float64], n_tri: npt.NDArray[np.float64],
                   colors: Colors) -> None:
    """
    Preenche com iluminação Phong todos os triângulos opacos de um draw call, em lote.

    O resultado é o mesmo de varrer os triângulos um a um com
    `scan_triangle_lit`, mas as contas de cobertura, z-buffer e iluminação
    são feitas sobre todas as subamostras de uma vez, e só as vencedoras de
    cada pixel são sombreadas. Vale só para geometria opaca: com
    transparência, a ordem de mistura entre triângulos importa e o chamador
    deve usar a varredura triângulo a triângulo.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo (já sem os de costas).
    pos_tri : NDArray[float64]
        Posição de mundo dos três vértices de cada triângulo, array (T, 3, 3).
    n_tri : NDArray[float64]
        Normal unitária de mundo dos três vértices de cada triângulo, array (T, 3, 3).
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.

    Returns
    -------
    None
        Escreve em estado.ms_buffer e estado.depth_buffer; não há retorno.
    """
    i0, i1, i2 = indices
    arestas, min_x, max_x, min_y, max_y = batch_edges_and_bbox(vertices[:, 0], vertices[:, 1],
                                                               i0, i1, i2)
    colunas = (max_x - min_x + 1) * MSAA_AMOSTRAS
    linhas = (max_y - min_y + 1) * MSAA_AMOSTRAS
    valido = (min_x <= max_x) & (min_y <= max_y)
    contagem = np.where(valido, colunas * linhas, 0)

    ids = np.nonzero(valido)[0]
    acumulado = np.cumsum(contagem[ids])
    inicio = 0
    while inicio < ids.size:
        base = acumulado[inicio - 1] if inicio else 0
        fim = max(int(np.searchsorted(acumulado, base + MAX_CANDIDATAS, side="right")),
                  inicio + 1)
        grupo = ids[inicio:fim]
        _resolver_grupo(vertices, indices, arestas, grupo, contagem[grupo],
                        (min_x, min_y, colunas), (pos_tri, n_tri), colors)
        inicio = fim
