"""
Rasterização em lote de todos os triângulos opacos de um draw call.

A cobertura e o z-buffer são resolvidos para o draw call inteiro de uma vez, e uma
"fonte de cor" (flat, cor por vértice, textura ou Phong) pinta só as subamostras vencedoras.
"""

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass

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

# O lote só compensa com muitos triângulos de poucas subamostras cada: ele evita o custo fixo
# por triângulo, mas ordena todas as subamostras candidatas do draw call. Medido nos exemplos,
# abaixo destes limites ele ganha (coelho, esferas, teapot), e acima perde para a varredura
# triângulo a triângulo (senoides, mineiro, cone e cilindro grandes).
MIN_TRIANGULOS = 8
MAX_CANDIDATAS_POR_TRIANGULO = 200


@dataclass(frozen=True)
class Vencedoras:
    """
    Subamostras que um grupo de triângulos ganhou no z-buffer.

    Attributes
    ----------
    tri : NDArray[int64]
        Triângulo dono de cada subamostra vencedora.
    ys, xs : NDArray[int64]
        Linha e coluna de pixel em `estado.ms_buffer`.
    sy, sx : NDArray[int64]
        Subamostra dentro do pixel.
    pesos : NDArray[float64]
        Peso baricêntrico perspectiva-correto de cada vértice, array (3, K).
    """

    tri: npt.NDArray[np.int64]
    ys: npt.NDArray[np.int64]
    xs: npt.NDArray[np.int64]
    sy: npt.NDArray[np.int64]
    sx: npt.NDArray[np.int64]
    pesos: npt.NDArray[np.float64]


# Calcula a cor RGB (0-255) de cada subamostra vencedora, array (K, 3).
Fonte = Callable[[Vencedoras], npt.NDArray[np.generic]]


def _interpolar(pesos: npt.NDArray[np.float64], atributo: npt.NDArray[np.float64],
                tri: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
    """
    Interpola um atributo dos três vértices de cada triângulo com os pesos de cada subamostra.

    Parameters
    ----------
    pesos : NDArray[float64]
        Pesos baricêntricos perspectiva-corretos, array (3, K).
    atributo : NDArray[float64]
        Valor do atributo nos três vértices de cada triângulo, array (T, 3, D).
    tri : NDArray[int64]
        Triângulo de cada uma das K subamostras.

    Returns
    -------
    NDArray[float64]
        Atributo interpolado, array (K, D).
    """
    return (pesos[0][:, None] * atributo[tri, 0] + pesos[1][:, None] * atributo[tri, 1]
            + pesos[2][:, None] * atributo[tri, 2])


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


def _vencedoras_grupo(vertices: npt.NDArray[np.float64],
                      indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                     npt.NDArray[np.int64]],
                      arestas: npt.NDArray[np.float64], tris: npt.NDArray[np.int64],
                      contagens: npt.NDArray[np.int64],
                      caixa: tuple[npt.NDArray[np.int64], ...]) -> Vencedoras | None:
    """
    Resolve cobertura e z-buffer de um grupo de triângulos.

    Em cada subamostra vence o candidato de menor profundidade, e o último em
    caso de empate; é o mesmo resultado de testar os triângulos um a um com
    `profundidade <= buffer`. A profundidade das vencedoras é gravada em
    `estado.depth_buffer`.

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
        (min_x, min_y, colunas) de cada triângulo (todos).

    Returns
    -------
    Vencedoras or None
        As subamostras vencedoras, ou None se o grupo não ganhou nenhuma.
    """
    i0, i1, i2 = indices
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
        return None
    tri, ys, xs, sy, sx = tri[dentro], ys[dentro], xs[dentro], sy[dentro], sx[dentro]
    sel = bari[:, dentro]
    total = sel.sum(axis=0)
    pesos = np.stack([sel[1] / total, sel[2] / total, sel[0] / total])

    prof = (pesos[0] * vertices[i0[tri], 3] + pesos[1] * vertices[i1[tri], 3]
            + pesos[2] * vertices[i2[tri], 3])
    aprovado = prof <= estado.depth_buffer[ys, xs, sy, sx]
    if not np.any(aprovado):
        return None
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
    return Vencedoras(tri, ys, xs, sy, sx, pesos)


def _preparar(vertices: npt.NDArray[np.float64],
              indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                             npt.NDArray[np.int64]]
              ) -> tuple[npt.NDArray[np.float64], tuple[npt.NDArray[np.int64], ...],
                         npt.NDArray[np.int64]]:
    """
    Calcula arestas, bounding boxes e a quantidade de subamostras candidatas de cada triângulo.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.

    Returns
    -------
    NDArray[float64]
        Coeficientes de aresta de cada triângulo, array (T, 3, 3).
    tuple[NDArray[int64], ...]
        (min_x, min_y, colunas) de cada triângulo, em pixels e em colunas de subamostras.
    NDArray[int64]
        Subamostras candidatas de cada triângulo (0 se a caixa está fora da tela).
    """
    i0, i1, i2 = indices
    arestas, min_x, max_x, min_y, max_y = batch_edges_and_bbox(vertices[:, 0], vertices[:, 1],
                                                               i0, i1, i2)
    colunas = (max_x - min_x + 1) * MSAA_AMOSTRAS
    linhas = (max_y - min_y + 1) * MSAA_AMOSTRAS
    valido = (min_x <= max_x) & (min_y <= max_y)
    return arestas, (min_x, min_y, colunas), np.where(valido, colunas * linhas, 0)


def _vencedoras(vertices: npt.NDArray[np.float64],
                indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                               npt.NDArray[np.int64]],
                preparo: tuple[npt.NDArray[np.float64], tuple[npt.NDArray[np.int64], ...],
                               npt.NDArray[np.int64]]) -> Iterator[Vencedoras]:
    """
    Resolve o draw call em grupos de triângulos, na ordem, devolvendo as vencedoras de cada um.

    O z-buffer é atualizado a cada grupo, então o grupo seguinte já testa contra o resultado
    do anterior, como na varredura triângulo a triângulo.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo (já sem os de costas).
    preparo : tuple
        Resultado de `_preparar` para estes vértices e índices.

    Yields
    ------
    Vencedoras
        Subamostras vencidas por um grupo de triângulos.
    """
    arestas, caixa, contagem = preparo
    ids = np.nonzero(contagem > 0)[0]
    acumulado = np.cumsum(contagem[ids])
    inicio = 0
    while inicio < ids.size:
        base = acumulado[inicio - 1] if inicio else 0
        fim = max(int(np.searchsorted(acumulado, base + MAX_CANDIDATAS, side="right")),
                  inicio + 1)
        grupo = ids[inicio:fim]
        venc = _vencedoras_grupo(vertices, indices, arestas, grupo, contagem[grupo], caixa)
        if venc is not None:
            yield venc
        inicio = fim


def rasterizar_lote(vertices: npt.NDArray[np.float64],
                    indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                   npt.NDArray[np.int64]], fonte: Fonte) -> bool:
    """
    Rasteriza todos os triângulos opacos de um draw call, pintando com uma fonte de cor.

    O resultado é o mesmo de varrer os triângulos um a um, mas a cobertura e o
    z-buffer são resolvidos de uma vez, e só as subamostras vencedoras de cada
    pixel recebem cor. Vale só para geometria opaca: com transparência, a ordem
    de mistura entre triângulos importa e o chamador deve usar a varredura
    triângulo a triângulo. O lote também só é usado quando compensa (ver
    `MIN_TRIANGULOS` e `MAX_CANDIDATAS_POR_TRIANGULO`); senão nada é desenhado
    e o chamador deve usar a varredura triângulo a triângulo.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo (já sem os de costas).
    fonte : Fonte
        Calcula a cor das subamostras vencedoras.

    Returns
    -------
    bool
        True se o draw call foi rasterizado (escrevendo em estado.ms_buffer e
        estado.depth_buffer); False se o lote não compensa e nada foi desenhado.
    """
    preparo = _preparar(vertices, indices)
    n_tri = indices[0].size
    if n_tri < MIN_TRIANGULOS or preparo[2].sum() > n_tri * MAX_CANDIDATAS_POR_TRIANGULO:
        return False

    for v in _vencedoras(vertices, indices, preparo):
        estado.ms_buffer[v.ys, v.xs, v.sy, v.sx] = fonte(v)
    return True


def fonte_flat(cores: npt.NDArray[np.generic]) -> Fonte:
    """
    Fonte de uma cor chapada por triângulo.

    Parameters
    ----------
    cores : NDArray
        Cor RGB (0-255) de cada triângulo, array (T, 3).

    Returns
    -------
    Fonte
        Devolve a cor do triângulo dono de cada subamostra.
    """
    return lambda v: cores[v.tri]


def fonte_cor_vertice(cores: npt.NDArray[np.float64]) -> Fonte:
    """
    Fonte de cor interpolada entre os vértices de cada triângulo (Gouraud).

    Parameters
    ----------
    cores : NDArray[float64]
        Cor [r, g, b] em [0, 1] dos três vértices de cada triângulo, array (T, 3, 3).

    Returns
    -------
    Fonte
        Devolve a cor interpolada, convertida para 0-255.
    """
    def fonte(v: Vencedoras) -> npt.NDArray[np.generic]:
        cor = _interpolar(v.pesos, cores, v.tri)
        return np.clip(piso(cor * 255), 0, 255).astype(np.uint8)
    return fonte


def _niveis_mip(vertices: npt.NDArray[np.float64],
                indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                               npt.NDArray[np.int64]], uv_tri: npt.NDArray[np.float64],
                mipmaps: list[npt.NDArray[np.uint8]]) -> npt.NDArray[np.int64]:
    """
    Escolhe o nível de mipmap de cada triângulo, com a mesma regra de `select_mip_level`.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.
    uv_tri : NDArray[float64]
        Coordenada de textura dos três vértices de cada triângulo, array (T, 3, 2).
    mipmaps : list[NDArray[uint8]]
        Cadeia de mipmaps da textura.

    Returns
    -------
    NDArray[int64]
        Nível de mipmap de cada triângulo.
    """
    i0, i1, i2 = indices
    x0, y0, x1, y1 = vertices[i0, 0], vertices[i0, 1], vertices[i1, 0], vertices[i1, 1]
    x2, y2 = vertices[i2, 0], vertices[i2, 1]
    area_tela = np.abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)) / 2

    u0, v0, u1, v1 = uv_tri[:, 0, 0], uv_tri[:, 0, 1], uv_tri[:, 1, 0], uv_tri[:, 1, 1]
    u2, v2 = uv_tri[:, 2, 0], uv_tri[:, 2, 1]
    area_uv = np.abs((u1 - u0) * (v2 - v0) - (v1 - v0) * (u2 - u0)) / 2
    area_texel = area_uv * mipmaps[0].shape[0] * mipmaps[0].shape[1]

    ultimo = len(mipmaps) - 1
    niveis = np.zeros(len(area_tela), dtype=np.int64)
    niveis[area_tela <= 0] = ultimo
    reduz = np.nonzero((area_tela > 0) & (area_texel > area_tela))[0]
    razoes = (area_texel[reduz] / area_tela[reduz]).tolist()
    niveis[reduz] = np.clip([math.floor(0.5 * math.log2(r)) for r in razoes], 0, ultimo)
    return niveis


def fonte_textura(vertices: npt.NDArray[np.float64],
                  indices: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                 npt.NDArray[np.int64]], mipmaps: list[npt.NDArray[np.uint8]],
                  uv_tri: npt.NDArray[np.float64]) -> Fonte:
    """
    Fonte de cor amostrada de uma textura, com o nível de mipmap de cada triângulo.

    Parameters
    ----------
    vertices : NDArray[float64]
        Vértices projetados, array (N, 4) com (x, y, w, z) de tela.
    indices : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.
    mipmaps : list[NDArray[uint8]]
        Cadeia de mipmaps da textura.
    uv_tri : NDArray[float64]
        Coordenada de textura dos três vértices de cada triângulo, array (T, 3, 2).

    Returns
    -------
    Fonte
        Devolve a cor RGB (0-255) da textura em cada subamostra.
    """
    niveis = _niveis_mip(vertices, indices, uv_tri, mipmaps)

    def fonte(v: Vencedoras) -> npt.NDArray[np.generic]:
        uv = _interpolar(v.pesos, uv_tri, v.tri)
        u, vv = uv[:, 0] % 1.0, uv[:, 1] % 1.0
        nivel_k = niveis[v.tri]
        cor = np.empty((v.tri.size, 3), dtype=np.uint8)
        usados: list[int] = np.unique(nivel_k).tolist()
        for nivel in usados:
            sel = nivel_k == nivel
            textura = mipmaps[nivel]
            largura, altura = textura.shape[0], textura.shape[1]
            tx = np.clip((u[sel] * largura).astype(np.int64), 0, largura - 1)
            # V=0 no X3D é a base da textura, mas a linha 0 da imagem (após o transpose
            # de GPU.load_texture) é o topo, daí o (1 - v).
            ty = np.clip(((1.0 - vv[sel]) * altura).astype(np.int64), 0, altura - 1)
            cor[sel] = textura[tx, ty, :3]
        return cor
    return fonte


def fonte_phong(pos_tri: npt.NDArray[np.float64], n_tri: npt.NDArray[np.float64],
                colors: Colors, textura: Fonte | None = None) -> Fonte:
    """
    Fonte de cor iluminada pelo modelo de Phong, com posição e normal interpoladas.

    Parameters
    ----------
    pos_tri : NDArray[float64]
        Posição de mundo dos três vértices de cada triângulo, array (T, 3, 3).
    n_tri : NDArray[float64]
        Normal unitária de mundo dos três vértices de cada triângulo, array (T, 3, 3).
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    textura : Fonte or None, optional
        Fonte de textura; se dada, a cor amostrada substitui a difusa do material.

    Returns
    -------
    Fonte
        Devolve a cor iluminada, convertida para 0-255.
    """
    def fonte(v: Vencedoras) -> npt.NDArray[np.generic]:
        pos = _interpolar(v.pesos, pos_tri, v.tri)
        normal = _interpolar(v.pesos, n_tri, v.tri)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        difusa = (None if textura is None
                  else np.asarray(textura(v), dtype=np.float64) / 255.0)
        cor = shade(pos, normal, colors, difusa)
        return np.clip(piso(cor * 255), 0, 255).astype(np.uint8)
    return fonte
