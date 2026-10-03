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

import gpu  # Simula os recursos de uma GPU
import numpy as np
import numpy.typing as npt

from ._animacao import orientationInterpolator, splinePositionInterpolator, timeSensor
from ._constantes import LOTE_MINIMO, MSAA_AMOSTRAS, SEGMENTOS
from ._cores import piso, to_rgb8
from ._estado import estado
from ._malhas import box_mesh, cached_mesh, cap_mesh, join_meshes, side_mesh, sphere_mesh
from ._matrizes import perspective_matrix, rotation_matrix, scale_matrix, translation_matrix
from ._texturas import get_texture_mipmaps, optional_mipmaps, sample_texture
from ._tipos import Colors, Malha, Textura, VerticeProjetado
from ._triangulacao import fan_triangulate_cached, strip_triangle_indices


class GL:
    """
    Classe que representa a biblioteca gráfica (Graphics Library).
    """

    @staticmethod
    def setup(width: int, height: int, near: float = 0.01, far: float = 1000) -> None:
        """
        Define parâmetros para câmera de razão de aspecto, plano próximo e distante.

        Parameters
        ----------
        width : int
            Largura da tela/framebuffer, em pixels.
        height : int
            Altura da tela/framebuffer, em pixels.
        near : float, optional
            Distância do plano de corte próximo da câmera, por padrão 0.01.
        far : float, optional
            Distância do plano de corte distante da câmera, por padrão 1000.

        Returns
        -------
        None
            Inicializa os atributos de classe da GL (matrizes, pilha de
            transformações, buffer de multisample); não há retorno.
        """
        estado.width = width
        estado.height = height
        estado.near = near
        estado.far = far
        estado.view_matrix = np.identity(4)
        estado.perspective_matrix = np.identity(4)
        estado.transform_stack = [np.identity(4)]
        estado.lights = []
        estado.camera_position = np.zeros(3)
        estado.t0 = estado.origem_fixa
        estado.ms_buffer = np.zeros(
            (height, width, MSAA_AMOSTRAS, MSAA_AMOSTRAS, 3), dtype=np.uint8)
        estado.depth_buffer = np.ones(
            (height, width, MSAA_AMOSTRAS, MSAA_AMOSTRAS), dtype=np.float64)

    @staticmethod
    def clear() -> None:
        """
        Limpa o frame atual: o FrameBuffer do GPU e os buffers internos da GL.

        Chama gpu.GPU.clear_buffer() e reinicia estado.ms_buffer com a mesma cor
        de limpeza e estado.depth_buffer com o plano far (1.0); ambos são
        conceitos internos da GL (a camada acima do GPU simulado), então não
        podem viver dentro de gpu.GPU.clear_buffer() sem inverter a
        dependência entre as camadas; centralizar as limpezas aqui mantém
        uma única chamada no início de cada frame.
        """
        gpu.GPU.clear_buffer()
        estado.ms_buffer[:] = gpu.GPU.clear_color_val
        estado.depth_buffer[:] = 1.0
        estado.lights = []

    @staticmethod
    def resolve_multisample() -> None:
        """
        Resolve o buffer de multisample no FrameBuffer de desenho atual do GPU.

        Faz a média das subamostras de cada pixel e escreve o resultado no
        FrameBuffer. Deve ser chamado uma vez no final de cada frame, depois
        que toda a cena já foi desenhada (equivalente ao "resolve pass" de um
        MSAA real).
        """
        resolvido = estado.ms_buffer.mean(axis=(2, 3))
        buffer_cor = gpu.GPU.frame_buffer[gpu.GPU.draw_framebuffer].color
        buffer_cor[:] = piso(resolvido).astype(np.uint8)

    # Matrizes de reflexão e rotação usadas para gerar
    # os 8 octantes simétricos de um círculo a partir de um único octante calculado.
    _CIRCLE_OCTANT_REFLECTIONS: ClassVar[npt.NDArray[np.float64]] = np.array([
        [[1, 0], [0, 1]], [[0, 1], [1, 0]],
        [[0, -1], [1, 0]], [[-1, 0], [0, 1]],
        [[-1, 0], [0, -1]], [[0, -1], [-1, 0]],
        [[0, 1], [-1, 0]], [[1, 0], [0, -1]],
    ], dtype=np.float64)

    @staticmethod
    def _draw_points(xs: npt.NDArray[np.int64], ys: npt.NDArray[np.int64],
                     cor: list[int] | npt.NDArray[np.int64]) -> None:
        """
        Desenha um conjunto de pixels, descartando os que caem fora da tela.

        Marca todas as subamostras MSAA do pixel com a cor (um ponto/pixel
        não tem noção de cobertura parcial nesse renderizador, então cobre o
        pixel inteiro).

        Parameters
        ----------
        xs : NDArray[int64]
            Coordenadas x (coluna) dos pixels a desenhar.
        ys : NDArray[int64]
            Coordenadas y (linha) dos pixels a desenhar, mesmo tamanho de `xs`.
        cor : list[int] or NDArray[int64]
            Cor RGB (0-255) a escrever em cada pixel.

        Returns
        -------
        None
            Escreve em estado.ms_buffer; não há retorno.
        """
        dentro = (xs >= 0) & (xs < estado.width) & (ys >= 0) & (ys < estado.height)
        estado.ms_buffer[ys[dentro], xs[dentro], :, :] = cor

    @staticmethod
    def _draw_points_blend(xs: npt.NDArray[np.int64], ys: npt.NDArray[np.int64],
                           cor: list[int] | npt.NDArray[np.int64],
                           cobertura: npt.NDArray[np.float64]) -> None:
        """
        Desenha um conjunto de pixels com cobertura parcial (anti-aliasing).

        Aplica apenas uma fração proporcional das subamostras MSAA no pixel com a cor.

        Usado para anti-aliasing analítico (Xiaolin Wu), que calcula uma
        cobertura contínua em [0, 1] por pixel, aqui ela é quantizada para o
        nível mais próximo representável pela grade de subamostras (a mesma
        limitação de qualquer MSAA real: um edge fica só com N/total níveis
        de cobertura possíveis, não um contínuo).

        Parameters
        ----------
        xs : NDArray[int64]
            Coordenadas x (coluna) dos pixels a desenhar.
        ys : NDArray[int64]
            Coordenadas y (linha) dos pixels a desenhar, mesmo tamanho de `xs`.
        cor : list[int] or NDArray[int64]
            Cor RGB (0-255) a escrever nas subamostras cobertas.
        cobertura : NDArray[float64]
            Opacidade de cada ponto em [0, 1], mesmo tamanho de `xs`. Pontos
            com cobertura <= 0 são descartados, junto dos que caem fora da
            tela.

        Returns
        -------
        None
            Escreve em estado.ms_buffer; não há retorno.
        """
        # Verifica quais pontos caem dentro da tela e têm cobertura positiva.
        dentro = ((xs >= 0) & (xs < estado.width) & (ys >= 0) & (ys < estado.height)
                  & (cobertura > 0))
        xs_d, ys_d, cov_d = xs[dentro], ys[dentro], cobertura[dentro]

        # Quantiza a cobertura contínua para a quantidade de subamostras a
        # cobrir, de 0 a total_amostras.
        total_amostras = MSAA_AMOSTRAS * MSAA_AMOSTRAS
        n_amostras = np.clip(piso(cov_d * total_amostras), 0, total_amostras).astype(np.int64)

        # Máscara booleana por ponto: quais das total_amostras subamostras
        # (as N primeiras, em ordem fixa) devem receber a cor.
        indices = np.arange(total_amostras)
        marcar = (indices[None, :] < n_amostras[:, None]).reshape(
            -1, MSAA_AMOSTRAS, MSAA_AMOSTRAS)
        
        atual = estado.ms_buffer[ys_d, xs_d]
        atual[marcar] = np.asarray(cor) # Aplica o MSAA
        estado.ms_buffer[ys_d, xs_d] = atual

    @staticmethod
    def _line_points(x0: float, y0: float, x1: float, y1: float
                     ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                npt.NDArray[np.float64]]:
        """
        Interpola os pontos de uma linha entre dois pontos, com anti-aliasing.

        Algoritmo de Xiaolin Wu, vetorizado com numpy: percorre o eixo
        dominante (o de maior variação) em passos inteiros e, para cada
        passo, calcula a posição exata (fracionária) da reta no eixo
        perpendicular. Como essa posição cai entre dois pixels, os dois
        recebem cobertura complementar, o mais próximo da reta com peso
        maior, em vez de arredondar para um único pixel "cheio" (o que
        produzia a borda em escada quando desenhado sem blending).

        Parameters
        ----------
        x0 : float
            Coordenada x do ponto inicial da reta, em coordenadas de tela.
        y0 : float
            Coordenada y do ponto inicial da reta, em coordenadas de tela.
        x1 : float
            Coordenada x do ponto final da reta, em coordenadas de tela.
        y1 : float
            Coordenada y do ponto final da reta, em coordenadas de tela.

        Returns
        -------
        NDArray[int64]
            Coordenadas x dos pixels tocados pela reta (dois por passo).
        NDArray[int64]
            Coordenadas y dos pixels tocados pela reta, mesmo tamanho do
            primeiro retorno.
        NDArray[float64]
            Cobertura (opacidade) de cada pixel em [0, 1], mesmo tamanho dos
            dois retornos anteriores.
        """
        dx = x1 - x0
        dy = y1 - y0
        steep = abs(dy) > abs(dx)

        if steep:
            x0, y0, x1, y1 = y0, x0, y1, x1
            dx, dy = dy, dx

        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
            dx, dy = -dx, -dy

        gradiente = dy / dx if dx != 0 else 0.0

        eixo = np.arange(math.floor(x0), math.floor(x1) + 1)
        y_exato = y0 + (eixo - x0) * gradiente

        y_piso = np.floor(y_exato)
        frac = y_exato - y_piso

        # Pixel principal (mais próximo da reta) e o secundário logo abaixo/à
        # direita, com cobertura complementar (1 - frac) e (frac).
        xs = np.concatenate([eixo, eixo])
        ys = np.concatenate([y_piso, y_piso + 1])
        cobertura = np.concatenate([1 - frac, frac])

        if steep:
            xs, ys = ys, xs

        return xs.astype(np.int64), ys.astype(np.int64), cobertura.astype(np.float64)

    @staticmethod
    def _scan_triangle(x0: float, y0: float, x1: float, y1: float,
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

    @staticmethod
    def _blend_write(ys: npt.NDArray[np.int64], xs: npt.NDArray[np.int64],
                     sy: npt.NDArray[np.int64], sx: npt.NDArray[np.int64],
                     cor: npt.NDArray[np.float64] | npt.NDArray[np.int64] | npt.NDArray[np.uint8],
                     alpha: float) -> None:
        """
        Escreve cor em estado.ms_buffer, misturando com o que já está lá se houver transparência.

        Implementa alpha blending (`estado.ms_buffer` = `cor` * `alpha` +
        `estado.ms_buffer` * `(1 - alpha)`) nas subamostras indicadas.
        `alpha` vem de `1 - transparency` do Material X3D: `transparency` 0
        é opaco (`alpha` 1) e 1 é totalmente transparente (`alpha` 0). Com
        `alpha >= 1.0` (caso comum, geometria opaca) pula a mistura e
        escreve `cor` direto, mesmo resultado sem o custo da conta.

        Parameters
        ----------
        ys, xs, sy, sx : NDArray[int64]
            Índices em `estado.ms_buffer` (linha, coluna, subamostra y,
            subamostra x) das subamostras a escrever, mesmo tamanho.
        cor : NDArray[float64], NDArray[int64] or NDArray[uint8]
            Cor RGB (0-255) a escrever, um único vetor (3,) para
            preenchimento flat, ou uma cor por subamostra (K, 3).
        alpha : float
            Opacidade em [0, 1] da geometria sendo desenhada.

        Returns
        -------
        None
            Escreve em estado.ms_buffer; não há retorno.
        """
        if alpha >= 1.0:
            estado.ms_buffer[ys, xs, sy, sx] = cor
            return

        fundo = estado.ms_buffer[ys, xs, sy, sx].astype(np.float64)
        frente = np.asarray(cor, dtype=np.float64)
        mistura = frente * alpha + fundo * (1 - alpha)
        estado.ms_buffer[ys, xs, sy, sx] = np.clip(piso(mistura), 0, 255).astype(np.uint8)

    @staticmethod
    def _batch_edges_and_bbox(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
                              i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                              i2: npt.NDArray[np.int64]
                              ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64],
                                         npt.NDArray[np.int64], npt.NDArray[np.int64],
                                         npt.NDArray[np.int64]]:
        """
        Pré-calcula os coeficientes de aresta e a bounding box de todos os T triângulos de uma vez.

        `GL._triangle_coverage` precisa dos coeficientes de aresta e da
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
            tamanho (tipicamente o retorno de `GL._project_points`).
        i0, i1, i2 : NDArray[int64]
            Índices do primeiro, segundo e terceiro vértice de cada
            triângulo, em `tela_x`/`tela_y`, mesmo tamanho T entre si.

        Returns
        -------
        NDArray[float64]
            `arestas`: coeficientes (dy, -dx, ay*dx - ax*dy) das 3 arestas
            de cada triângulo, array (T, 3, 3), na mesma ordem usada por
            `GL._triangle_coverage` (edge0 = v0->v1, edge1 = v1->v2,
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

    @staticmethod
    def _prepare_edges_and_bbox(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
                                i0: npt.NDArray[np.int64], i1: npt.NDArray[np.int64],
                                i2: npt.NDArray[np.int64]
                                ) -> tuple[list[npt.NDArray[np.float64] | None],
                                           list[tuple[int, int, int, int] | None]]:
        """
        Decide se compensa pré-calcular arestas/bbox em lote para um draw call.

        `GL._batch_edges_and_bbox` tem um custo fixo por chamada (montar os
        arrays `(T, 3)`/`(T, 3, 3)`, fazer os `roll`, converter os arrays de
        bbox para listas Python) que só compensa quando amortizado sobre
        vários triângulos: para um draw call com poucos triângulos (ex: um
        `TriangleSet` de um triângulo só, comum em cenas com muitos objetos
        pequenos separados), esse custo fixo é maior que simplesmente deixar
        `GL._triangle_coverage` calcular a aresta/bbox daquele único
        triângulo inline, como fazia antes da vetorização em lote existir.
        Por isso, abaixo de `LOTE_MINIMO` triângulos, devolve listas de
        `None`: `GL._triangle_coverage` recebe `None` em `arestas`/`bbox` e
        calcula os dois na hora, por triângulo, sem o overhead da
        vetorização em lote.

        Parameters
        ----------
        tela_x, tela_y : NDArray[float64]
            Coordenadas de tela de todos os vértices envolvidos, mesmo
            tamanho (tipicamente o retorno de `GL._project_points`).
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

        arestas_t, min_x, max_x, min_y, max_y = GL._batch_edges_and_bbox(tela_x, tela_y, i0, i1, i2)
        arestas_l: list[npt.NDArray[np.float64] | None] = list(arestas_t)
        bboxes: list[tuple[int, int, int, int] | None] = list(
            zip(min_x.tolist(), max_x.tolist(), min_y.tolist(), max_y.tolist()))

        return arestas_l, bboxes

    @staticmethod
    def _scan_triangle_depth(v0: VerticeProjetado, v1: VerticeProjetado,
                             v2: VerticeProjetado, arestas: npt.NDArray[np.float64] | None,
                             bbox: tuple[int, int, int, int] | None, cor: npt.NDArray[np.int64],
                             alpha: float = 1.0) -> None:
        """
        Varre um triângulo 3D com preenchimento flat, testando o z-buffer.

        Equivalente a `GL._scan_triangle`, mas para geometria 3D já
        projetada: usa `GL._triangle_coverage` para descartar (e não
        escrever) as subamostras encobertas por geometria mais perto da
        câmera já desenhada no frame, o que corrige a oclusão entre
        triângulos de objetos diferentes que se cruzam no espaço (sem
        z-buffer, a oclusão dependeria só da ordem de desenho no grafo de
        cena, painter's algorithm implícito e incorreto para geometria que
        se cruza). `alpha` < 1 mistura a cor com o que já está no buffer em
        vez de sobrescrever (ver `GL._blend_write`), e não atualiza o
        z-buffer (ver `GL._triangle_coverage`), para que geometria
        transparente não esconda o que está atrás dela de outra geometria
        transparente desenhada depois.

        Parameters
        ----------
        v0, v1, v2 : VerticeProjetado
            Vértices do triângulo (nessa ordem), cada um uma tupla
            (x, y, w, z) em coordenadas de tela, com w o componente w do
            espaço de clip e z o componente z de NDC, ambos devolvidos por
            `GL._project_points`.
        arestas : NDArray[float64] or None
            Coeficientes de aresta do triângulo, array (3, 3), devolvido
            por `GL._batch_edges_and_bbox`, ou None (ver
            `GL._prepare_edges_and_bbox`).
        bbox : tuple[int, int, int, int] or None
            Bounding box do triângulo em pixels de tela: (min_x, max_x,
            min_y, max_y), devolvida por `GL._batch_edges_and_bbox`, ou
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
        cobertura = GL._triangle_coverage(v0, v1, v2, arestas, bbox,
                                          escreve_profundidade=alpha >= 1.0)

        if cobertura is None:
            return

        ys, xs, sy, sx, _ = cobertura
        GL._blend_write(ys, xs, sy, sx, cor, alpha)

    @staticmethod
    def _triangle_coverage(v0: VerticeProjetado, v1: VerticeProjetado, v2: VerticeProjetado,
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
        `GL._batch_edges_and_bbox`), vetorizado em vez de recomputado a cada
        chamada desta função dentro do laço por triângulo (ver documento de
        rasterização por função de aresta). Para draw calls pequenos, onde
        esse pré-cálculo em lote não compensa (ver
        `GL._prepare_edges_and_bbox`), `arestas`/`bbox` chegam como `None` e
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
        `GL._project_points`) e comparada com `estado.depth_buffer`. Só as
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
            `GL._project_points`.
        arestas : NDArray[float64] or None
            Coeficientes (dy, -dx, ay*dx - ax*dy) das 3 arestas do
            triângulo, array (3, 3), devolvido por
            `GL._batch_edges_and_bbox` para o triângulo em questão, ou
            `None` para calcular na hora (ver `GL._prepare_edges_and_bbox`).
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

    @staticmethod
    def _scan_triangle_color(v0: VerticeProjetado, cor0: npt.NDArray[np.float64],
                             v1: VerticeProjetado, cor1: npt.NDArray[np.float64],
                             v2: VerticeProjetado, cor2: npt.NDArray[np.float64],
                             arestas: npt.NDArray[np.float64] | None,
                             bbox: tuple[int, int, int, int] | None,
                             alpha: float = 1.0
                             ) -> None:
        """
        Varre um triângulo 2D com cor interpolada por vértice (Gouraud shading).

        A interpolação é corrigida pela perspectiva (ver `GL._triangle_coverage`):
        sem essa correção, um vértice muito mais distante que os outros dois
        puxaria a cor para perto de si numa fração maior da área em tela do
        que deveria, porque a área em tela por si só não reflete a
        profundidade real do ponto na câmera. `GL._triangle_coverage` também
        faz o teste de z-buffer, então subamostras encobertas por geometria
        já desenhada mais perto da câmera não são escritas aqui. `alpha` < 1
        mistura a cor com o que já está no buffer em vez de sobrescrever
        (ver `GL._blend_write`) e não atualiza o z-buffer.

        Parameters
        ----------
        v0, v1, v2 : VerticeProjetado
            Vértices do triângulo (nessa ordem), cada um uma tupla
            (x, y, w, z) em coordenadas de tela, devolvida por
            `GL._project_points`.
        cor0, cor1, cor2 : NDArray[float64]
            Cor de cada vértice (na mesma ordem), no formato X3D [r, g, b]
            com cada canal em [0, 1].
        arestas : NDArray[float64] or None
            Coeficientes de aresta do triângulo, array (3, 3), devolvido
            por `GL._batch_edges_and_bbox`, ou None (ver
            `GL._prepare_edges_and_bbox`).
        bbox : tuple[int, int, int, int] or None
            Bounding box do triângulo em pixels de tela, devolvida por
            `GL._batch_edges_and_bbox`, ou None junto com arestas=None.
        alpha : float, optional
            Opacidade da geometria em [0, 1] (`1 - transparency` do
            Material X3D), por padrão 1.0 (opaco).

        Returns
        -------
        None
            Escreve em estado.ms_buffer; não há retorno.
        """
        cobertura = GL._triangle_coverage(v0, v1, v2, arestas, bbox,
                                          escreve_profundidade=alpha >= 1.0)

        if cobertura is None:
            return

        ys, xs, sy, sx, pesos = cobertura

        cor = (pesos[0][:, None] * cor0 + pesos[1][:, None] * cor1
               + pesos[2][:, None] * cor2)
        cor_rgb8 = np.clip(piso(cor * 255), 0, 255).astype(np.uint8)

        GL._blend_write(ys, xs, sy, sx, cor_rgb8, alpha)

    @staticmethod
    def _scan_triangle_textured(v0: VerticeProjetado, uv0: npt.NDArray[np.float64],
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
        corrigida pela perspectiva (ver `GL._triangle_coverage`), senão a
        textura distorce em superfícies inclinadas em relação à câmera.
        `GL._triangle_coverage` também faz o teste de z-buffer, então
        subamostras encobertas por geometria já desenhada mais perto da
        câmera não são escritas aqui. `alpha` < 1 mistura a cor com o que já
        está no buffer em vez de sobrescrever (ver `GL._blend_write`) e não
        atualiza o z-buffer.

        Parameters
        ----------
        v0, v1, v2 : VerticeProjetado
            Vértices do triângulo (nessa ordem), cada um uma tupla
            (x, y, w, z) em coordenadas de tela, devolvida por
            `GL._project_points`.
        uv0, uv1, uv2 : NDArray[float64]
            Coordenada de textura [u, v] de cada vértice (na mesma ordem).
        mipmaps : list[NDArray[uint8]]
            Cadeia de mipmaps da textura, do nível 0 (original) ao 1x1,
            no formato devolvido por `get_texture_mipmaps` (cada nível
            com eixos [u][v], como `gpu.GPU.load_texture`).
        arestas : NDArray[float64] or None
            Coeficientes de aresta do triângulo, array (3, 3), devolvido
            por `GL._batch_edges_and_bbox`, ou None (ver
            `GL._prepare_edges_and_bbox`).
        bbox : tuple[int, int, int, int] or None
            Bounding box do triângulo em pixels de tela, devolvida por
            `GL._batch_edges_and_bbox`, ou None junto com arestas=None.
        alpha : float, optional
            Opacidade da geometria em [0, 1] (`1 - transparency` do
            Material X3D), por padrão 1.0 (opaco).

        Returns
        -------
        None
            Escreve em estado.ms_buffer; não há retorno.
        """
        cobertura = GL._triangle_coverage(v0, v1, v2, arestas, bbox,
                                          escreve_profundidade=alpha >= 1.0)

        if cobertura is None:
            return

        ys, xs, sy, sx, pesos = cobertura

        cor = sample_texture(pesos, (v0, v1, v2), (uv0, uv1, uv2), mipmaps)

        GL._blend_write(ys, xs, sy, sx, cor, alpha)

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

        GL._draw_points(pontos[:, 0], pontos[:, 1], cor)

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
            xs, ys, cobertura = GL._line_points(x0, y0, x1, y1)
            GL._draw_points_blend(xs, ys, cor, cobertura)

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

        GL._draw_points(all_points[:, 0].astype(np.int64), all_points[:, 1].astype(np.int64), cor)

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

            GL._scan_triangle(vertices[i], vertices[i + 1],
                              vertices[i + 2], vertices[i + 3],
                              vertices[i + 4], vertices[i + 5], cor)

    @staticmethod
    def _project_points(point: list[float]
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
            no teste de z-buffer (ver `GL._triangle_coverage`): ao contrário
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

    @staticmethod
    def _front_facing_mask(tela_x: npt.NDArray[np.float64], tela_y: npt.NDArray[np.float64],
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
            tela (tipicamente o retorno de GL._project_points).
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
        tela_x, tela_y, tela_w, tela_z = GL._project_points(point)

        n_tri = len(tela_x) // 3
        i0 = np.arange(0, n_tri * 3, 3)
        i1, i2 = i0 + 1, i0 + 2

        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        verts: list[VerticeProjetado] = list(
            zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
        i0.tolist()
        i1.tolist()
        i2.tolist()

        arestas_l, bboxes = GL._prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

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
        tela_x, tela_y, tela_w, tela_z = GL._project_points(point)

        # Array contento a quantidade de vértices de cada tira
        counts = np.asarray(stripCount, dtype=np.int64)

        # Array contendo os offsets de cada tira (inicio + quantidade)
        offsets = np.concatenate(([0], np.cumsum(counts)))

        # Cria uma lista de arrays, cada um contendo os índices de vértices de uma tira
        tiras: list[npt.NDArray[np.int64]] = [
            np.arange(offsets[i], offsets[i + 1]) for i in range(len(counts))]

        i0, i1, i2 = strip_triangle_indices(tiras)

        # Back-Face Culling: descartar triângulos de costas para a câmera antes de rasterizar
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        verts: list[VerticeProjetado] = list(
            zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))

        i0.tolist()
        i1.tolist()
        i2.tolist()

        arestas_l, bboxes = GL._prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

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
        tela_x, tela_y, tela_w, tela_z = GL._project_points(point)

        idx = np.asarray(index, dtype=np.int64)
        # Divide em tiras nos pontos onde -1 aparece; cada segmento resultante,
        # exceto o primeiro, começa com o próprio -1 (removido pela máscara).
        cortes = np.nonzero(idx == -1)[0]
        tiras: list[npt.NDArray[np.int64]] = [
            segmento[segmento != -1] for segmento in np.split(idx, cortes)
        ]

        i0, i1, i2 = strip_triangle_indices(tiras)
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        verts: list[VerticeProjetado] = list(
            zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
        i0.tolist()
        i1.tolist()
        i2.tolist()

        arestas_l, bboxes = GL._prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

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
            `GL._project_points`), indexados por `idx0`/`idx1`/`idx2`.
        frente : NDArray[bool_]
            Máscara de back-face culling usada para os triângulos de
            `idx0`/`idx1`/`idx2`, para filtrar `texCoordIndex` na mesma
            topologia.
        arestas_l, bboxes : list
            Coeficientes de aresta e bounding box de cada triângulo de
            `idx0`/`idx1`/`idx2` (mesma ordem e tamanho), devolvidos por
            `GL._batch_edges_and_bbox` e já convertidos para lista.
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
            GL._scan_triangle_textured(verts[a], uva, verts[b], uvb, verts[c], uvc,
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
            `GL._batch_edges_and_bbox` e já convertidos para lista.
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
            GL._scan_triangle_color(verts[a], ca, verts[b], cb, verts[c], cc,
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
            `GL._batch_edges_and_bbox` e já convertidos para lista.
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
            GL._scan_triangle_depth(verts[a], verts[b], verts[c],
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
        tela_x, tela_y, tela_w, tela_z = GL._project_points(coord)

        i0, i1, i2, face_id = fan_triangulate_cached(coordIndex)

        if i0.size == 0:
            return

        # Back-Face Culling: descarta triângulos de costas para a câmera antes de rasterizar.
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2, face_id = i0[frente], i1[frente], i2[frente], face_id[frente]

        if i0.size == 0:
            return

        verts: list[VerticeProjetado] = list(
            zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
        idx0: list[int] = i0.tolist()
        idx1: list[int] = i1.tolist()
        idx2: list[int] = i2.tolist()
        alpha = 1.0 - colors["transparency"]

        arestas_l, bboxes = GL._prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)

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
    def _to_world(posicoes: npt.NDArray[np.float64], normais: npt.NDArray[np.float64] | None
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

    @staticmethod
    def _shade(pos: npt.NDArray[np.float64], normal: npt.NDArray[np.float64],
               colors: Colors, difusa: npt.NDArray[np.float64] | None = None
               ) -> npt.NDArray[np.float64]:
        r"""
        Calcula a cor iluminada de pontos de uma superfície (modelo de Phong).

        Para cada luz direcional ativa, com $L$ apontando para a luz, $V$
        para a câmera e $H$ o vetor intermediário entre eles:

        $$
        C = E + \sum_L \Big[ a_L\, c_L\, k_a\, D
            + i_L\, c_L \big( D\,\max(N \cdot L, 0)
            + S\,\max(N \cdot H, 0)^{128 s} \big) \Big]
        $$

        em que $E$, $D$, $S$ e $s$ são a emissiva, a difusa, a especular e o
        `shininess` do material, e $k_a$ o seu `ambientIntensity`. O
        termo especular só existe onde $N \cdot L > 0$. O resultado é
        recortado a [0, 1].

        Parameters
        ----------
        pos : NDArray[float64]
            Posições (N, 3) em coordenadas de mundo.
        normal : NDArray[float64]
            Normais unitárias (N, 3) em coordenadas de mundo.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.
        difusa : NDArray[float64] or None, optional
            Cor difusa (N, 3) de cada ponto, em [0, 1], no lugar de
            `colors["diffuseColor"]` (é assim que uma textura entra: ela
            substitui a difusa do material).

        Returns
        -------
        NDArray[float64]
            Cores (N, 3) com cada canal em [0, 1].
        """
        emissiva = np.asarray(colors["emissiveColor"], dtype=np.float64)
        resultado = np.tile(emissiva, (len(pos), 1))
        if not estado.lights:
            return resultado

        if difusa is None:
            difusa = np.asarray(colors["diffuseColor"], dtype=np.float64)
        especular = np.asarray(colors["specularColor"], dtype=np.float64)
        expoente = colors["shininess"] * 128.0
        para_camera = estado.camera_position - pos
        para_camera /= np.maximum(np.linalg.norm(para_camera, axis=1, keepdims=True), 1e-12)

        for luz in estado.lights:
            para_luz = -luz["direcao"]
            n_l = np.maximum(normal @ para_luz, 0.0)[:, None]
            meio = para_camera + para_luz
            meio /= np.maximum(np.linalg.norm(meio, axis=1, keepdims=True), 1e-12)
            n_h = np.maximum((normal * meio).sum(axis=1), 0.0)[:, None]
            brilho = np.where(n_l > 0, n_h ** expoente, 0.0)

            ambiente = luz["ambiente"] * colors["ambientIntensity"] * difusa
            direta = difusa * n_l + especular * brilho
            resultado += luz["cor"] * (ambiente + luz["intensidade"] * direta)

        return np.clip(resultado, 0.0, 1.0)

    @staticmethod
    def _scan_triangle_lit(v0: VerticeProjetado, v1: VerticeProjetado, v2: VerticeProjetado,
                           pos: npt.NDArray[np.float64], normal: npt.NDArray[np.float64],
                           arestas: npt.NDArray[np.float64] | None,
                           bbox: tuple[int, int, int, int] | None, colors: Colors,
                           alpha: float, textura: Textura | None = None) -> None:
        """
        Varre um triângulo calculando a iluminação em cada subamostra (Phong shading).

        Interpola a posição e a normal de mundo com os pesos
        perspectiva-corretos de `GL._triangle_coverage` e aplica `GL._shade`
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
            Coeficientes de aresta do triângulo (ver `GL._prepare_edges_and_bbox`).
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
        cobertura = GL._triangle_coverage(v0, v1, v2, arestas, bbox,
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
        cor = GL._shade(pesos.T @ pos, n, colors, difusa)
        cor_rgb8 = np.clip(piso(cor * 255), 0, 255).astype(np.uint8)

        GL._blend_write(ys, xs, sy, sx, cor_rgb8, alpha)

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
        (`GL._scan_triangle_lit`), usando as normais por vértice se dadas e,
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
            Arestas de cada triângulo (ver `GL._prepare_edges_and_bbox`).
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
                GL._scan_triangle_textured(verts[a], uv[a], verts[b], uv[b], verts[c], uv[c],
                                           mipmaps, arestas_l[t], bboxes[t], alpha)
            return

        cor = to_rgb8(colors["emissiveColor"])
        for t, (a, b, c) in enumerate(zip(idx0, idx1, idx2)):
            GL._scan_triangle_depth(verts[a], verts[b], verts[c],
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

        mundo, n_mundo = GL._to_world(np.asarray(posicoes, dtype=np.float64).reshape(-1, 3),
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
            GL._scan_triangle_lit(verts[a], verts[b], verts[c], pos_tri[t], n_tri[t],
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
        tela_x, tela_y, tela_w, tela_z = GL._project_points(posicoes.ravel().tolist())

        i0, i1, i2 = triangulos[:, 0], triangulos[:, 1], triangulos[:, 2]
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        if i0.size == 0:
            return

        verts: list[VerticeProjetado] = list(
            zip(tela_x.tolist(), tela_y.tolist(), tela_w.tolist(), tela_z.tolist()))
        arestas_l, bboxes = GL._prepare_edges_and_bbox(tela_x, tela_y, i0, i1, i2)
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

        _, direcao = GL._to_world(np.zeros((1, 3)), np.array([direction], dtype=np.float64))
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
