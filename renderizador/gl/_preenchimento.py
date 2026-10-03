"""
Preenchimento de malhas de triângulos (flat, cor, textura, luz).
"""

import numpy as np
import numpy.typing as npt

from ._arestas import prepare_edges_and_bbox
from ._cores import to_rgb8
from ._estado import estado
from ._lote import fill_lit_batch
from ._projecao import front_facing_mask, project_points, to_world
from ._texturas import get_texture_mipmaps
from ._tipos import Colors, Malha, Textura, VerticeProjetado
from ._triangulacao import fan_triangulate_cached
from ._varredura import (
    scan_triangle_color,
    scan_triangle_depth,
    scan_triangle_lit,
    scan_triangle_textured,
)


def fill_face_set_textured(idx0: list[int], idx1: list[int], idx2: list[int],
                            verts: list[VerticeProjetado], frente: npt.NDArray[np.bool_],
                            arestas_l: list[npt.NDArray[np.float64] | None],
                            bboxes: list[tuple[int, int, int, int] | None],
                            texCoord: list[float], texCoordIndex: list[int],
                            coordIndex: list[int], current_texture: list[str],
                            alpha: float) -> bool:
    """
    Tenta preencher as faces de um IndexedFaceSet com textura.

    Extraído de `indexedFaceSet` para reduzir sua complexidade
    cognitiva: a decisão de usar textura, o teste de topologia de
    `texCoordIndex` e o laço de varredura ficam isolados aqui.

    Parameters
    ----------
    idx0, idx1, idx2 : list[int]
        Índices (em `verts`) do primeiro, segundo e terceiro vértice de
        cada triângulo já triangulado em leque e filtrado por
        back-face culling.
    verts : list[VerticeProjetado]
        Vértices já projetados em coordenadas de tela (ver
        `project_points`), indexados por `idx0`/`idx1`/`idx2`.
    frente : NDArray[bool_]
        Máscara de back-face culling usada para os triângulos de
        `idx0`/`idx1`/`idx2`, para filtrar `texCoordIndex` na mesma
        topologia.
    arestas_l, bboxes : list
        Coeficientes de aresta e bounding box de cada triângulo de
        `idx0`/`idx1`/`idx2` (mesma ordem e tamanho), devolvidos por
        `batch_edges_and_bbox` e já convertidos para lista.
    texCoord : list[float]
        Coordenadas de textura por vértice no formato [u0, v0, u1, v1, ...].
    texCoordIndex : list[int]
        Índices de coordenada de textura (em `texCoord`), mesmo formato
        de `coordIndex`; se vazio, usa-se `coordIndex` no lugar.
    coordIndex : list[int]
        Índices de vértice originais (antes do leque), usados como
        fallback de `texCoordIndex` quando este está vazio.
    current_texture : list[str]
        Caminho(s) da textura atual do Appearance, se houver.
    alpha : float
        Opacidade da geometria em [0, 1] (`1 - transparency`).

    Returns
    -------
    bool
        True se havia textura e a topologia de `texCoordIndex` bateu
        com a de `coordIndex` (e os triângulos já foram desenhados,
        terminando o preenchimento da face). False se não há textura,
        ou a topologia não bate e o chamador deve tentar outro
        preenchimento.
    """
    mipmaps = get_texture_mipmaps(current_texture) if texCoord and current_texture else None

    if mipmaps is None:
        return False

    tidx = texCoordIndex if texCoordIndex else coordIndex
    ti0, ti1, ti2, _ = fan_triangulate_cached(tidx)

    if ti0.size != frente.size:
        return False

    ti0, ti1, ti2 = ti0[frente], ti1[frente], ti2[frente]
    uv = np.asarray(texCoord, dtype=np.float64).reshape(-1, 2)
    uv0, uv1, uv2 = uv[ti0], uv[ti1], uv[ti2]

    # zip de 6 iteráveis cai no overload genérico Iterable[Any] do
    # typeshed (só tipa até 5); zipar índices e uv's em dois 3-tuplos
    # primeiro mantém os 3 zips dentro do limite tipado.
    for t, ((a, b, c), (uva, uvb, uvc)) in enumerate(zip(zip(idx0, idx1, idx2),
                                                          zip(uv0, uv1, uv2))):
        scan_triangle_textured(verts[a], uva, verts[b], uvb, verts[c], uvc,
                                   mipmaps, arestas_l[t], bboxes[t], alpha)

    return True


def fill_face_set_color_per_vertex(idx0: list[int], idx1: list[int], idx2: list[int],
                                    verts: list[VerticeProjetado],
                                    frente: npt.NDArray[np.bool_], color: list[float],
                                    colorIndex: list[int], coordIndex: list[int],
                                    arestas_l: list[npt.NDArray[np.float64] | None],
                                    bboxes: list[tuple[int, int, int, int] | None],
                                    alpha: float) -> bool:
    """
    Tenta preencher as faces de um IndexedFaceSet com cor por vértice (Gouraud).

    Extraído de `indexedFaceSet` pelo mesmo motivo de
    `fill_face_set_textured`: isola o teste de topologia de
    `colorIndex` e o laço de varredura.

    Parameters
    ----------
    idx0, idx1, idx2 : list[int]
        Índices (em `verts`) de cada triângulo já triangulado em leque
        e filtrado por back-face culling.
    verts : list[VerticeProjetado]
        Vértices já projetados em coordenadas de tela.
    frente : NDArray[bool_]
        Máscara de back-face culling, para filtrar `colorIndex` na
        mesma topologia.
    color : list[float]
        Cores por vértice no formato [r0, g0, b0, r1, g1, b1, ...].
    colorIndex : list[int]
        Índices de cor (em `color`), mesmo formato de `coordIndex`; se
        vazio, usa-se `coordIndex` no lugar.
    coordIndex : list[int]
        Índices de vértice originais, usados como fallback de
        `colorIndex` quando este está vazio.
    arestas_l, bboxes : list
        Coeficientes de aresta e bounding box de cada triângulo de
        `idx0`/`idx1`/`idx2` (mesma ordem e tamanho), devolvidos por
        `batch_edges_and_bbox` e já convertidos para lista.
    alpha : float
        Opacidade da geometria em [0, 1] (`1 - transparency`).

    Returns
    -------
    bool
        True se a topologia de `colorIndex` bateu com a de
        `coordIndex` (e os triângulos já foram desenhados). False se a
        topologia não bate e o chamador deve tentar outro preenchimento.
    """
    cores = np.asarray(color, dtype=np.float64).reshape(-1, 3)
    ci0, ci1, ci2, _ = fan_triangulate_cached(colorIndex if colorIndex else coordIndex)

    if ci0.size != frente.size:
        return False

    ci0, ci1, ci2 = ci0[frente], ci1[frente], ci2[frente]
    cor0, cor1, cor2 = cores[ci0], cores[ci1], cores[ci2]

    # Mesmo motivo do zip duplo em fill_face_set_textured.
    for t, ((a, b, c), (ca, cb, cc)) in enumerate(zip(zip(idx0, idx1, idx2),
                                                       zip(cor0, cor1, cor2))):
        scan_triangle_color(verts[a], ca, verts[b], cb, verts[c], cc,
                                arestas_l[t], bboxes[t], alpha)

    return True


def fill_face_set_color_per_face(idx0: list[int], idx1: list[int], idx2: list[int],
                                  verts: list[VerticeProjetado],
                                  face_id: npt.NDArray[np.int64], color: list[float],
                                  colorIndex: list[int],
                                  arestas_l: list[npt.NDArray[np.float64] | None],
                                  bboxes: list[tuple[int, int, int, int] | None],
                                  alpha: float) -> None:
    """
    Preenche as faces de um IndexedFaceSet com uma cor sólida por face inteira.

    Extraído de `indexedFaceSet` pelo mesmo motivo de
    `fill_face_set_textured`. Ao contrário da variante por vértice,
    sempre desenha: uma cor por face, diferente de coordenada de
    textura ou cor por vértice, não tem uma topologia própria de
    `colorIndex` (um índice por face, sem separadores -1) que possa
    divergir de `coordIndex`.

    Parameters
    ----------
    idx0, idx1, idx2 : list[int]
        Índices (em `verts`) de cada triângulo já triangulado em leque
        e filtrado por back-face culling.
    verts : list[VerticeProjetado]
        Vértices já projetados em coordenadas de tela.
    face_id : NDArray[int64]
        Posição, na lista de faces do IndexedFaceSet, da face de origem
        de cada triângulo em `idx0`/`idx1`/`idx2` (0-based, já filtrada
        por back-face culling).
    color : list[float]
        Cores por face no formato [r0, g0, b0, r1, g1, b1, ...].
    colorIndex : list[int]
        Índices de cor (em `color`) por face, sem separadores -1; se
        vazio, a i-ésima face usa a i-ésima cor (a própria `face_id`).
    arestas_l, bboxes : list
        Coeficientes de aresta e bounding box de cada triângulo de
        `idx0`/`idx1`/`idx2` (mesma ordem e tamanho), devolvidos por
        `batch_edges_and_bbox` e já convertidos para lista.
    alpha : float
        Opacidade da geometria em [0, 1] (`1 - transparency`).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    cores = np.asarray(color, dtype=np.float64).reshape(-1, 3)

    if colorIndex:
        color_idx_por_tri = np.asarray(colorIndex, dtype=np.int64)[face_id]
    else:
        color_idx_por_tri = face_id

    cor_tri = to_rgb8(cores[color_idx_por_tri])

    for t, (a, b, c, cor) in enumerate(zip(idx0, idx1, idx2, cor_tri)):
        scan_triangle_depth(verts[a], verts[b], verts[c],
                                arestas_l[t], bboxes[t], cor, alpha)


def fill_triangles(posicoes: npt.ArrayLike, verts: list[VerticeProjetado],
                    i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                    i2: npt.NDArray[np.int64],
                    arestas_l: list[npt.NDArray[np.float64] | None],
                    bboxes: list[tuple[int, int, int, int] | None], colors: Colors,
                    normais: npt.NDArray[np.float64] | None = None,
                    textura: Textura | None = None) -> None:
    """
    Preenche triângulos já projetados com a cor do material, iluminada se houver luzes.

    Sem luzes ativas, preenche flat com `colors["emissiveColor"]` (ou com
    a textura, se dada). Com luzes, sombreia por subamostra
    (`scan_triangle_lit`), usando as normais por vértice se dadas e,
    senão, a normal de cada face.

    Parameters
    ----------
    posicoes : ArrayLike
        Vértices em coordenadas de objeto, [x0, y0, z0, x1, ...] ou (N, 3).
    verts : list[VerticeProjetado]
        Vértices projetados, na mesma ordem de `posicoes`.
    i0, i1, i2 : NDArray[int64]
        Índices dos três vértices de cada triângulo (já sem os de costas).
    arestas_l : list[NDArray[float64] or None]
        Arestas de cada triângulo (ver `prepare_edges_and_bbox`).
    bboxes : list[tuple[int, int, int, int] or None]
        Bounding box de cada triângulo.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    normais : NDArray[float64] or None, optional
        Normais (N, 3) em coordenadas de objeto, uma por vértice; se
        None, usa-se a normal plana de cada triângulo.
    textura : Textura or None, optional
        Mipmaps e UVs por vértice; se dada, a textura substitui a cor
        do material (a difusa, quando há luz).

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    if estado.lights:
        fill_lit(posicoes, verts, (i0, i1, i2), arestas_l, bboxes, colors,
                     normais, textura)
    else:
        fill_unlit(verts, (i0, i1, i2), arestas_l, bboxes, colors, textura)


def fill_unlit(verts: list[VerticeProjetado],
                tri: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                           npt.NDArray[np.int64]],
                arestas_l: list[npt.NDArray[np.float64] | None],
                bboxes: list[tuple[int, int, int, int] | None], colors: Colors,
                textura: Textura | None) -> None:
    """
    Preenche triângulos sem luz: textura se houver, senão a cor emissiva flat.

    Parameters
    ----------
    verts : list[VerticeProjetado]
        Vértices projetados.
    tri : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.
    arestas_l : list[NDArray[float64] or None]
        Arestas de cada triângulo.
    bboxes : list[tuple[int, int, int, int] or None]
        Bounding box de cada triângulo.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    textura : Textura or None
        Mipmaps e UVs por vértice, ou None para preencher flat.

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    alpha = 1.0 - colors["transparency"]
    idx0: list[int] = tri[0].tolist()
    idx1: list[int] = tri[1].tolist()
    idx2: list[int] = tri[2].tolist()

    if textura is not None:
        mipmaps, uv = textura
        for t, (a, b, c) in enumerate(zip(idx0, idx1, idx2)):
            scan_triangle_textured(verts[a], uv[a], verts[b], uv[b], verts[c], uv[c],
                                       mipmaps, arestas_l[t], bboxes[t], alpha)
        return

    cor = to_rgb8(colors["emissiveColor"])
    for t, (a, b, c) in enumerate(zip(idx0, idx1, idx2)):
        scan_triangle_depth(verts[a], verts[b], verts[c],
                                arestas_l[t], bboxes[t], cor, alpha)


def fill_lit(posicoes: npt.ArrayLike, verts: list[VerticeProjetado],
              tri: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                         npt.NDArray[np.int64]],
              arestas_l: list[npt.NDArray[np.float64] | None],
              bboxes: list[tuple[int, int, int, int] | None], colors: Colors,
              normais: npt.NDArray[np.float64] | None, textura: Textura | None) -> None:
    """
    Preenche triângulos com iluminação Phong por subamostra.

    Parameters
    ----------
    posicoes : ArrayLike
        Vértices em coordenadas de objeto, [x0, y0, z0, x1, ...] ou (N, 3).
    verts : list[VerticeProjetado]
        Vértices projetados.
    tri : tuple[NDArray[int64], NDArray[int64], NDArray[int64]]
        Índices dos três vértices de cada triângulo.
    arestas_l : list[NDArray[float64] or None]
        Arestas de cada triângulo.
    bboxes : list[tuple[int, int, int, int] or None]
        Bounding box de cada triângulo.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    normais : NDArray[float64] or None
        Normais por vértice em coordenadas de objeto, ou None para usar a
        normal plana de cada triângulo.
    textura : Textura or None
        Mipmaps e UVs por vértice; se dada, a cor amostrada substitui a
        difusa do material.

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    alpha = 1.0 - colors["transparency"]
    i0, i1, i2 = tri
    idx0: list[int] = i0.tolist()
    idx1: list[int] = i1.tolist()
    idx2: list[int] = i2.tolist()

    mundo, n_mundo = to_world(np.asarray(posicoes, dtype=np.float64).reshape(-1, 3),
                                  normais)
    indices = np.stack([i0, i1, i2], axis=1)
    if n_mundo is None:
        n_face = np.cross(mundo[i1] - mundo[i0], mundo[i2] - mundo[i0])
        n_face /= np.maximum(np.linalg.norm(n_face, axis=1, keepdims=True), 1e-12)
        n_tri = np.repeat(n_face[:, None, :], 3, axis=1)
    else:
        n_tri = n_mundo[indices]
    pos_tri = mundo[indices]

    if textura is None and alpha >= 1.0:
        fill_lit_batch(np.array(verts), tri, pos_tri, n_tri, colors)
        return

    for t, (a, b, c) in enumerate(zip(idx0, idx1, idx2)):
        tex = (textura[0], textura[1][indices[t]]) if textura is not None else None
        scan_triangle_lit(verts[a], verts[b], verts[c], pos_tri[t], n_tri[t],
                              arestas_l[t], bboxes[t], colors, alpha, tex)


def draw_mesh(malha: Malha, colors: Colors, mipmaps: list[npt.NDArray[np.uint8]] | None = None
               ) -> None:
    """
    Projeta, descarta faces de costas e rasteriza uma malha de triângulos indexada.

    Caminho comum das primitivas (Box, Sphere, Cone e Cylinder): elas só
    geram a malha, e o resto do pipeline é o mesmo de `triangleSet`.
    Sem luzes ativas, preenche com `colors["emissiveColor"]` (flat). Com
    luzes, sombreia por subamostra com as normais interpoladas (Phong
    shading, ver `fill_triangles`).

    Parameters
    ----------
    malha : Malha
        Posições (em coordenadas de objeto), normais e triângulos.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    mipmaps : list[NDArray[uint8]] or None, optional
        Cadeia de mipmaps da textura da malha (ver
        `get_texture_mipmaps`), se tiver; os UVs vêm da própria malha.

    Returns
    -------
    None
        Escreve em estado.ms_buffer; não há retorno.
    """
    posicoes, normais, triangulos, uv = malha
    tela_x, tela_y, tela_w, tela_z = project_points(posicoes.ravel().tolist())

    i0, i1, i2 = triangulos[:, 0], triangulos[:, 1], triangulos[:, 2]
    frente = front_facing_mask(tela_x, tela_y, i0, i1, i2)
    i0, i1, i2 = i0[frente], i1[frente], i2[frente]

    if i0.size == 0:
        return

    verts: list[VerticeProjetado] = list(
        zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
    arestas_l, bboxes = prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)
    textura = (mipmaps, uv) if mipmaps else None
    fill_triangles(posicoes, verts, i0, i1, i2, arestas_l, bboxes, colors, normais,
                       textura)
