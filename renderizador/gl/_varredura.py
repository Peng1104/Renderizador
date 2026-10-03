"""
Varredura de triângulos: flat, cor por vértice, textura e Phong.
"""

import math

import numpy as np
import numpy.typing as npt

from ._cobertura import triangle_coverage
from ._constantes import MSAA_AMOSTRAS
from ._cores import piso
from ._estado import estado
from ._framebuffer import blend_write
from ._iluminacao import shade
from ._texturas import sample_texture
from ._tipos import Colors, Textura, VerticeProjetado


def scan_triangle(x0: float, y0: float, x1: float, y1: float,
                   x2: float, y2: float, cor: npt.NDArray[np.int64]) -> None:
    """
    Varre um triângulo 2D, marcando a cobertura dele no buffer de multisample.

    Aplica o MSAA, sem fazer blend (flat shading).

    Parameters
    ----------
    x0 : float
        Coordenada x do primeiro vértice, em coordenadas de tela.
    y0 : float
        Coordenada y do primeiro vértice, em coordenadas de tela.
    x1 : float
        Coordenada x do segundo vértice, em coordenadas de tela.
    y1 : float
        Coordenada y do segundo vértice, em coordenadas de tela.
    x2 : float
        Coordenada x do terceiro vértice, em coordenadas de tela.
    y2 : float
        Coordenada y do terceiro vértice, em coordenadas de tela.
    cor : NDArray[int64]
        Cor RGB (0-255) de preenchimento do triângulo.

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    # Bounding box do triângulo
    min_x = max(0, math.floor(min(x0, x1, x2)))
    max_x = min(estado.width - 1, math.ceil(max(x0, x1, x2)))
    min_y = max(0, math.floor(min(y0, y1, y2)))
    max_y = min(estado.height - 1, math.ceil(max(y0, y1, y2)))

    # Fora da tela: não há pixels a preencher, retorna sem escrever nada.
    if min_x > max_x or min_y > max_y:
        return

    # Os pontos das vértices do triângulo
    verts = np.array([
        [x0, y0],
        [x1, y1],
        [x2, y2]
    ], dtype=np.float64)

    a = verts
    b = np.roll(verts, -1, axis=0)
    d = b - a

    # Cada aresta (a -> b) define uma reta cuja função é
    # edge(p) = dy*px - dx*py + (ay*dx - ax*dy), com [dx, dy] = b - a.
    arestas = np.column_stack([
        d[:,  1],                               # dy
        -d[:, 0],                               # -dx
        a[:,  1] * d[:, 0] - a[:, 0] * d[:, 1], # (ay*dx - ax*dy)
    ])

    # m subamostras por eixo (m*m por pixel), centralizadas em cada célula
    # 1/m de um pixel: com m=2 (4x MSAA), deslocamentos 0.25 e 0.75.
    m = MSAA_AMOSTRAS
    desloc = (np.arange(m) + 0.5) / m

    xs_pixel = np.arange(min_x, max_x + 1)
    ys_pixel = np.arange(min_y, max_y + 1)
    xs_fino = (xs_pixel[:, None] + desloc[None, :]).ravel()  # (W*m,)
    ys_fino = (ys_pixel[:, None] + desloc[None, :]).ravel()  # (H*m,)

    # Area de cada subamostra: (H*m, W*m)
    fx, fy = np.meshgrid(xs_fino, ys_fino)
    pontos = np.stack([fx.ravel(), fy.ravel(), np.ones(fx.size)])

    baricentro = arestas @ pontos
    dentro = np.all(baricentro >= 0, axis=0) | np.all(baricentro <= 0, axis=0)

    # Agrupa as m*m subamostras de cada pixel. O reshape (H*m, W*m) ->
    # (H, m, W, m) é válido porque xs_fino/ys_fino foram montados
    # agrupados por pixel (todas as subamostras de um pixel são
    # consecutivas). Escreve a cor só nas subamostras (y, x, sy, sx) que
    # caíram dentro do triângulo.
    dentro = dentro.reshape(len(ys_pixel), m, len(xs_pixel), m)

    # Acha os índices (pixel y, subamostra y, pixel x, subamostra x) dentro do triângulo.
    ys_idx, sy_idx, xs_idx, sx_idx = np.nonzero(dentro)

    # Preenche as subamostras correspondentes no buffer de multisample com a cor do triângulo.
    estado.ms_buffer[ys_pixel[ys_idx], xs_pixel[xs_idx], sy_idx, sx_idx] = cor


def scan_triangle_depth(v0: VerticeProjetado, v1: VerticeProjetado,
                         v2: VerticeProjetado, arestas: npt.NDArray[np.float64] | None,
                         bbox: tuple[int, int, int, int] | None, cor: npt.NDArray[np.int64],
                         alpha: float = 1.0) -> None:
    """
    Varre um triângulo 3D com preenchimento flat, testando o z-buffer.

    Equivalente a `scan_triangle`, mas para geometria 3D já
    projetada: usa `triangle_coverage` para descartar (e não
    escrever) as subamostras encobertas por geometria mais perto da
    câmera já desenhada no frame, o que corrige a oclusão entre
    triângulos de objetos diferentes que se cruzam no espaço (sem
    z-buffer, a oclusão dependeria só da ordem de desenho no grafo de
    cena, painter's algorithm implícito e incorreto para geometria que
    se cruza). `alpha` < 1 mistura a cor com o que já está no buffer em
    vez de sobrescrever (ver `blend_write`), e não atualiza o
    z-buffer (ver `triangle_coverage`), para que geometria
    transparente não esconda o que está atrás dela de outra geometria
    transparente desenhada depois.

    Parameters
    ----------
    v0, v1, v2 : VerticeProjetado
        Vértices do triângulo (nessa ordem), cada um uma tupla
        (x, y, w, z) em coordenadas de tela, com w o componente w do
        espaço de clip e z o componente z de NDC, ambos devolvidos por
        `project_points`.
    arestas : NDArray[float64] or None
        Coeficientes de aresta do triângulo, array (3, 3), devolvido
        por `batch_edges_and_bbox`, ou None (ver
        `prepare_edges_and_bbox`).
    bbox : tuple[int, int, int, int] or None
        Bounding box do triângulo em pixels de tela: (min_x, max_x,
        min_y, max_y), devolvida por `batch_edges_and_bbox`, ou
        None junto com arestas=None.
    cor : NDArray[int64]
        Cor RGB (0-255) de preenchimento do triângulo.
    alpha : float, optional
        Opacidade da geometria em [0, 1] (`1 - transparency` do
        Material X3D), por padrão 1.0 (opaco).

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    cobertura = triangle_coverage(v0, v1, v2, arestas, bbox,
                                      escreve_profundidade=alpha >= 1.0)

    if cobertura is None:
        return

    ys, xs, sy, sx, _ = cobertura
    blend_write(ys, xs, sy, sx, cor, alpha)


def scan_triangle_color(v0: VerticeProjetado, cor0: npt.NDArray[np.float64],
                         v1: VerticeProjetado, cor1: npt.NDArray[np.float64],
                         v2: VerticeProjetado, cor2: npt.NDArray[np.float64],
                         arestas: npt.NDArray[np.float64] | None,
                         bbox: tuple[int, int, int, int] | None,
                         alpha: float = 1.0
                         ) -> None:
    """
    Varre um triângulo 2D com cor interpolada por vértice (Gouraud shading).

    A interpolação é corrigida pela perspectiva (ver `triangle_coverage`):
    sem essa correção, um vértice muito mais distante que os outros dois
    puxaria a cor para perto de si numa fração maior da área em tela do
    que deveria, porque a área em tela por si só não reflete a
    profundidade real do ponto na câmera. `triangle_coverage` também
    faz o teste de z-buffer, então subamostras encobertas por geometria
    já desenhada mais perto da câmera não são escritas aqui. `alpha` < 1
    mistura a cor com o que já está no buffer em vez de sobrescrever
    (ver `blend_write`) e não atualiza o z-buffer.

    Parameters
    ----------
    v0, v1, v2 : VerticeProjetado
        Vértices do triângulo (nessa ordem), cada um uma tupla
        (x, y, w, z) em coordenadas de tela, devolvida por
        `project_points`.
    cor0, cor1, cor2 : NDArray[float64]
        Cor de cada vértice (na mesma ordem), no formato X3D [r, g, b]
        com cada canal em [0, 1].
    arestas : NDArray[float64] or None
        Coeficientes de aresta do triângulo, array (3, 3), devolvido
        por `batch_edges_and_bbox`, ou None (ver
        `prepare_edges_and_bbox`).
    bbox : tuple[int, int, int, int] or None
        Bounding box do triângulo em pixels de tela, devolvida por
        `batch_edges_and_bbox`, ou None junto com arestas=None.
    alpha : float, optional
        Opacidade da geometria em [0, 1] (`1 - transparency` do
        Material X3D), por padrão 1.0 (opaco).

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    cobertura = triangle_coverage(v0, v1, v2, arestas, bbox,
                                      escreve_profundidade=alpha >= 1.0)

    if cobertura is None:
        return

    ys, xs, sy, sx, pesos = cobertura

    cor = (pesos[0][:, None] * cor0 + pesos[1][:, None] * cor1
           + pesos[2][:, None] * cor2)
    cor_rgb8 = np.clip(piso(cor * 255), 0, 255).astype(np.uint8)

    blend_write(ys, xs, sy, sx, cor_rgb8, alpha)


def scan_triangle_textured(v0: VerticeProjetado, uv0: npt.NDArray[np.float64],
                            v1: VerticeProjetado, uv1: npt.NDArray[np.float64],
                            v2: VerticeProjetado, uv2: npt.NDArray[np.float64],
                            mipmaps: list[npt.NDArray[np.uint8]],
                            arestas: npt.NDArray[np.float64] | None,
                            bbox: tuple[int, int, int, int] | None,
                            alpha: float = 1.0) -> None:
    """
    Varre um triângulo 2D com uma textura mapeada por coordenadas UV por vértice.

    Amostragem nearest-neighbor (sem filtragem bilinear) dentro do nível
    de mipmap escolhido (ver `select_mip_level`), com wrap (repeat)
    das coordenadas UV fora de [0, 1], que é o padrão X3D
    (`repeatS`/`repeatT` = TRUE). A interpolação das coordenadas UV é
    corrigida pela perspectiva (ver `triangle_coverage`), senão a
    textura distorce em superfícies inclinadas em relação à câmera.
    `triangle_coverage` também faz o teste de z-buffer, então
    subamostras encobertas por geometria já desenhada mais perto da
    câmera não são escritas aqui. `alpha` < 1 mistura a cor com o que já
    está no buffer em vez de sobrescrever (ver `blend_write`) e não
    atualiza o z-buffer.

    Parameters
    ----------
    v0, v1, v2 : VerticeProjetado
        Vértices do triângulo (nessa ordem), cada um uma tupla
        (x, y, w, z) em coordenadas de tela, devolvida por
        `project_points`.
    uv0, uv1, uv2 : NDArray[float64]
        Coordenada de textura [u, v] de cada vértice (na mesma ordem).
    mipmaps : list[NDArray[uint8]]
        Cadeia de mipmaps da textura, do nível 0 (original) ao 1x1,
        no formato devolvido por `get_texture_mipmaps` (cada nível
        com eixos [u][v], como `gpu.GPU.load_texture`).
    arestas : NDArray[float64] or None
        Coeficientes de aresta do triângulo, array (3, 3), devolvido
        por `batch_edges_and_bbox`, ou None (ver
        `prepare_edges_and_bbox`).
    bbox : tuple[int, int, int, int] or None
        Bounding box do triângulo em pixels de tela, devolvida por
        `batch_edges_and_bbox`, ou None junto com arestas=None.
    alpha : float, optional
        Opacidade da geometria em [0, 1] (`1 - transparency` do
        Material X3D), por padrão 1.0 (opaco).

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    cobertura = triangle_coverage(v0, v1, v2, arestas, bbox,
                                      escreve_profundidade=alpha >= 1.0)

    if cobertura is None:
        return

    ys, xs, sy, sx, pesos = cobertura

    cor = sample_texture(pesos, (v0, v1, v2), (uv0, uv1, uv2), mipmaps)

    blend_write(ys, xs, sy, sx, cor, alpha)


def scan_triangle_lit(v0: VerticeProjetado, v1: VerticeProjetado, v2: VerticeProjetado,
                       pos: npt.NDArray[np.float64], normal: npt.NDArray[np.float64],
                       arestas: npt.NDArray[np.float64] | None,
                       bbox: tuple[int, int, int, int] | None, colors: Colors,
                       alpha: float, textura: Textura | None = None) -> None:
    """
    Varre um triângulo calculando a iluminação em cada subamostra (Phong shading).

    Interpola a posição e a normal de mundo com os pesos
    perspectiva-corretos de `triangle_coverage` e aplica `shade`
    em cada subamostra coberta. Por isso o brilho especular aparece no
    interior de um triângulo, onde nenhum vértice o tem.

    Parameters
    ----------
    v0, v1, v2 : VerticeProjetado
        Vértices do triângulo, em coordenadas de tela.
    pos : NDArray[float64]
        Posições de mundo dos três vértices, array (3, 3).
    normal : NDArray[float64]
        Normais unitárias de mundo dos três vértices, array (3, 3).
    arestas : NDArray[float64] or None
        Coeficientes de aresta do triângulo (ver `prepare_edges_and_bbox`).
    bbox : tuple[int, int, int, int] or None
        Bounding box do triângulo em pixels de tela, ou None junto com arestas=None.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    alpha : float
        Opacidade da geometria em [0, 1].
    textura : Textura or None, optional
        Textura do triângulo já com os UVs dos três vértices (array
        (3, 2)); se dada, a cor amostrada substitui a difusa do material.

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    cobertura = triangle_coverage(v0, v1, v2, arestas, bbox,
                                      escreve_profundidade=alpha >= 1.0)

    if cobertura is None:
        return

    ys, xs, sy, sx, pesos = cobertura

    difusa = None
    if textura is not None:
        mipmaps, uv3 = textura
        difusa = sample_texture(pesos, (v0, v1, v2), (uv3[0], uv3[1], uv3[2]),
                                    mipmaps) / 255.0

    n = pesos.T @ normal
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cor = shade(pesos.T @ pos, n, colors, difusa)
    cor_rgb8 = np.clip(piso(cor * 255), 0, 255).astype(np.uint8)

    blend_write(ys, xs, sy, sx, cor_rgb8, alpha)
