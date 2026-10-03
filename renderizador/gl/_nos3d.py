"""
Nós X3D de malhas 3D: triângulos, tiras e IndexedFaceSet.
"""

import numpy as np
import numpy.typing as npt

from ._arestas import prepare_edges_and_bbox
from ._preenchimento import (
    fill_face_set_color_per_face,
    fill_face_set_color_per_vertex,
    fill_face_set_textured,
    fill_triangles,
)
from ._projecao import front_facing_mask, project_points
from ._tipos import Colors, VerticeProjetado
from ._triangulacao import fan_triangulate_cached, strip_triangle_indices


def triangleSet(point: list[float], colors: Colors) -> None:
    """
    Renderiza TriangleSet: uma lista de triângulos 3D independentes.

    Descarta (back-face culling) os triângulos de costas para a câmera
    antes de varrer, seguindo a convenção anti-horária.

    Parameters
    ----------
    point : list[float]
        Coordenadas dos vértices no formato [x0, y0, z0, x1, y1, z1, ...],
        em coordenadas de objeto. Cada grupo de 3 vértices (9 floats)
        forma um triângulo independente.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor de preenchimento (flat shading).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    tela_x, tela_y, tela_w, tela_z = project_points(point)

    n_tri = len(tela_x) // 3
    i0 = np.arange(0, n_tri * 3, 3)
    i1, i2 = i0 + 1, i0 + 2

    frente = front_facing_mask(tela_x, tela_y, i0, i1, i2)
    i0, i1, i2 = i0[frente], i1[frente], i2[frente]

    verts: list[VerticeProjetado] = list(
        zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
    i0.tolist()
    i1.tolist()
    i2.tolist()

    arestas_l, bboxes = prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

    fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)


def triangleStripSet(point: list[float], stripCount: list[int], colors: Colors) -> None:
    """
    Renderiza uma ou mais tiras de triângulos interconectados (TriangleStripSet).

    Liga os vértices em sequência dentro de cada tira: o primeiro
    triângulo usa os vértices 0, 1 e 2; o seguinte usa 1, 2 e 3; depois
    2, 3 e 4; e assim por diante. A cada triângulo, o sentido "cru" da
    sequência da tira alterna,b a função corrige isso internamente para
    manter todos os triângulos no sentido anti-horário, e descarta
    (back-face culling) os que ficam de costas para a câmera.

    Parameters
    ----------
    point : list[float]
        Coordenadas dos vértices no formato [x0, y0, z0, x1, y1, z1, ...],
        um float por eixo na ordem x, y, z, concatenados sequencialmente
        para todos os vértices de todas as tiras.
    stripCount : list[int]
        Quantidade de vértices de cada tira, na ordem em que aparecem em
        `point`. A soma dos valores deve ser igual ao número de vértices
        em `point` (point tem 3 * sum(stripCount) floats).
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor de preenchimento (flat shading).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    tela_x, tela_y, tela_w, tela_z = project_points(point)

    # Array contento a quantidade de vértices de cada tira
    counts = np.asarray(stripCount, dtype=np.int64)

    # Array contendo os offsets de cada tira (inicio + quantidade)
    offsets = np.concatenate(([0], np.cumsum(counts)))

    # Cria uma lista de arrays, cada um contendo os índices de vértices de uma tira
    tiras: list[npt.NDArray[np.int64]] = [
        np.arange(offsets[i], offsets[i + 1]) for i in range(len(counts))]

    i0, i1, i2 = strip_triangle_indices(tiras)

    # Back-Face Culling: descartar triângulos de costas para a câmera antes de rasterizar
    frente = front_facing_mask(tela_x, tela_y, i0, i1, i2)
    i0, i1, i2 = i0[frente], i1[frente], i2[frente]

    verts: list[VerticeProjetado] = list(
        zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))

    i0.tolist()
    i1.tolist()
    i2.tolist()

    arestas_l, bboxes = prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

    fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)


def indexedTriangleStripSet(point: list[float], index: list[int], colors: Colors) -> None:
    """
    Renderiza IndexedTriangleStripSet: tiras de triângulos indexadas.

    Mesma lógica de conexão do TriangleStripSet (0,1,2 depois 1,2,3
    depois 2,3,4...), mas os índices de vértice, vêm em `index`, com 
    tiras separadas por -1. Descarta (back-face culling) os triângulos
    de costas para a câmera antes de rasterizar, seguindo a convenção
    anti-horária.

    Parameters
    ----------
    point : list[float]
        Coordenadas dos vértices no formato [x0, y0, z0, x1, y1, z1, ...],
        em coordenadas de objeto.
    index : list[int]
        Índices de vértice (em `point`) que formam as tiras, na ordem em
        que devem ser conectados. O valor -1 separa uma tira da próxima.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor de preenchimento (flat shading).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    tela_x, tela_y, tela_w, tela_z = project_points(point)

    idx = np.asarray(index, dtype=np.int64)
    # Divide em tiras nos pontos onde -1 aparece; cada segmento resultante,
    # exceto o primeiro, começa com o próprio -1 (removido pela máscara).
    cortes = np.nonzero(idx == -1)[0]
    tiras: list[npt.NDArray[np.int64]] = [
        segmento[segmento != -1] for segmento in np.split(idx, cortes)
    ]

    i0, i1, i2 = strip_triangle_indices(tiras)
    frente = front_facing_mask(tela_x, tela_y, i0, i1, i2)
    i0, i1, i2 = i0[frente], i1[frente], i2[frente]

    verts: list[VerticeProjetado] = list(
        zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
    i0.tolist()
    i1.tolist()
    i2.tolist()

    arestas_l, bboxes = prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

    fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)


def indexedFaceSet(coord: list[float], coordIndex: list[int], colorPerVertex: bool,
                   color: list[float], colorIndex: list[int],
                   texCoord: list[float], texCoordIndex: list[int],
                   colors: Colors, current_texture: list[str]) -> None:
    """
    Renderiza IndexedFaceSet: Uma malha de faces poligonais indexadas.

    Cada face (delimitada por -1 em `coordIndex`) é triangulada em leque
    a partir do seu primeiro vértice. Descarta (back-face culling) os
    triângulos de costas para a câmera antes de rasterizar, seguindo a
    convenção anti-horária do projeto.

    Prioridade de preenchimento (mutuamente exclusivas, como no X3D):
    textura (se `current_texture` e `texCoord` estiverem presentes) >
    cor por vértice/face (se `color` estiver presente, respeitando
    `colorPerVertex`) > `colors["emissiveColor"]` flat, como fallback.

    Parameters
    ----------
    coord : list[float]
        Coordenadas dos vértices no formato [x0, y0, z0, x1, y1, z1, ...],
        em coordenadas de objeto.
    coordIndex : list[int]
        Índices de vértice (em `coord`) que formam as faces, na ordem em
        que devem ser conectados. O valor -1 separa uma face da próxima.
    colorPerVertex : bool
        Se True (e `color` não vazio), cada vértice da face tem sua
        própria cor, interpolada pelo triângulo (Gouraud shading). Se
        False, cada face inteira recebe uma única cor.
    color : list[float]
        Cores no formato [r0, g0, b0, r1, g1, b1, ...]; o que cada cor
        indexa (vértice ou face) depende de `colorPerVertex`.
    colorIndex : list[int]
        Índices de cor (em `color`). Se `colorPerVertex` for True, mesmo
        formato de `coordIndex` (um índice por vértice de face, -1
        separando faces); se vazio, usa-se `coordIndex` no lugar. Se
        `colorPerVertex` for False, um índice por face (sem -1); se
        vazio, usa-se a própria ordem das faces (a i-ésima face usa a
        i-ésima cor).
    texCoord : list[float]
        Coordenadas de textura por vértice no formato [u0, v0, u1, v1, ...].
    texCoordIndex : list[int]
        Índices de coordenada de textura (em `texCoord`) por vértice das
        faces, mesmo formato de `coordIndex`; se vazio, usa-se
        `coordIndex` no lugar.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó. Usa-se
        `colors["emissiveColor"]` como cor de preenchimento quando não há
        textura nem `color` por vértice/face.
    current_texture : list[str]
        Caminho(s) da textura atual do Appearance, se houver. Usa-se
        apenas o primeiro.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    tela_x, tela_y, tela_w, tela_z = project_points(coord)

    i0, i1, i2, face_id = fan_triangulate_cached(coordIndex)

    if i0.size == 0:
        return

    # Back-Face Culling: descarta triângulos de costas para a câmera antes de rasterizar.
    frente = front_facing_mask(tela_x, tela_y, i0, i1, i2)
    i0, i1, i2, face_id = i0[frente], i1[frente], i2[frente], face_id[frente]

    if i0.size == 0:
        return

    verts: list[VerticeProjetado] = list(
        zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
    idx0: list[int] = i0.tolist()
    idx1: list[int] = i1.tolist()
    idx2: list[int] = i2.tolist()
    alpha = 1.0 - colors["transparency"]

    arestas_l, bboxes = prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

    # Prioridade de preenchimento (mutuamente exclusivas, como no X3D):
    # textura > cor por vértice/face > colors["emissiveColor"] flat.
    # Cada tentativa devolve False (e cai para a próxima prioridade) se
    # a topologia do índice correspondente não bater com a de
    # coordIndex, exigido pela spec X3D mas verificado aqui por
    # segurança.
    if fill_face_set_textured(idx0, idx1, idx2, verts, frente, arestas_l, bboxes,
                                  texCoord, texCoordIndex, coordIndex,
                                  current_texture, alpha):
        return

    if color:
        if colorPerVertex:
            if fill_face_set_color_per_vertex(idx0, idx1, idx2, verts, frente,
                                                   color, colorIndex, coordIndex,
                                                   arestas_l, bboxes, alpha):
                return
        else:
            fill_face_set_color_per_face(idx0, idx1, idx2, verts, face_id,
                                             color, colorIndex, arestas_l, bboxes, alpha)
            return

    fill_triangles(coord, verts, i0, i1, i2, arestas_l, bboxes, colors)
