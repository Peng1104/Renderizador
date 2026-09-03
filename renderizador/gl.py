#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# pylint: disable=invalid-name

"""
Biblioteca Gráfica / Graphics Library.

Desenvolvido por: Lucas Hix
Disciplina: Computação Gráfica
Data: 19/08/2026
"""

import math  # Funções matemáticas
import time  # Para operações com tempo
from typing import ClassVar, TypedDict

import gpu  # Simula os recursos de uma GPU
import numpy as np  # Biblioteca do Numpy
import numpy.typing as npt


class Colors(TypedDict):
    """
    Conjunto de cores resolvidas a partir de um nó Appearance/Material.
    """

    diffuseColor: list[float]
    emissiveColor: list[float]
    specularColor: list[float]
    shininess: float
    transparency: float
    ambientIntensity: float

class Pointo2D:
    """
    Classe que representa um ponto 2D.
    """

    x: int
    y: int

class GL:
    """
    Classe que representa a biblioteca gráfica (Graphics Library).
    """

    width: ClassVar[int]  # largura da tela
    height: ClassVar[int] # altura da tela
    near: ClassVar[float] # plano de corte próximo
    far: ClassVar[float]  # plano de corte distante

    # Matriz view (mundo -> câmera) e de projeção perspectiva (câmera -> clip),
    # calculadas em GL.viewpoint(). Identidade até que um Viewpoint seja lido.
    view_matrix: ClassVar[npt.NDArray[np.float64]]
    perspective_matrix: ClassVar[npt.NDArray[np.float64]]

    # Pilha de matrizes de transformação (objeto -> mundo). O topo (última posição)
    # é a matriz corrente, acumulada dos Transforms ancestrais no grafo de cena.
    transform_stack: ClassVar[list[npt.NDArray[np.float64]]]

    # 4x MSAA: grade de MSAA_AMOSTRAS x MSAA_AMOSTRAS subamostras por pixel (2x2=4).
    # ms_buffer guarda, para cada pixel e cada subamostra, a última cor escrita
    # nela (por ordem de desenho, como um MSAA de verdade faria com os
    # fragmentos que cobrem cada subamostra). O resolve (média das subamostras
    # de cada pixel) só acontece uma vez por frame, em GL.resolve_multisample(),
    # depois que toda a cena já foi desenhada, por isso o anti-aliasing não
    # sofre do problema de "blend duplicado" que geometria adjacente causaria
    # se cada primitivo misturasse sua cobertura parcial direto no framebuffer
    # final.
    MSAA_AMOSTRAS: ClassVar[int] = 2
    ms_buffer: ClassVar[npt.NDArray[np.uint8]]

    # Cache de texturas já carregadas (chave: caminho em current_texture), para
    # não reler o arquivo de imagem do disco a cada face que a usa.
    _texture_cache: ClassVar[dict[str, npt.NDArray[np.uint8]]] = {}

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
        GL.width = width
        GL.height = height
        GL.near = near
        GL.far = far
        GL.view_matrix = np.identity(4)
        GL.perspective_matrix = np.identity(4)
        GL.transform_stack = [np.identity(4)]
        GL.ms_buffer = np.zeros(
            (height, width, GL.MSAA_AMOSTRAS, GL.MSAA_AMOSTRAS, 3), dtype=np.uint8)

    @staticmethod
    def clear() -> None:
        """
        Limpa o frame atual: o FrameBuffer do GPU e o buffer de multisample da GL.

        Chama gpu.GPU.clear_buffer() e reinicia GL.ms_buffer com a mesma cor
        de limpeza, ms_buffer é um conceito interno da GL (a camada acima do
        GPU simulado), então não pode viver dentro de gpu.GPU.clear_buffer()
        sem inverter a dependência entre as camadas; centralizar as duas
        limpezas aqui mantém uma única chamada no início de cada frame.
        """
        gpu.GPU.clear_buffer()
        GL.ms_buffer[:] = gpu.GPU.clear_color_val

    @staticmethod
    def resolve_multisample() -> None:
        """
        Resolve o buffer de multisample no FrameBuffer de desenho atual do GPU.

        Faz a média das subamostras de cada pixel e escreve o resultado no
        FrameBuffer. Deve ser chamado uma vez no final de cada frame, depois
        que toda a cena já foi desenhada (equivalente ao "resolve pass" de um
        MSAA real).
        """
        resolvido = GL.ms_buffer.mean(axis=(2, 3))
        buffer_cor = gpu.GPU.frame_buffer[gpu.GPU.draw_framebuffer].color
        buffer_cor[:] = GL._round(resolvido).astype(np.uint8)

    @staticmethod
    def _translation_matrix(t: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de translação.

        Parameters
        ----------
        t : list[float]
            Vetor de translação [x, y, z].

        Returns
        -------
        NDArray[float64]
            Matriz 4x4 homogênea correspondente à translação `t`.
        """
        m = np.identity(4)
        m[:3, 3] = t
        return m

    @staticmethod
    def _scale_matrix(s: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de escala.

        Parameters
        ----------
        s : list[float]
            Fatores de escala [x, y, z], um por eixo.

        Returns
        -------
        NDArray[float64]
            Matriz 4x4 homogênea correspondente à escala `s`.
        """
        m = np.identity(4)
        m[0, 0], m[1, 1], m[2, 2] = s
        return m

    @staticmethod
    def _axis_angle_to_quaternion(rotation: list[float]) -> npt.NDArray[np.float64]:
        """
        Converte eixo [x, y, z] e ângulo t (radianos) num quatérnio unitário.

        Segue a regra da mão direita.

        Parameters
        ----------
        rotation : list[float]
            Rotação no formato [x, y, z, t]: eixo [x, y, z] (não precisa estar
            normalizado) e ângulo t em radianos.

        Returns
        -------
        NDArray[float64]
            Quatérnio unitário [w, x, y, z] equivalente. Retorna o quatérnio
            identidade [1, 0, 0, 0] quando o eixo é nulo.
        """
        eixo = np.asarray(rotation[:3], dtype=np.float64)
        norma = np.linalg.norm(eixo)

        if norma == 0:
            return np.array([1.0, 0.0, 0.0, 0.0])

        eixo = eixo / norma
        t = rotation[3]
        metade = t / 2
        return np.array([math.cos(metade), *(eixo * math.sin(metade))])

    @staticmethod
    def _quaternion_to_rotation_matrix(q: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de rotação a partir de um quatérnio unitário.

        Parameters
        ----------
        q : NDArray[float64]
            Quatérnio unitário [w, x, y, z].

        Returns
        -------
        NDArray[float64]
            Matriz 4x4 homogênea de rotação equivalente a `q`.
        """
        w, x, y, z = q

        # Fórmula padrão de conversão quatérnio unitário -> matriz de rotação,
        # obtida expandindo a rotação de um vetor v por v' = q*v*q⁻¹:
        # - Diagonal: cada eixo permanece 1 menos a contribuição dos OUTROS dois
        #   componentes da parte vetorial (ex: R[0][0]=1-2(y²+z²), a rotação em
        #   torno de x não deveria afetar o próprio x, só y e z, evitar o gimbal lock).
        # - Fora da diagonal: cada par (i,j) tem um termo simétrico de produto
        #   cruzado 2*qi*qj (a parte "linear" da rotação, do termo q_v⊗q_v) somado
        #   ou subtraído de um termo 2*w*qk (a parte "antissimétrica" que vem do
        #   termo w*[q_v]×, troca de sinal conforme (i,j,k) seguem a regra da
        #   mão direita, por isso R[i][j] e R[j][i] têm o termo 2*w*qk com sinais opostos).

        m = np.identity(4)
        m[:3, :3] = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y)],
            [2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y)],
        ])
        return m

    @staticmethod
    def _rotation_matrix(rotation: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de rotação a partir de eixo e ângulo.

        Parameters
        ----------
        rotation : list[float]
            Rotação no formato [x, y, z, t]: eixo [x, y, z] e ângulo t em
            radianos, seguindo a regra da mão direita.

        Returns
        -------
        NDArray[float64]
            Matriz 4x4 homogênea de rotação equivalente a `rotation`.
        """
        return GL._quaternion_to_rotation_matrix(GL._axis_angle_to_quaternion(rotation))

    @staticmethod
    def _perspective_matrix(field_of_view: float, aspect: float, near: float,
                            far: float) -> npt.NDArray[np.float64]:
        """
        Monta a matriz de projeção perspectiva.

        Parameters
        ----------
        field_of_view : float
            Campo de visão vertical, em radianos, já ajustado à razão de
            aspecto (ver GL.viewpoint).
        aspect : float
            Razão de aspecto da tela (largura / altura).
        near : float
            Distância do plano de corte próximo da câmera.
        far : float
            Distância do plano de corte distante da câmera.

        Returns
        -------
        NDArray[float64]
            Matriz 4x4 de projeção perspectiva (câmera -> clip).
        """
        top = near * math.tan(field_of_view / 2)
        right = top * aspect
        z_escala = -(far + near) / (far - near)
        z_translacao = -2 * far * near / (far - near)

        return np.array([
            [near / right, 0,          0,           0],
            [0,            near / top, 0,           0],
            [0,            0,          z_escala,    z_translacao],
            [0,            0,          -1,          0],
        ], dtype=np.float64)

    # Matrizes de reflexão e rotação usadas para gerar
    # os 8 octantes simétricos de um círculo a partir de um único octante calculado.
    _CIRCLE_OCTANT_REFLECTIONS: ClassVar[npt.NDArray[np.float64]] = np.array([
        [[1, 0], [0, 1]], [[0, 1], [1, 0]],
        [[0, -1], [1, 0]], [[-1, 0], [0, 1]],
        [[-1, 0], [0, -1]], [[0, -1], [-1, 0]],
        [[0, 1], [-1, 0]], [[1, 0], [0, -1]],
    ], dtype=np.float64)

    @staticmethod
    def _round(valor: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """
        Converte coordenada contínua para índice de pixel.

        Cada pixel n cobre o intervalo [n, n+1), então o índice correto é o
        piso da coordenada.

        Parameters
        ----------
        valor : ArrayLike
            Coordenada (ou array de coordenadas) contínua a converter.

        Returns
        -------
        NDArray[float64]
            Piso de `valor`, mesma forma que a entrada.
        """
        return np.floor(np.asarray(valor, dtype=np.float64))

    @staticmethod
    def _to_rgb8(cor: npt.ArrayLike) -> npt.NDArray[np.int64]:
        """
        Converte uma cor X3D (0 a 1) para o intervalo 0-255 usado pelo matplotlib.

        Parameters
        ----------
        cor : ArrayLike
            Cor (ou array de cores) no formato X3D, com cada canal em [0, 1]
            (ex: emissiveColor, ou um array (N, 3) de cores por triângulo).

        Returns
        -------
        NDArray[int64]
            Cor com cada canal em [0, 255], arredondada e recortada à faixa.
        """
        return np.clip(
            GL._round(np.asarray(cor, dtype=np.float64) * 255), 0, 255).astype(np.int64).tolist()

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
            Escreve em GL.ms_buffer; não há retorno.
        """
        dentro = (xs >= 0) & (xs < GL.width) & (ys >= 0) & (ys < GL.height)
        GL.ms_buffer[ys[dentro], xs[dentro], :, :] = cor

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
            Escreve em GL.ms_buffer; não há retorno.
        """
        # Verifica quais pontos caem dentro da tela e têm cobertura positiva.
        dentro = (xs >= 0) & (xs < GL.width) & (ys >= 0) & (ys < GL.height) & (cobertura > 0)
        xs_d, ys_d, cov_d = xs[dentro], ys[dentro], cobertura[dentro]

        # Quantiza a cobertura contínua para a quantidade de subamostras a
        # cobrir, de 0 a total_amostras.
        total_amostras = GL.MSAA_AMOSTRAS * GL.MSAA_AMOSTRAS
        n_amostras = np.clip(GL._round(cov_d * total_amostras), 0, total_amostras).astype(np.int64)

        # Máscara booleana por ponto: quais das total_amostras subamostras
        # (as N primeiras, em ordem fixa) devem receber a cor.
        indices = np.arange(total_amostras)
        marcar = (indices[None, :] < n_amostras[:, None]).reshape(
            -1, GL.MSAA_AMOSTRAS, GL.MSAA_AMOSTRAS)
        
        atual = GL.ms_buffer[ys_d, xs_d]
        atual[marcar] = np.asarray(cor) # Aplica o MSAA
        GL.ms_buffer[ys_d, xs_d] = atual

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
        y_exato = y0 + gradiente * (eixo - x0)

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
            Escreve em GL.ms_buffer; não há retorno.
        """
        # Bounding box do triângulo
        min_x = max(0, math.floor(min(x0, x1, x2)))
        max_x = min(GL.width - 1, math.ceil(max(x0, x1, x2)))
        min_y = max(0, math.floor(min(y0, y1, y2)))
        max_y = min(GL.height - 1, math.ceil(max(y0, y1, y2)))

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
        m = GL.MSAA_AMOSTRAS
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
        GL.ms_buffer[ys_pixel[ys_idx], xs_pixel[xs_idx], sy_idx, sx_idx] = cor

    @staticmethod
    def _triangle_coverage(x0: float, y0: float, x1: float, y1: float, x2: float, y2: float
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

        Parameters
        ----------
        x0, y0, x1, y1, x2, y2 : float
            Coordenadas de tela dos 3 vértices do triângulo.

        Returns
        -------
        tuple or None
            None se o triângulo cai inteiramente fora da tela. Senão,
            `(ys, xs, sy, sx, pesos)`: os 4 primeiros são índices em
            `GL.ms_buffer` (linha, coluna, subamostra y, subamostra x) das K
            subamostras cobertas; `pesos` é um array (3, K) com o peso
            baricêntrico de v0, v1 e v2 (nessa ordem) em cada subamostra.
        """
        min_x = max(0, math.floor(min(x0, x1, x2)))
        max_x = min(GL.width - 1, math.ceil(max(x0, x1, x2)))
        min_y = max(0, math.floor(min(y0, y1, y2)))
        max_y = min(GL.height - 1, math.ceil(max(y0, y1, y2)))

        if min_x > max_x or min_y > max_y:
            return None

        verts = np.array([[x0, y0], [x1, y1], [x2, y2]], dtype=np.float64)
        a = verts
        b = np.roll(verts, -1, axis=0)
        d = b - a

        arestas = np.column_stack([
            d[:,  1],
            -d[:, 0],
            a[:,  1] * d[:, 0] - a[:, 0] * d[:, 1],
        ])

        m = GL.MSAA_AMOSTRAS
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

        return ys_pixel[ys_idx], xs_pixel[xs_idx], sy_idx, sx_idx, pesos

    @staticmethod
    def _scan_triangle_color(x0: float, y0: float, cor0: npt.NDArray[np.float64],
                             x1: float, y1: float, cor1: npt.NDArray[np.float64],
                             x2: float, y2: float, cor2: npt.NDArray[np.float64]) -> None:
        """
        Varre um triângulo 2D com cor interpolada por vértice (Gouraud shading).

        Parameters
        ----------
        x0, y0, x1, y1, x2, y2 : float
            Coordenadas de tela dos 3 vértices do triângulo.
        cor0, cor1, cor2 : NDArray[float64]
            Cor de cada vértice (na mesma ordem), no formato X3D [r, g, b]
            com cada canal em [0, 1].

        Returns
        -------
        None
            Escreve em GL.ms_buffer; não há retorno.
        """
        cobertura = GL._triangle_coverage(x0, y0, x1, y1, x2, y2)

        if cobertura is None:
            return
        
        ys, xs, sy, sx, pesos = cobertura

        cor = (pesos[0][:, None] * cor0 + pesos[1][:, None] * cor1
               + pesos[2][:, None] * cor2)
        cor_rgb8 = np.clip(GL._round(cor * 255), 0, 255).astype(np.uint8)

        GL.ms_buffer[ys, xs, sy, sx] = cor_rgb8

    @staticmethod
    def _scan_triangle_textured(x0: float, y0: float, uv0: npt.NDArray[np.float64],
                                x1: float, y1: float, uv1: npt.NDArray[np.float64],
                                x2: float, y2: float, uv2: npt.NDArray[np.float64],
                                textura: npt.NDArray[np.uint8]) -> None:
        """
        Varre um triângulo 2D com uma textura mapeada por coordenadas UV por vértice.

        Amostragem nearest-neighbor (sem filtragem bilinear), com wrap
        (repeat) das coordenadas UV fora de [0, 1], que é o padrão X3D
        (`repeatS`/`repeatT` = TRUE).

        Parameters
        ----------
        x0, y0, x1, y1, x2, y2 : float
            Coordenadas de tela dos 3 vértices do triângulo.
        uv0, uv1, uv2 : NDArray[float64]
            Coordenada de textura [u, v] de cada vértice (na mesma ordem).
        textura : NDArray[uint8]
            Matriz de pixels da textura, no formato devolvido por
            `GL._get_texture` (eixos [u][v]).

        Returns
        -------
        None
            Escreve em GL.ms_buffer; não há retorno.
        """
        cobertura = GL._triangle_coverage(x0, y0, x1, y1, x2, y2)

        if cobertura is None:
            return
        
        ys, xs, sy, sx, pesos = cobertura

        uv = pesos[0][:, None] * uv0 + pesos[1][:, None] * uv1 + pesos[2][:, None] * uv2

        largura, altura = textura.shape[0], textura.shape[1]

        u = uv[:, 0] % 1.0
        v = uv[:, 1] % 1.0

        tx = np.clip((u * largura).astype(np.int64), 0, largura - 1)
        # V=0 no X3D é a base da textura, mas a linha 0 da imagem (após o
        # transpose de GPU.load_texture) é o topo, daí o (1 - v).
        ty = np.clip(((1.0 - v) * altura).astype(np.int64), 0, altura - 1)

        GL.ms_buffer[ys, xs, sy, sx] = textura[tx, ty, :3]

    @staticmethod
    def _get_texture(current_texture: list[str]) -> npt.NDArray[np.uint8] | None:
        """
        Carrega (com cache) a textura atual do Appearance.

        Parameters
        ----------
        current_texture : list[str]
            Caminho(s) da textura atual do Appearance/ImageTexture; usa-se
            apenas o primeiro, como o restante da GL faz para as demais
            propriedades resolvidas do Appearance.

        Returns
        -------
        NDArray[uint8] or None
            Matriz de pixels da textura (eixos [u][v], como devolvido por
            `gpu.GPU.load_texture`), ou None se `current_texture` estiver vazio.
        """
        if not current_texture:
            return None
        
        nome = current_texture[0]

        if nome not in GL._texture_cache:
            GL._texture_cache[nome] = gpu.GPU.load_texture(nome)

        return GL._texture_cache[nome]

    @staticmethod
    def _fan_triangulate(idxs: npt.NDArray[np.int64]
                         ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                    npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        """
        Triangula em leque uma lista de faces separadas por -1.

        Cada face é triangulada em leque a partir do seu primeiro vértice:
        (v0, v1, v2), (v0, v2, v3), (v0, v3, v4), ... : Usado tanto para os
        índices de vértice (`coordIndex`) quanto, com a mesma estrutura de
        faces, para os de cor (`colorIndex`) e de textura (`texCoordIndex`).

        Parameters
        ----------
        idxs : NDArray[int64]
            Índices concatenados de várias faces, com -1 separando cada uma.

        Returns
        -------
        NDArray[int64]
            i0 — índice do primeiro vértice do leque de cada triângulo.
        NDArray[int64]
            i1 — índice do segundo vértice de cada triângulo, mesmo tamanho de i0.
        NDArray[int64]
            i2 — índice do terceiro vértice de cada triângulo, mesmo tamanho de i0.
        NDArray[int64]
            face_id — posição, na lista de faces (contando as descartadas por
            terem menos de 3 vértices), da face de origem de cada triângulo.
        """
        cortes = np.nonzero(idxs == -1)[0]
        faces: list[npt.NDArray[np.int64]] = [
            segmento[segmento != -1] for segmento in np.split(idxs, cortes)]

        i0_partes: list[npt.NDArray[np.int64]] = []
        i1_partes: list[npt.NDArray[np.int64]] = []
        i2_partes: list[npt.NDArray[np.int64]] = []
        face_partes: list[npt.NDArray[np.int64]] = []

        for fid, face in enumerate(faces):
            if face.size < 3:
                continue

            n_tri = face.size - 2

            i0_partes.append(np.full(n_tri, face[0]))
            i1_partes.append(face[1:-1])
            i2_partes.append(face[2:])

            face_partes.append(np.full(n_tri, fid))

        if not i0_partes:
            vazio = np.empty(0, dtype=np.int64)

            return vazio, vazio, vazio, vazio

        return (np.concatenate(i0_partes), np.concatenate(i1_partes),
                np.concatenate(i2_partes), np.concatenate(face_partes))

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); o resultado
            final só aparece após o resolve do frame (GL.resolve_multisample()); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        pontos = GL._round(np.asarray(point).reshape(-1, 2)).astype(np.int64)

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        r = round(radius)

        # Sem For: Calcula octante aplica as matrizes identidade e
        # gera o circulo completo 

        # Calcula um único octante (0 <= x <= y)
        xs_octant = np.arange(0, int(r / math.sqrt(2)) + 1, dtype=np.float64)
        ys_octant = GL._round(np.sqrt(r ** 2 - xs_octant ** 2))

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])

        for i in range(0, len(vertices) - 5, 6):

            GL._scan_triangle(vertices[i], vertices[i + 1],
                              vertices[i + 2], vertices[i + 3],
                              vertices[i + 4], vertices[i + 5], cor)


    @staticmethod
    def _project_points(point: list[float]
                        ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
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
        """
        # Matriz completa: objeto -> mundo -> câmera -> clip.
        transformacao = GL.perspective_matrix @ GL.view_matrix @ GL.transform_stack[-1]

        pontos = np.asarray(point, dtype=np.float64).reshape(-1, 3)
        homogeneos = np.hstack([pontos, np.ones((pontos.shape[0], 1))])

        clip = (transformacao @ homogeneos.T).T
        # Divisão de perspectiva: normaliza pelo componente w.
        ndc = clip[:, :3] / clip[:, 3:4]

        # Mapeia de NDC ([-1, 1]) para coordenadas de tela (eixo y invertido).
        tela_x = (ndc[:, 0] + 1) / 2 * GL.width
        tela_y = (1 - ndc[:, 1]) / 2 * GL.height

        return tela_x, tela_y

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        tela_x, tela_y = GL._project_points(point)

        n_tri = len(tela_x) // 3
        i0 = np.arange(0, n_tri * 3, 3)
        i1, i2 = i0 + 1, i0 + 2

        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        xs, ys = tela_x.tolist(), tela_y.tolist()
        for a, b, c in zip(i0.tolist(), i1.tolist(), i2.tolist()):
            GL._scan_triangle(xs[a], ys[a],
                              xs[b], ys[b],
                              xs[c], ys[c], cor)

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
            Atualiza GL.view_matrix e GL.perspective_matrix; não há retorno.
        """
        # Matriz de transformação da câmera (câmera -> mundo): rotação seguida de translação.
        camera_para_mundo = GL._translation_matrix(position) @ GL._rotation_matrix(orientation)

        # A view é a inversa: para uma matriz de rotação + translação, a inversa é a
        # transposta do bloco de rotação seguida da translação negada.
        GL.view_matrix = np.linalg.inv(camera_para_mundo)

        aspect = GL.width / GL.height

        # O fieldOfView do X3D se aplica à menor dimensão da tela sem alteração; a maior
        # dimensão recebe o ângulo mais largo, calculado a partir da razão de aspecto.
        if aspect > 1:  # tela mais larga que alta: a vertical (menor) recebe o fov cru
            fovy = fieldOfView
        else:  # tela mais alta que larga: a horizontal (menor) recebe o fov cru
            fovy = 2 * math.atan(math.tan(fieldOfView / 2) / aspect)

        GL.perspective_matrix = GL._perspective_matrix(fovy, aspect, GL.near, GL.far)

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
            Empilha a matriz resultante em GL.transform_stack.
        """
        t = translation if translation else [0.0, 0.0, 0.0]
        s = scale if scale else [1.0, 1.0, 1.0]
        r = rotation if rotation else [0.0, 0.0, 1.0, 0.0]

        # Ordem de aplicação em um ponto local: primeiro escala, depois rotação,
        # depois translação — ou seja, local_para_pai = T @ R @ S.
        local_para_pai = GL._translation_matrix(t) @ GL._rotation_matrix(r) @ GL._scale_matrix(s)

        local_para_mundo = GL.transform_stack[-1] @ local_para_pai
        GL.transform_stack.append(local_para_mundo)

    @staticmethod
    def transform_out() -> None:
        """
        Sai de um nó Transform: desempilha a matriz de transformação corrente.

        Chamada ao sair de um nó X3D do tipo Transform do grafo de cena, para
        recuperar a matriz de transformação do Transform ancestral.

        Returns
        -------
        None
            Remove o topo de GL.transform_stack.
        """
        GL.transform_stack.pop()

    @staticmethod
    def _strip_triangle_indices(tiras: list[npt.NDArray[np.int64]]
                                ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                           npt.NDArray[np.int64]]:
        """
        Calcula os triplos (i0, i1, i2) de todos os triângulos de todas as tiras.

        Uma tira alterna o sentido "cru" da sequência a cada triângulo (0,1,2 depois
        1,2,3 depois 2,3,4...); para manter o mesmo sentido (anti-horário) em todos
        os triângulos gerados, os dois primeiros índices são trocados nos triângulos
        de posição ímpar dentro da tira.

        Parameters
        ----------
        tiras : list[NDArray[int64]]
            Lista de tiras, cada uma um array com os índices de vértice, na
            ordem em que aparecem na tira. Tiras com menos de 3 índices são
            ignoradas (não geram triângulo).

        Returns
        -------
        NDArray[int64]
            Índices do primeiro vértice de cada triângulo, de todas as tiras
            concatenadas.
        NDArray[int64]
            Índices do segundo vértice de cada triângulo, mesmo tamanho do
            primeiro retorno.
        NDArray[int64]
            Índices do terceiro vértice de cada triângulo, mesmo tamanho do
            primeiro retorno.
        """
        i0_partes: list[npt.NDArray[np.int64]] = []
        i1_partes: list[npt.NDArray[np.int64]] = []
        i2_partes: list[npt.NDArray[np.int64]] = []

        for tira in tiras:
            n = tira.size

            if n < 3:
                continue

            i = np.arange(n - 2)
            par = i % 2 == 0
            i0_partes.append(np.where(par, tira[i], tira[i + 1]))
            i1_partes.append(np.where(par, tira[i + 1], tira[i]))
            i2_partes.append(tira[i + 2])

        if not i0_partes:
            vazio = np.empty(0, dtype=np.int64)
            return vazio, vazio, vazio

        return (np.concatenate(i0_partes), np.concatenate(i1_partes), np.concatenate(i2_partes))

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        tela_x, tela_y = GL._project_points(point)

        # Array contento a quantidade de vértices de cada tira
        counts = np.asarray(stripCount, dtype=np.int64)

        # Array contendo os offsets de cada tira (inicio + quantidade)
        offsets = np.concatenate(([0], np.cumsum(counts)))

        # Cria uma lista de arrays, cada um contendo os índices de vértices de uma tira
        tiras: list[npt.NDArray[np.int64]] = [
            np.arange(offsets[i], offsets[i + 1]) for i in range(len(counts))]

        i0, i1, i2 = GL._strip_triangle_indices(tiras)

        # Back-Face Culling: descartar triângulos de costas para a câmera antes de rasterizar
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]
        
        xs, ys = tela_x.tolist(), tela_y.tolist()

        for a, b, c in zip(i0.tolist(), i1.tolist(), i2.tolist()):
            GL._scan_triangle(xs[a], ys[a],
                              xs[b], ys[b],
                              xs[c], ys[c], cor)

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        tela_x, tela_y = GL._project_points(point)

        idx = np.asarray(index, dtype=np.int64)
        # Divide em tiras nos pontos onde -1 aparece; cada segmento resultante,
        # exceto o primeiro, começa com o próprio -1 (removido pela máscara).
        cortes = np.nonzero(idx == -1)[0]
        tiras: list[npt.NDArray[np.int64]] = [
            segmento[segmento != -1] for segmento in np.split(idx, cortes)
        ]

        i0, i1, i2 = GL._strip_triangle_indices(tiras)
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2 = i0[frente], i1[frente], i2[frente]

        xs, ys = tela_x.tolist(), tela_y.tolist()
        for a, b, c in zip(i0.tolist(), i1.tolist(), i2.tolist()):
            GL._scan_triangle(xs[a], ys[a],
                              xs[b], ys[b],
                              xs[c], ys[c], cor)

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
            A função escreve no buffer de multisample da GL (GL.ms_buffer); não há
            retorno.
        """
        tela_x, tela_y = GL._project_points(coord)

        idxs = np.asarray(coordIndex, dtype=np.int64)
        i0, i1, i2, face_id = GL._fan_triangulate(idxs)

        if i0.size == 0:
            return

        # Back-Face Culling: descarta triângulos de costas para a câmera antes de rasterizar.
        frente = GL._front_facing_mask(tela_x, tela_y, i0, i1, i2)
        i0, i1, i2, face_id = i0[frente], i1[frente], i2[frente], face_id[frente]

        if i0.size == 0:
            return

        xs, ys = tela_x.tolist(), tela_y.tolist()

        # Textura: só se houver imagem e coordenada de textura, e a topologia de
        # texCoordIndex (ou o fallback coordIndex) bater com a de coordIndex:
        # Exigido pela spec X3D, mas verificado aqui por segurança.
        textura = GL._get_texture(current_texture) if texCoord and current_texture else None

        if textura is not None:
            tidx = np.asarray(texCoordIndex if texCoordIndex else coordIndex, dtype=np.int64)
            ti0, ti1, ti2, _ = GL._fan_triangulate(tidx)

            if ti0.size == frente.size:
                ti0, ti1, ti2 = ti0[frente], ti1[frente], ti2[frente]
                uv = np.asarray(texCoord, dtype=np.float64).reshape(-1, 2)
                uv0, uv1, uv2 = uv[ti0], uv[ti1], uv[ti2]

                for a, b, c, v0, v1, v2 in zip(i0.tolist(), i1.tolist(), i2.tolist(),
                                                uv0, uv1, uv2):

                    GL._scan_triangle_textured(xs[a], ys[a], v0,
                                               xs[b], ys[b], v1,
                                               xs[c], ys[c], v2, textura)
                return

        if color:
            cores = np.asarray(color, dtype=np.float64).reshape(-1, 3)

            if colorPerVertex:
                cidx = np.asarray(colorIndex if colorIndex else coordIndex, dtype=np.int64)
                ci0, ci1, ci2, _ = GL._fan_triangulate(cidx)

                if ci0.size == frente.size:
                    ci0, ci1, ci2 = ci0[frente], ci1[frente], ci2[frente]
                    cor0, cor1, cor2 = cores[ci0], cores[ci1], cores[ci2]

                    for a, b, c, v0, v1, v2 in zip(i0.tolist(), i1.tolist(), i2.tolist(),
                                                    cor0, cor1, cor2):

                        GL._scan_triangle_color(xs[a], ys[a], v0,
                                                xs[b], ys[b], v1,
                                                xs[c], ys[c], v2)
                    return
            else:
                # Uma cor por face inteira: colorIndex (se houver) indexa por
                # face, sem separadores -1; sem colorIndex, a i-ésima face usa
                # a i-ésima cor (face_id já é essa posição, 0-based).
                if colorIndex:
                    color_idx_por_tri = np.asarray(colorIndex, dtype=np.int64)[face_id]
                else:
                    color_idx_por_tri = face_id

                cor_tri = GL._to_rgb8(cores[color_idx_por_tri])

                for a, b, c, cor in zip(i0.tolist(), i1.tolist(), i2.tolist(), cor_tri):
                    GL._scan_triangle(xs[a], ys[a], xs[b], ys[b], xs[c], ys[c], cor)

                return

        cor = GL._to_rgb8(colors["emissiveColor"])

        for a, b, c in zip(i0.tolist(), i1.tolist(), i2.tolist()):
            GL._scan_triangle(xs[a], ys[a], xs[b], ys[b], xs[c], ys[c], cor)

    @staticmethod
    def box(size: list[float], colors: Colors) -> None:
        """
        Renderiza Box: um paralelepípedo centrado na origem local.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        size : list[float]
            Extensões da caixa [x, y, z] ao longo dos eixos locais; cada
            valor deve ser maior que zero.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.

        Returns
        -------
        None
            A função desenharia diretamente no framebuffer da GL; não há
            retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Box
        # A função box é usada para desenhar paralelepípedos na cena. O Box é centrada no
        # (0, 0, 0) no sistema de coordenadas local e alinhado com os eixos de coordenadas
        # locais. O argumento size especifica as extensões da caixa ao longo dos eixos X, Y
        # e Z, respectivamente, e cada valor do tamanho deve ser maior que zero. Para desenha
        # essa caixa você vai provavelmente querer tesselar ela em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Box : size = {0}".format(size)) # imprime no terminal pontos
        print("Box : colors = {0}".format(colors)) # imprime no terminal as cores

        # Exemplo de desenho de um pixel branco na coordenada 10, 10
        gpu.GPU.draw_pixel([10, 10], gpu.PixelFormat.RGB8, [255, 255, 255])  # altera pixel

    @staticmethod
    def sphere(radius: float, colors: Colors) -> None:
        """
        Renderiza Sphere: uma esfera centrada na origem local.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        radius : float
            Raio da esfera.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.

        Returns
        -------
        None
            A função desenharia diretamente no framebuffer da GL; não há
            retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Sphere
        # A função sphere é usada para desenhar esferas na cena. O esfera é centrada no
        # (0, 0, 0) no sistema de coordenadas local. O argumento radius especifica o
        # raio da esfera que está sendo criada. Para desenha essa esfera você vai
        # precisar tesselar ela em triângulos, para isso encontre os vértices e defina
        # os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Sphere : radius = {0}".format(radius)) # imprime no terminal o raio da esfera
        print("Sphere : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def cone(bottomRadius: float, height: float, colors: Colors) -> None:
        """
        Renderiza Cone: um cone centrado na origem local, alinhado ao eixo Y.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        bottomRadius : float
            Raio da base do cone.
        height : float
            Altura do cone.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.

        Returns
        -------
        None
            A função desenharia diretamente no framebuffer da GL; não há
            retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Cone
        # A função cone é usada para desenhar cones na cena. O cone é centrado no
        # (0, 0, 0) no sistema de coordenadas local. O argumento bottomRadius especifica o
        # raio da base do cone e o argumento height especifica a altura do cone.
        # O cone é alinhado com o eixo Y local. O cone é fechado por padrão na base.
        # Para desenha esse cone você vai precisar tesselar ele em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Cone : bottomRadius = {0}".format(bottomRadius)) # imprime no terminal o raio da base
        print("Cone : height = {0}".format(height)) # imprime no terminal a altura do cone
        print("Cone : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def cylinder(radius: float, height: float, colors: Colors) -> None:
        """
        Renderiza Cylinder: um cilindro centrado na origem local, alinhado ao eixo Y.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        radius : float
            Raio da base do cilindro.
        height : float
            Altura do cilindro.
        colors : Colors
            Cores resolvidas do Appearance/Material do nó.

        Returns
        -------
        None
            A função desenharia diretamente no framebuffer da GL; não há
            retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Cylinder
        # A função cylinder é usada para desenhar cilindros na cena. O cilindro é centrado no
        # (0, 0, 0) no sistema de coordenadas local. O argumento radius especifica o
        # raio da base do cilindro e o argumento height especifica a altura do cilindro.
        # O cilindro é alinhado com o eixo Y local. O cilindro é fechado por padrão em
        # ambas as extremidades.
        # Para desenha esse cilindro você vai precisar tesselar ele em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Cylinder : radius = {0}".format(radius)) # imprime no terminal o raio do cilindro
        print("Cylinder : height = {0}".format(height)) # imprime no terminal a altura do cilindro
        print("Cylinder : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def navigationInfo(headlight: bool) -> None:
        """
        Processa NavigationInfo: características do avatar e do modo de visualização.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        headlight : bool
            Se True, o visualizador deve acender uma luz direcional que
            sempre aponta na direção em que o usuário está olhando.

        Returns
        -------
        None
            Não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/navigation.html#NavigationInfo
        # O campo do headlight especifica se um navegador deve acender um luz direcional que
        # sempre aponta na direção que o usuário está olhando. Definir este campo como TRUE
        # faz com que o visualizador forneça sempre uma luz do ponto de vista do usuário.
        # A luz headlight deve ser direcional, ter intensidade = 1, cor = (1 1 1),
        # ambientIntensity = 0,0 e direção = (0 0 −1).

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("NavigationInfo : headlight = {0}".format(headlight)) # imprime no terminal

    @staticmethod
    def directionalLight(ambientIntensity: float, color: list[float], intensity: float,
                         direction: list[float]) -> None:
        """
        Processa DirectionalLight: uma luz direcional (raios paralelos).

        Ainda não implementado (stub) — ver comentário abaixo.

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
            Não há retorno.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#DirectionalLight
        # Define uma fonte de luz direcional que ilumina ao longo de raios paralelos
        # em um determinado vetor tridimensional. Possui os campos básicos ambientIntensity,
        # cor, intensidade. O campo de direção especifica o vetor de direção da iluminação
        # que emana da fonte de luz no sistema de coordenadas local. A luz é emitida ao
        # longo de raios paralelos de uma distância infinita.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("DirectionalLight : ambientIntensity = {0}".format(ambientIntensity))
        print("DirectionalLight : color = {0}".format(color)) # imprime no terminal
        print("DirectionalLight : intensity = {0}".format(intensity)) # imprime no terminal
        print("DirectionalLight : direction = {0}".format(direction)) # imprime no terminal

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

    @staticmethod
    def timeSensor(cycleInterval: float, loop: bool) -> float:
        """
        Gera eventos conforme o tempo passa (TimeSensor).

        Parameters
        ----------
        cycleInterval : float
            Duração de um ciclo do TimeSensor, em segundos. Deve ser maior
            que zero.
        loop : bool
            Se True, o TimeSensor continua a execução no próximo ciclo ao
            final de cada ciclo; se False, a execução é encerrada.

        Returns
        -------
        float
            Fração de tempo decorrida no ciclo atual, em [0, 1).
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/time.html#TimeSensor
        # Os nós TimeSensor podem ser usados para muitas finalidades, incluindo:
        # Condução de simulações e animações contínuas; Controlar atividades periódicas;
        # iniciar eventos de ocorrência única, como um despertador;
        # Se, no final de um ciclo, o valor do loop for FALSE, a execução é encerrada.
        # Por outro lado, se o loop for TRUE no final de um ciclo, um nó dependente do
        # tempo continua a execução no próximo ciclo. O ciclo de um nó TimeSensor dura
        # cycleInterval segundos. O valor de cycleInterval deve ser maior que zero.

        # Deve retornar a fração de tempo passada em fraction_changed

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("TimeSensor : cycleInterval = {0}".format(cycleInterval)) # imprime no terminal
        print("TimeSensor : loop = {0}".format(loop))

        # Esse método já está implementado para os alunos como exemplo
        epoch = time.time()  # time in seconds since the epoch as a floating point number.
        fraction_changed = (epoch % cycleInterval) / cycleInterval

        return fraction_changed

    @staticmethod
    def splinePositionInterpolator(set_fraction: float, key: list[float], keyValue: list[float],
                                   closed: bool) -> list[float]:
        """
        Interpola não linearmente entre uma lista de vetores 3D.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        set_fraction : float
            Fração a ser interpolada, em [0, 1].
        key : list[float]
            Chaves (quadros-chave) correspondentes a `keyValue`.
        keyValue : list[float]
            Vetores 3D a interpolar, no formato [x0, y0, z0, x1, y1, z1, ...] —
            um vetor por chave em `key`.
        closed : bool
            Se True, trata a malha de chaves como fechada, com uma transição
            da última chave para a primeira (ignorado se os keyValues da
            primeira e da última chave não forem idênticos).

        Returns
        -------
        list[float]
            Vetor 3D interpolado [x, y, z] para `set_fraction`.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/interpolators.html#SplinePositionInterpolator
        # Interpola não linearmente entre uma lista de vetores 3D. O campo keyValue possui
        # uma lista com os valores a serem interpolados, key possui uma lista respectiva de chaves
        # dos valores em keyValue, a fração a ser interpolada vem de set_fraction que varia de
        # zeroa a um. O campo keyValue deve conter exatamente tantos vetores 3D quanto os
        # quadros-chave no key. O campo closed especifica se o interpolador deve tratar a malha
        # como fechada, com uma transições da última chave para a primeira chave. Se os keyValues
        # na primeira e na última chave não forem idênticos, o campo closed será ignorado.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("SplinePositionInterpolator : set_fraction = {0}".format(set_fraction))
        print("SplinePositionInterpolator : key = {0}".format(key)) # imprime no terminal
        print("SplinePositionInterpolator : keyValue = {0}".format(keyValue))
        print("SplinePositionInterpolator : closed = {0}".format(closed))

        # Abaixo está só um exemplo de como os dados podem ser calculados e transferidos
        value_changed = [0.0, 0.0, 0.0]
        
        return value_changed

    @staticmethod
    def orientationInterpolator(set_fraction: float, key: list[float],
                                keyValue: list[float]) -> list[float]:
        """
        Interpola entre uma lista de valores de rotação específicos.

        Ainda não implementado (stub) — ver comentário abaixo.

        Parameters
        ----------
        set_fraction : float
            Fração a ser interpolada, em [0, 1].
        key : list[float]
            Chaves (quadros-chave) correspondentes a `keyValue`.
        keyValue : list[float]
            Rotações a interpolar, no formato [x0, y0, z0, t0, x1, y1, z1, t1,
            ...] — uma rotação (eixo + ângulo) por chave em `key`.

        Returns
        -------
        list[float]
            Rotação interpolada [x, y, z, t] para `set_fraction`.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/interpolators.html#OrientationInterpolator
        # Interpola rotações são absolutas no espaço do objeto e, portanto, não são cumulativas.
        # Uma orientação representa a posição final de um objeto após a aplicação de uma rotação.
        # Um OrientationInterpolator interpola entre duas orientações calculando o caminho mais
        # curto na esfera unitária entre as duas orientações. A interpolação é linear em
        # comprimento de arco ao longo deste caminho. Os resultados são indefinidos se as duas
        # orientações forem diagonalmente opostas. O campo keyValue possui uma lista com os
        # valores a serem interpolados, key possui uma lista respectiva de chaves
        # dos valores em keyValue, a fração a ser interpolada vem de set_fraction que varia de
        # zeroa a um. O campo keyValue deve conter exatamente tantas rotações 3D quanto os
        # quadros-chave no key.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("OrientationInterpolator : set_fraction = {0}".format(set_fraction))
        print("OrientationInterpolator : key = {0}".format(key)) # imprime no terminal
        print("OrientationInterpolator : keyValue = {0}".format(keyValue))

        # Abaixo está só um exemplo de como os dados podem ser calculados e transferidos
        value_changed = [0.0, 0.0, 1.0, 0.0]

        return value_changed

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
