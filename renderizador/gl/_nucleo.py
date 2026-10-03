#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# pylint: disable=invalid-name

"""
Biblioteca Gráfica / Graphics Library.

Desenvolvido por: Lucas Hix
Disciplina: Computação Gráfica
Data: 19/08/2026
"""

import math
from typing import ClassVar

import numpy as np
import numpy.typing as npt

from ._animacao import orientationInterpolator, splinePositionInterpolator, timeSensor
from ._arestas import prepare_edges_and_bbox
from ._constantes import SEGMENTOS
from ._cores import piso, to_rgb8
from ._estado import estado
from ._framebuffer import clear, resolve_multisample, setup
from ._malhas import box_mesh, cached_mesh, cap_mesh, join_meshes, side_mesh, sphere_mesh
from ._matrizes import perspective_matrix, rotation_matrix, scale_matrix, translation_matrix
from ._primitivas2d import draw_points, draw_points_blend, line_points
from ._projecao import front_facing_mask, project_points, to_world
from ._texturas import get_texture_mipmaps, optional_mipmaps
from ._tipos import Colors, Malha, Textura, VerticeProjetado
from ._triangulacao import fan_triangulate_cached, strip_triangle_indices
from ._varredura import (
    scan_triangle,
    scan_triangle_color,
    scan_triangle_depth,
    scan_triangle_lit,
    scan_triangle_textured,
)


class GL:
    """
    Classe que representa a biblioteca gráfica (Graphics Library).
    """

    # Matrizes de reflexão e rotação usadas para gerar
    # os 8 octantes simétricos de um círculo a partir de um único octante calculado.
    _CIRCLE_OCTANT_REFLECTIONS: ClassVar[npt.NDArray[np.float64]] = np.array([
        [[1, 0], [0, 1]], [[0, 1], [1, 0]],
        [[0, -1], [1, 0]], [[-1, 0], [0, 1]],
        [[-1, 0], [0, -1]], [[0, -1], [-1, 0]],
        [[0, 1], [-1, 0]], [[1, 0], [0, -1]],
    ], dtype=np.float64)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        all_points = np.concatenate([octant @ m.T for m in GL._CIRCLE_OCTANT_REFLECTIONS])

        draw_points(all_points[:, 0].astype(np.int64), all_points[:, 1].astype(np.int64), cor)

    @staticmethod
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

    @staticmethod
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

        GL._fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)

    @staticmethod
    def viewpoint(position: list[float], orientation: list[float], fieldOfView: float) -> None:
        """
        Processa um nó Viewpoint, calculando as matrizes de view e projeção.

        Parameters
        ----------
        position : list[float]
            Posição [x, y, z] da câmera no espaço do mundo.
        orientation : list[float]
            Orientação da câmera no formato [x, y, z, t]: eixo de rotação
            [x, y, z] e ângulo t em radianos, seguindo a regra da mão direita.
        fieldOfView : float
            Campo de visão da câmera, em radianos, aplicado à menor dimensão
            da tela (a maior recebe um ângulo ajustado pela razão de aspecto).

        Returns
        -------
        None
            Atualiza estado.view_matrix e estado.perspective_matrix; não há retorno.
        """
        # Matriz de transformação da câmera (câmera -> mundo): rotação seguida de translação.
        camera_para_mundo = translation_matrix(position) @ rotation_matrix(orientation)

        # A view é a inversa: para uma matriz de rotação + translação, a inversa é a
        # transposta do bloco de rotação seguida da translação negada.
        estado.view_matrix = np.linalg.inv(camera_para_mundo)
        estado.camera_position = np.asarray(position, dtype=np.float64)

        aspect = estado.width / estado.height

        # O fieldOfView do X3D se aplica à menor dimensão da tela sem alteração; a maior
        # dimensão recebe o ângulo mais largo, calculado a partir da razão de aspecto.
        if aspect > 1:  # tela mais larga que alta: a vertical (menor) recebe o fov cru
            fovy = fieldOfView
        else:  # tela mais alta que larga: a horizontal (menor) recebe o fov cru
            fovy = 2 * math.atan(math.tan(fieldOfView / 2) / aspect)

        estado.perspective_matrix = perspective_matrix(fovy, aspect, estado.near, estado.far)

    @staticmethod
    def transform_in(translation: list[float], scale: list[float], rotation: list[float]) -> None:
        """
        Entra num nó Transform: empilha a matriz de transformação acumulada.

        Chamada ao entrar num nó X3D do tipo Transform do grafo de cena.
        Quando se usa Transforms dentro de outros Transforms, a matriz
        corrente acumula sobre o topo da pilha, que guarda a transformação do
        Transform ancestral.

        Parameters
        ----------
        translation : list[float]
            Translação [x, y, z] do Transform. Lista vazia equivale a
            nenhuma translação.
        scale : list[float]
            Escala [x, y, z] do Transform, um fator por eixo. Lista vazia
            equivale a escala unitária (1, 1, 1).
        rotation : list[float]
            Rotação no formato [x, y, z, t]: eixo [x, y, z] e ângulo t em
            radianos, seguindo a regra da mão direita. Lista vazia equivale a
            nenhuma rotação.

        Returns
        -------
        None
            Empilha a matriz resultante em estado.transform_stack.
        """
        t = translation if translation else [0.0, 0.0, 0.0]
        s = scale if scale else [1.0, 1.0, 1.0]
        r = rotation if rotation else [0.0, 0.0, 1.0, 0.0]

        # Ordem de aplicação em um ponto local: primeiro escala, depois rotação,
        # depois translação — ou seja, local_para_pai = T @ R @ S.
        local_para_pai = translation_matrix(t) @ rotation_matrix(r) @ scale_matrix(s)

        local_para_mundo = estado.transform_stack[-1] @ local_para_pai
        estado.transform_stack.append(local_para_mundo)

    @staticmethod
    def transform_out() -> None:
        """
        Sai de um nó Transform: desempilha a matriz de transformação corrente.

        Chamada ao sair de um nó X3D do tipo Transform do grafo de cena, para
        recuperar a matriz de transformação do Transform ancestral.

        Returns
        -------
        None
            Remove o topo de estado.transform_stack.
        """
        estado.transform_stack.pop()

    @staticmethod
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

        GL._fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)

    @staticmethod
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

        GL._fill_triangles(point, verts, i0, i1, i2, arestas_l, bboxes, colors)

    @staticmethod
    def _fill_face_set_textured(idx0: list[int], idx1: list[int], idx2: list[int],
                                verts: list[VerticeProjetado], frente: npt.NDArray[np.bool_],
                                arestas_l: list[npt.NDArray[np.float64] | None],
                                bboxes: list[tuple[int, int, int, int] | None],
                                texCoord: list[float], texCoordIndex: list[int],
                                coordIndex: list[int], current_texture: list[str],
                                alpha: float) -> bool:
        """
        Tenta preencher as faces de um IndexedFaceSet com textura.

        Extraído de `GL.indexedFaceSet` para reduzir sua complexidade
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

    @staticmethod
    def _fill_face_set_color_per_vertex(idx0: list[int], idx1: list[int], idx2: list[int],
                                        verts: list[VerticeProjetado],
                                        frente: npt.NDArray[np.bool_], color: list[float],
                                        colorIndex: list[int], coordIndex: list[int],
                                        arestas_l: list[npt.NDArray[np.float64] | None],
                                        bboxes: list[tuple[int, int, int, int] | None],
                                        alpha: float) -> bool:
        """
        Tenta preencher as faces de um IndexedFaceSet com cor por vértice (Gouraud).

        Extraído de `GL.indexedFaceSet` pelo mesmo motivo de
        `GL._fill_face_set_textured`: isola o teste de topologia de
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

        # Mesmo motivo do zip duplo em GL._fill_face_set_textured.
        for t, ((a, b, c), (ca, cb, cc)) in enumerate(zip(zip(idx0, idx1, idx2),
                                                           zip(cor0, cor1, cor2))):
            scan_triangle_color(verts[a], ca, verts[b], cb, verts[c], cc,
                                    arestas_l[t], bboxes[t], alpha)

        return True

    @staticmethod
    def _fill_face_set_color_per_face(idx0: list[int], idx1: list[int], idx2: list[int],
                                      verts: list[VerticeProjetado],
                                      face_id: npt.NDArray[np.int64], color: list[float],
                                      colorIndex: list[int],
                                      arestas_l: list[npt.NDArray[np.float64] | None],
                                      bboxes: list[tuple[int, int, int, int] | None],
                                      alpha: float) -> None:
        """
        Preenche as faces de um IndexedFaceSet com uma cor sólida por face inteira.

        Extraído de `GL.indexedFaceSet` pelo mesmo motivo de
        `GL._fill_face_set_textured`. Ao contrário da variante por vértice,
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

    @staticmethod
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
        if GL._fill_face_set_textured(idx0, idx1, idx2, verts, frente, arestas_l, bboxes,
                                      texCoord, texCoordIndex, coordIndex,
                                      current_texture, alpha):
            return

        if color:
            if colorPerVertex:
                if GL._fill_face_set_color_per_vertex(idx0, idx1, idx2, verts, frente,
                                                       color, colorIndex, coordIndex,
                                                       arestas_l, bboxes, alpha):
                    return
            else:
                GL._fill_face_set_color_per_face(idx0, idx1, idx2, verts, face_id,
                                                 color, colorIndex, arestas_l, bboxes, alpha)
                return

        GL._fill_triangles(coord, verts, i0, i1, i2, arestas_l, bboxes, colors)

    @staticmethod
    def _fill_triangles(posicoes: npt.ArrayLike, verts: list[VerticeProjetado],
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
            GL._fill_lit(posicoes, verts, (i0, i1, i2), arestas_l, bboxes, colors,
                         normais, textura)
        else:
            GL._fill_unlit(verts, (i0, i1, i2), arestas_l, bboxes, colors, textura)

    @staticmethod
    def _fill_unlit(verts: list[VerticeProjetado],
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

    @staticmethod
    def _fill_lit(posicoes: npt.ArrayLike, verts: list[VerticeProjetado],
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

        for t, (a, b, c) in enumerate(zip(idx0, idx1, idx2)):
            tex = (textura[0], textura[1][indices[t]]) if textura is not None else None
            scan_triangle_lit(verts[a], verts[b], verts[c], pos_tri[t], n_tri[t],
                                  arestas_l[t], bboxes[t], colors, alpha, tex)

    @staticmethod
    def _draw_mesh(malha: Malha, colors: Colors, mipmaps: list[npt.NDArray[np.uint8]] | None = None
                   ) -> None:
        """
        Projeta, descarta faces de costas e rasteriza uma malha de triângulos indexada.

        Caminho comum das primitivas (Box, Sphere, Cone e Cylinder): elas só
        geram a malha, e o resto do pipeline é o mesmo de `GL.triangleSet`.
        Sem luzes ativas, preenche com `colors["emissiveColor"]` (flat). Com
        luzes, sombreia por subamostra com as normais interpoladas (Phong
        shading, ver `GL._fill_triangles`).

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
        GL._fill_triangles(posicoes, verts, i0, i1, i2, arestas_l, bboxes, colors, normais,
                           textura)

    @staticmethod
    def box(size: list[float], colors: Colors, current_texture: list[str] | None = None
            ) -> None:
        """
        Renderiza Box: um paralelepípedo centrado na origem local.

        Parameters
        ----------
        size : list[float]
            Extensões da caixa [x, y, z] ao longo dos eixos locais; cada
            valor deve ser maior que zero.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.
        current_texture : list[str] or None, optional
            Caminho(s) da textura atual do Appearance, se houver. Cada face
            mostra a textura inteira, com U para a direita e V para cima
            vistos de fora (mapeamento X3D do Box).

        Returns
        -------
        None
            A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
            retorno.
        """
        x, y, z = size
        malha = cached_mesh(("box", x, y, z), lambda: box_mesh((x, y, z)))
        GL._draw_mesh(malha, colors, optional_mipmaps(current_texture))

    @staticmethod
    def sphere(radius: float, colors: Colors, current_texture: list[str] | None = None) -> None:
        """
        Renderiza Sphere: uma esfera centrada na origem local.

        Parameters
        ----------
        radius : float
            Raio da esfera.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.
        current_texture : list[str] or None, optional
            Caminho(s) da textura atual do Appearance, se houver.
            A textura dá a volta na esfera, com a costura no
            fundo (-Z) e v = 1 no polo norte.

        Returns
        -------
        None
            A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
            retorno.
        """
        malha = cached_mesh(("sphere", radius), lambda: sphere_mesh(radius))
        GL._draw_mesh(malha, colors, optional_mipmaps(current_texture))

    @staticmethod
    def cone(bottomRadius: float, height: float, colors: Colors,
             current_texture: list[str] | None = None) -> None:
        """
        Renderiza Cone: um cone centrado na origem local, alinhado ao eixo Y.

        O vértice fica em +height/2 e a base (fechada) em -height/2.

        Parameters
        ----------
        bottomRadius : float
            Raio da base do cone.
        height : float
            Altura do cone.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.
        current_texture : list[str] or None, optional
            Caminho(s) da textura atual do Appearance, se houver.
            A lateral dá a volta no cone (v = 1 no vértice) e a
            base mostra um recorte circular da textura.

        Returns
        -------
        None
            A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
            retorno.
        """
        def construir() -> Malha:
            lateral = side_mesh(0.0, bottomRadius, height, SEGMENTOS, bottomRadius)
            tampa = cap_mesh(bottomRadius, -height / 2, -1.0, SEGMENTOS, 0)
            return join_meshes([lateral, tampa])

        malha = cached_mesh(("cone", bottomRadius, height), construir)
        GL._draw_mesh(malha, colors, optional_mipmaps(current_texture))

    @staticmethod
    def cylinder(radius: float, height: float, colors: Colors,
                 current_texture: list[str] | None = None) -> None:
        """
        Renderiza Cylinder: um cilindro centrado na origem local, alinhado ao eixo Y.

        Fechado nas duas extremidades.

        Parameters
        ----------
        radius : float
            Raio da base do cilindro.
        height : float
            Altura do cilindro.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.
        current_texture : list[str] or None, optional
            Caminho(s) da textura atual do Appearance, se houver.
            A lateral dá a volta no cilindro e as tampas mostram
            um recorte circular da textura.

        Returns
        -------
        None
            A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
            retorno.
        """
        def construir() -> Malha:
            lateral = side_mesh(radius, radius, height, SEGMENTOS, 0.0)
            topo = cap_mesh(radius, height / 2, 1.0, SEGMENTOS, 0)
            baixo = cap_mesh(radius, -height / 2, -1.0, SEGMENTOS, 0)
            return join_meshes([lateral, topo, baixo])

        malha = cached_mesh(("cylinder", radius, height), construir)
        GL._draw_mesh(malha, colors, optional_mipmaps(current_texture))

    @staticmethod
    def navigationInfo(headlight: bool) -> None:
        """
        Processa NavigationInfo: características do avatar e do modo de visualização.

        Com `headlight` ligado, acrescenta às luzes do frame uma luz direcional
        branca presa à câmera. Deve ser chamada depois de `GL.viewpoint`.

        Parameters
        ----------
        headlight : bool
            Se True, o visualizador deve acender uma luz direcional que
            sempre aponta na direção em que o usuário está olhando.

        Returns
        -------
        None
            Acrescenta a luz da câmera a estado.lights quando `headlight` é True;
            não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/navigation.html#NavigationInfo
        # O campo do headlight especifica se um navegador deve acender um luz direcional que
        # sempre aponta na direção que o usuário está olhando. Definir este campo como TRUE
        # faz com que o visualizador forneça sempre uma luz do ponto de vista do usuário.
        # A luz headlight deve ser direcional, ter intensidade = 1, cor = (1 1 1),
        # ambientIntensity = 0,0 e direção = (0 0 −1).

        if headlight:
            # A direção (0, 0, -1) do headlight está no espaço da câmera; a rotação
            # da view é ortogonal, então a inversa dela (camera -> mundo) é a transposta.
            direcao = estado.view_matrix[:3, :3].T @ np.array([0.0, 0.0, -1.0])
            estado.lights.append({"direcao": direcao, "cor": np.ones(3),
                              "intensidade": 1.0, "ambiente": 0.0})

    @staticmethod
    def directionalLight(ambientIntensity: float, color: list[float], intensity: float,
                         direction: list[float]) -> None:
        """
        Processa DirectionalLight: uma luz direcional (raios paralelos).

        A direção é levada ao espaço de mundo pela transformação corrente, de
        modo que luzes dentro de um Transform giram com ele.

        Parameters
        ----------
        ambientIntensity : float
            Contribuição de luz ambiente da fonte, em [0, 1].
        color : list[float]
            Cor da luz [r, g, b], cada canal em [0, 1].
        intensity : float
            Intensidade (brilho) da luz.
        direction : list[float]
            Vetor de direção [x, y, z] da luz, no sistema de coordenadas
            local.

        Returns
        -------
        None
            Acrescenta a luz a estado.lights; não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#DirectionalLight
        # Define uma fonte de luz direcional que ilumina ao longo de raios paralelos
        # em um determinado vetor tridimensional. Possui os campos básicos ambientIntensity,
        # cor, intensidade. O campo de direção especifica o vetor de direção da iluminação
        # que emana da fonte de luz no sistema de coordenadas local. A luz é emitida ao
        # longo de raios paralelos de uma distância infinita.

        _, direcao = to_world(np.zeros((1, 3)), np.array([direction], dtype=np.float64))
        assert direcao is not None
        estado.lights.append({"direcao": direcao[0], "cor": np.asarray(color, dtype=np.float64),
                          "intensidade": intensity, "ambiente": ambientIntensity})

    @staticmethod
    def pointLight(ambientIntensity: float, color: list[float], intensity: float,
                  location: list[float]) -> None:
        """
        Processa PointLight: uma luz pontual omnidirecional.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        ambientIntensity : float
            Contribuição de luz ambiente da fonte, em [0, 1].
        color : list[float]
            Cor da luz [r, g, b], cada canal em [0, 1].
        intensity : float
            Intensidade (brilho) da luz.
        location : list[float]
            Posição [x, y, z] da luz, no sistema de coordenadas local.

        Returns
        -------
        None
            Não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#PointLight
        # Fonte de luz pontual em um local 3D no sistema de coordenadas local. Uma fonte
        # de luz pontual emite luz igualmente em todas as direções; ou seja, é omnidirecional.
        # Possui os campos básicos ambientIntensity, cor, intensidade. Um nó PointLight ilumina
        # a geometria em um raio de sua localização. O campo do raio deve ser maior ou igual a
        # zero. A iluminação do nó PointLight diminui com a distância especificada.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("PointLight : ambientIntensity = {0}".format(ambientIntensity))
        print("PointLight : color = {0}".format(color)) # imprime no terminal
        print("PointLight : intensity = {0}".format(intensity)) # imprime no terminal
        print("PointLight : location = {0}".format(location)) # imprime no terminal

    @staticmethod
    def fog(visibilityRange: float, color: list[float]) -> None:
        """
        Processa Fog: névoa que mistura objetos distantes com uma cor constante.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        visibilityRange : float
            Distância, no sistema de coordenadas local, na qual os objetos
            ficam totalmente obscurecidos pela névoa.
        color : list[float]
            Cor da névoa [r, g, b], cada canal em [0, 1].

        Returns
        -------
        None
            Não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/environmentalEffects.html#Fog
        # O nó Fog fornece uma maneira de simular efeitos atmosféricos combinando objetos
        # com a cor especificada pelo campo de cores com base nas distâncias dos
        # vários objetos ao visualizador. A visibilidadeRange especifica a distância no
        # sistema de coordenadas local na qual os objetos são totalmente obscurecidos
        # pela névoa. Os objetos localizados fora de visibilityRange do visualizador são
        # desenhados com uma cor de cor constante. Objetos muito próximos do visualizador
        # são muito pouco misturados com a cor do nevoeiro.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Fog : color = {0}".format(color)) # imprime no terminal
        print("Fog : visibilityRange = {0}".format(visibilityRange))

    # Para o futuro (Não para versão atual do projeto.)
    def vertex_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um vertex shader.

        Parameters
        ----------
        shader : str
            Código-fonte do vertex shader.

        Returns
        -------
        None
            Não implementado; não há retorno.
        """

    def fragment_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um fragment shader.

        Parameters
        ----------
        shader : str
            Código-fonte do fragment shader.

        Returns
        -------
        None
            Não implementado; não há retorno.
        """

    timeSensor = staticmethod(timeSensor)

    splinePositionInterpolator = staticmethod(splinePositionInterpolator)

    orientationInterpolator = staticmethod(orientationInterpolator)

    setup = staticmethod(setup)
    clear = staticmethod(clear)
    resolve_multisample = staticmethod(resolve_multisample)
