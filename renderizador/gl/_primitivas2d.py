"""
Rasterização de pontos e linhas.
"""

import math

import numpy as np
import numpy.typing as npt

from ._constantes import MSAA_AMOSTRAS
from ._cores import piso
from ._estado import estado


def draw_points(xs: npt.NDArray[np.int64], ys: npt.NDArray[np.int64],
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


def draw_points_blend(xs: npt.NDArray[np.int64], ys: npt.NDArray[np.int64],
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


def line_points(x0: float, y0: float, x1: float, y1: float
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
