"""
Cobertura de triângulos por subamostra, com z-buffer e pesos perspectiva-corretos.
"""

import math

import numpy as np
import numpy.typing as npt

from ._constantes import MSAA_AMOSTRAS
from ._estado import estado
from ._tipos import VerticeProjetado


def triangle_coverage(v0: VerticeProjetado, v1: VerticeProjetado, v2: VerticeProjetado,
                       arestas: npt.NDArray[np.float64] | None,
                       bbox: tuple[int, int, int, int] | None,
                       escreve_profundidade: bool = True
                       ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                  npt.NDArray[np.int64], npt.NDArray[np.int64],
                                  npt.NDArray[np.float64]] | None:
    """
    Varredura de um triângulo 2D devolvendo a cobertura por subamostra, sem escrever cor.

    Mesma varredura MSAA de `_scan_triangle`, mas em vez de escrever uma
    cor sólida direto no buffer, devolve para cada subamostra coberta o
    seu peso baricêntrico em relação aos 3 vértices. Usado quando o
    preenchimento não é flat (cor interpolada por vértice ou textura),
    que precisam de um valor por subamostra em vez de uma cor única por
    triângulo.

    Os coeficientes de função de aresta e a bounding box (`arestas`,
    `bbox`) normalmente já vêm prontos, em vez de recalculados aqui a
    partir de `v0`, `v1`, `v2`: como as duas quantidades dependem só das
    coordenadas $(x, y)$ de tela dos 3 vértices, elas são calculadas de
    uma vez para todos os triângulos de um draw call (ver
    `batch_edges_and_bbox`), vetorizado em vez de recomputado a cada
    chamada desta função dentro do laço por triângulo (ver documento de
    rasterização por função de aresta). Para draw calls pequenos, onde
    esse pré-cálculo em lote não compensa (ver
    `prepare_edges_and_bbox`), `arestas`/`bbox` chegam como `None` e
    são calculados aqui mesmo, por triângulo, como antes da vetorização
    em lote existir.

    O peso baricêntrico bruto (calculado em coordenadas de tela, já
    projetadas) interpola atributos linearmente na tela, o que é
    incorreto sob perspectiva: dois vértices à mesma distância em tela
    podem estar a profundidades bem diferentes na câmera. Por isso o
    peso é corrigido pela perspectiva com o componente w de cada
    vértice (proporcional à profundidade na câmera) antes de ser
    devolvido: cada peso bruto é dividido pelo w do seu vértice e o
    resultado renormalizado para somar 1, que é a forma padrão de
    interpolação perspectiva-correta a partir de coordenadas já
    projetadas.

    Além da cobertura, faz o teste de z-buffer por subamostra: a
    profundidade de cada subamostra é interpolada com o peso baricêntrico
    BRUTO (não corrigido pela perspectiva, ao contrário de cor/textura,
    porque o z de NDC já é afim em coordenadas de tela, ver
    `project_points`) e comparada com `estado.depth_buffer`. Só as
    subamostras mais próximas da câmera do que o que já estava
    registrado sobrevivem e são as únicas devolvidas, o que resolve
    oclusão entre triângulos que se cruzam independente da ordem de
    desenho.

    Parameters
    ----------
    v0, v1, v2 : VerticeProjetado
        Vértices do triângulo (nessa ordem), cada um uma tupla
        (x, y, w, z) em coordenadas de tela, com w o componente w do
        espaço de clip e z o componente z de NDC, ambos devolvidos por
        `project_points`.
    arestas : NDArray[float64] or None
        Coeficientes (dy, -dx, ay*dx - ax*dy) das 3 arestas do
        triângulo, array (3, 3), devolvido por
        `batch_edges_and_bbox` para o triângulo em questão, ou
        `None` para calcular na hora (ver `prepare_edges_and_bbox`).
    bbox : tuple[int, int, int, int] or None
        Bounding box do triângulo em pixels de tela, já recortada aos
        limites da tela: (min_x, max_x, min_y, max_y); ou `None` para
        calcular na hora, sempre em conjunto com `arestas=None`.
    escreve_profundidade : bool, optional
        Se True (padrão), subamostras aprovadas no teste de z-buffer
        atualizam `estado.depth_buffer` com a nova profundidade. Geometria
        transparente passa False aqui: ela ainda é ocluída por (e testa
        contra) geometria mais próxima já desenhada, mas não grava sua
        própria profundidade, para não ocluir incorretamente outra
        geometria transparente desenhada depois dela na mesma região.

    Returns
    -------
    tuple or None
        None se o triângulo cai inteiramente fora da tela, ou se todas
        as subamostras cobertas perderam o teste de z-buffer. Senão,
        `(ys, xs, sy, sx, pesos)`: os 4 primeiros são índices em
        `estado.ms_buffer` (linha, coluna, subamostra y, subamostra x) das K
        subamostras cobertas E aprovadas no teste de profundidade;
        `pesos` é um array (3, K) com o peso baricêntrico, já corrigido
        pela perspectiva, de v0, v1 e v2 (nessa ordem) em cada
        subamostra.
    """
    x0, y0, w0, z0 = v0
    x1, y1, w1, z1 = v1
    x2, y2, w2, z2 = v2

    if bbox is None:
        min_x = max(0, math.floor(min(x0, x1, x2)))
        max_x = min(estado.width - 1, math.ceil(max(x0, x1, x2)))
        min_y = max(0, math.floor(min(y0, y1, y2)))
        max_y = min(estado.height - 1, math.ceil(max(y0, y1, y2)))
    else:
        min_x, max_x, min_y, max_y = bbox

    if min_x > max_x or min_y > max_y:
        return None

    if arestas is None:
        verts = np.array([[x0, y0], [x1, y1], [x2, y2]], dtype=np.float64)
        a = verts
        b = np.roll(verts, -1, axis=0)
        d = b - a
        arestas = np.column_stack([
            d[:,  1],
            -d[:, 0],
            a[:,  1] * d[:, 0] - a[:, 0] * d[:, 1],
        ])

    m = MSAA_AMOSTRAS
    desloc = (np.arange(m) + 0.5) / m

    # Cria uma grade de subamostras (m*m por pixel)
    xs_pixel = np.arange(min_x, max_x + 1)
    ys_pixel = np.arange(min_y, max_y + 1)
    xs_fino = (xs_pixel[:, None] + desloc[None, :]).ravel()
    ys_fino = (ys_pixel[:, None] + desloc[None, :]).ravel()

    fx, fy = np.meshgrid(xs_fino, ys_fino)
    pontos = np.stack([fx.ravel(), fy.ravel(), np.ones(fx.size)])

    # baricentro[i] é o valor da função de aresta i (edge0 = v0->v1, edge1 =
    # v1->v2, edge2 = v2->v0) em cada subamostra; o peso do vértice
    # OPOSTO a cada aresta é proporcional a esse valor (edge0 -> peso de
    # v2, edge1 -> peso de v0, edge2 -> peso de v1).
    baricentro = arestas @ pontos
    dentro = np.all(baricentro >= 0, axis=0) | np.all(baricentro <= 0, axis=0)
    dentro = dentro.reshape(len(ys_pixel), m, len(xs_pixel), m)

    ys_idx, sy_idx, xs_idx, sx_idx = np.nonzero(dentro)

    if ys_idx.size == 0:
        return None

    baricentro_4d = baricentro.reshape(3, len(ys_pixel), m, len(xs_pixel), m)
    baricentro_sel = baricentro_4d[:, ys_idx, sy_idx, xs_idx, sx_idx]  # (3, K)

    # Soma das 3 funções de aresta é constante (2x a área do triângulo,
    # com sinal), independente do ponto, normaliza para peso baricêntrico.
    total = baricentro_sel.sum(axis=0)
    pesos = np.stack([
        baricentro_sel[1] / total,  # peso de v0 (vem de edge1)
        baricentro_sel[2] / total,  # peso de v1 (vem de edge2)
        baricentro_sel[0] / total,  # peso de v2 (vem de edge0)
    ])

    ys_full = ys_pixel[ys_idx]
    xs_full = xs_pixel[xs_idx]

    # Teste de z-buffer: profundidade interpolada com o peso baricêntrico
    # bruto (afim em tela, sem correção de perspectiva) contra o valor já
    # registrado em estado.depth_buffer para cada subamostra.
    profundidade = pesos[0] * z0 + pesos[1] * z1 + pesos[2] * z2
    prof_atual = estado.depth_buffer[ys_full, xs_full, sy_idx, sx_idx]
    aprovado = profundidade <= prof_atual

    if not np.any(aprovado):
        return None

    ys_full, xs_full = ys_full[aprovado], xs_full[aprovado]
    sy_idx, sx_idx = sy_idx[aprovado], sx_idx[aprovado]
    pesos = pesos[:, aprovado]

    if escreve_profundidade:
        estado.depth_buffer[ys_full, xs_full, sy_idx, sx_idx] = profundidade[aprovado]

    # Correção de perspectiva: divide cada peso pelo w do respectivo
    # vértice e renormaliza para voltar a somar 1.
    pesos_persp = pesos / np.array([w0, w1, w2])[:, None]
    pesos_persp /= pesos_persp.sum(axis=0)

    return ys_full, xs_full, sy_idx, sx_idx, pesos_persp
