"""
Ciclo de vida do frame: setup, limpeza, escrita com blend e resolve do multisample.
"""

import gpu  # Simula os recursos de uma GPU
import numpy as np
import numpy.typing as npt

from ._constantes import MSAA_AMOSTRAS
from ._cores import piso
from ._estado import estado


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


def blend_write(ys: npt.NDArray[np.int64], xs: npt.NDArray[np.int64],
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
