#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Simulador de GPU.

Desenvolvido por: Luciano Soares <lpsoares@insper.edu.br>
Disciplina: Computação Gráfica
Data: 31 de Agosto de 2020
"""

import os  # Para rotinas do sistema operacional
from enum import IntEnum, IntFlag, auto
from typing import ClassVar, Sequence

# Numpy
import numpy as np
import numpy.typing as npt

# Pillow
from PIL import Image

# Tipos de dados

Coord = Sequence[int]
PixelData = Sequence[float] | npt.NDArray[np.floating] | npt.NDArray[np.integer]

class FramebufferTarget(IntFlag):
    """
    Define para qual operação (leitura, escrita ou ambas) um FrameBuffer é vinculado.
    """

    DRAW_FRAMEBUFFER = auto()  # Faz o bind só para escrever no framebuffer
    READ_FRAMEBUFFER = auto()  # Faz o bind só para leitura no framebuffer
    FRAMEBUFFER = DRAW_FRAMEBUFFER | READ_FRAMEBUFFER  # Faz o bind para leitura e escrita


class PixelFormat(IntEnum):
    """
    Formato dos dados armazenados em um canal (cor ou profundidade) do FrameBuffer.
    """

    RGB8 = 0b001  # Vermelho, Verde, Azul de 8bits cada (0-255)
    RGBA8 = 0b010  # Vermelho, Verde, Azul e Transparência de 8bits cada (0-255)
    DEPTH_COMPONENT16 = 0b101  # Profundidade de 16bits cada (0-65535)
    DEPTH_COMPONENT32F = 0b110  # Profundidade de 32bits em float


class Attachment(IntEnum):
    """
    Identifica qual memória de um FrameBuffer Object está sendo referenciada.
    """

    COLOR_ATTACHMENT = 0  # Alocações para as cores da imagem renderizada
    DEPTH_ATTACHMENT = 1  # Alocações para as profundidades da imagem renderizada


class FrameBuffer:
    """
    Organiza objetos FrameBuffer (FrameBuffer Objects).
    """

    def __init__(self) -> None:
        """
        Iniciando propriedades do FramBuffer.
        """
        self.color: npt.NDArray[np.uint8] = np.empty(0, dtype=np.uint8)
        self.depth: npt.NDArray[np.number] = np.empty(0)


class GPU:
    """
    Classe que representa o funcionamento de uma GPU.
    """

    # Atributos estáticos
    image_file: ClassVar[str] = ""
    frame_buffer: ClassVar[list[FrameBuffer]] = []
    path: ClassVar[str] = "."
    draw_framebuffer: ClassVar[int] = 0
    read_framebuffer: ClassVar[int] = 0
    clear_color_val: ClassVar[Sequence[float]] = [0, 0, 0]
    clear_depth_val: ClassVar[float] = 1.0

    def __init__(self, image_file: str, path: str) -> None:
        """
        Define o nome do arquivo para caso se salvar o framebuffer.
        """
        GPU.image_file = image_file

        # Inicia lista para objetos Frame Buffer
        GPU.frame_buffer = []

        # Define buffers de leitura e escrita
        GPU.draw_framebuffer = 0
        GPU.read_framebuffer = 0

        # Cor e profundidade padrão para apagar o FrameBuffer
        GPU.clear_color_val = [0, 0, 0]
        GPU.clear_depth_val = 1.0

        # Caminho para arquivos adicionais, como texturas
        GPU.path = path

    @staticmethod
    def gen_framebuffers(size: int) -> list[int]:
        """
        Gera posições para FrameBuffers.
        """
        allocated: list[int] = []
        for _ in range(size):
            fbo = FrameBuffer()
            GPU.frame_buffer.append(fbo)
            allocated += [len(GPU.frame_buffer)-1]  # informado a posição recem alocada
        return allocated

    @staticmethod
    def bind_framebuffer(buffer: FramebufferTarget, position: int) -> None:
        """
        Define o framebuffer a ser usado e como.
        """
        if buffer == FramebufferTarget.DRAW_FRAMEBUFFER:
            GPU.draw_framebuffer = position
        elif buffer == FramebufferTarget.READ_FRAMEBUFFER:
            GPU.read_framebuffer = position
        elif buffer == FramebufferTarget.FRAMEBUFFER:
            GPU.draw_framebuffer = position
            GPU.read_framebuffer = position

    @staticmethod
    def framebuffer_storage(position: int, attachment: Attachment, mode: PixelFormat,
                            width: int, height: int) -> None:
        """
        Aloca o FrameBuffer especificado.
        """
        if attachment == Attachment.COLOR_ATTACHMENT:
            if mode == PixelFormat.RGB8:
                dtype = np.uint8
                depth = 3
            else:  # mode == PixelFormat.RGBA8:
                dtype = np.uint8
                depth = 4
            # Aloca espaço definindo todos os valores como 0 (imagem preta)
            GPU.frame_buffer[position].color = np.zeros((height, width, depth), dtype=dtype)
        elif attachment == Attachment.DEPTH_ATTACHMENT:
            if mode == PixelFormat.DEPTH_COMPONENT16:
                dtype = np.uint16
                depth = 1
            else:  # mode == PixelFormat.DEPTH_COMPONENT32F:
                dtype = np.float32
                depth = 1
            # Aloca espaço definindo todos os valores como 1 (profundidade máxima)
            GPU.frame_buffer[position].depth = np.ones((height, width, depth), dtype=dtype)

    @staticmethod
    def clear_color(color: Sequence[float]) -> None:
        """
        Definindo cor para apagar o FrameBuffer.
        """
        GPU.clear_color_val = color

    @staticmethod
    def clear_depth(depth: float) -> None:
        """
        Definindo profundidade para apagar o FrameBuffer.
        """
        GPU.clear_depth_val = depth

    @staticmethod
    def clear_buffer() -> None:
        """
        Usa o mesmo valor em todo o FrameBuffer, na prática apagando ele.
        """
        if GPU.frame_buffer[GPU.draw_framebuffer].color.size != 0:
            GPU.frame_buffer[GPU.draw_framebuffer].color[:] = GPU.clear_color_val
        if GPU.frame_buffer[GPU.draw_framebuffer].depth.size != 0:
            GPU.frame_buffer[GPU.draw_framebuffer].depth[:] = GPU.clear_depth_val

    @staticmethod
    def draw_pixel(coord: Coord, mode: PixelFormat, data: PixelData) -> None:
        """
        Define o valor do pixel no framebuffer.
        """
        if coord and np.any(data):
            if mode in (PixelFormat.RGB8, PixelFormat.RGBA8):  # cores

                #  Verifica se o Framebuffer do canal de cor foi alocado
                if GPU.frame_buffer[GPU.draw_framebuffer].color.size != 0:

                    # Coleta a dimensão do Framebuffer para o canal de cor
                    fb_dim = GPU.frame_buffer[GPU.draw_framebuffer].color.shape

                    # Verifica se escrita é em um local válido
                    fora_dos_limites = (coord[0] < 0 or coord[0] >= fb_dim[1]
                                        or coord[1] < 0 or coord[1] >= fb_dim[0])
                    if fora_dos_limites:
                        raise Exception(
                            f"Acesso irregular de escrita na posição [{coord[0]}, {coord[1]}] "
                            f"do Framebuffer {fb_dim[1], fb_dim[0]}")

                    # Verifica se os dados estão no tamanho certo e em uma faixa suportada
                    dados_validos = (isinstance(data, (list, tuple, np.ndarray))
                                     and len(data) == (mode + 2)
                                     and all(0 <= i <= 255 for i in data))
                    if dados_validos:
                        # Grava dados no Framebuffer
                        GPU.frame_buffer[GPU.draw_framebuffer].color[coord[1]][coord[0]] = data
                    else:
                        raise Exception(
                            f"Valores do Frame buffer devem estar em um vetor de dimensão "
                            f"[{mode+2}] ser inteiros e estar entre 0 e 255")
                else:
                    raise Exception(
                        f"Frame buffer {GPU.draw_framebuffer} não alocado com o canal de cor")

            elif mode in (PixelFormat.DEPTH_COMPONENT16,
                        PixelFormat.DEPTH_COMPONENT32F):  # profundidade

                #  Verifica se o Framebuffer do canal de profundidade foi alocado
                if GPU.frame_buffer[GPU.draw_framebuffer].depth.size != 0:

                    # Coleta a dimensão do Framebuffer para o canal de profundidade
                    fb_dim = GPU.frame_buffer[GPU.draw_framebuffer].depth.shape

                    # Verifica se escrita é em um local válido
                    fora_dos_limites = (coord[0] < 0 or coord[0] >= fb_dim[1]
                                        or coord[1] < 0 or coord[1] >= fb_dim[0])
                    if fora_dos_limites:
                        raise Exception(
                            f"Acesso irregular de escrita na posição [{coord[0]}, {coord[1]}] "
                            f"do Framebuffer {fb_dim[1], fb_dim[0]}")

                    # Verifica se os dados estão no tamanho certo e em um formato suportado
                    dados_validos = (isinstance(data, (list, tuple, np.ndarray))
                                     and len(data) == 1
                                     and isinstance(data[0], (int, float)))
                    if dados_validos:
                        # Grava dados no Framebuffer
                        GPU.frame_buffer[GPU.draw_framebuffer].depth[coord[1]][coord[0]] = data
                    else:
                        raise Exception(
                            "Valores do Frame buffer devem ser um vetor com um único "
                            f"valor numérico: {data}")

                else:
                    raise Exception(
                        f"Frame buffer {GPU.draw_framebuffer} "
                        "não alocado com o canal de profundidade")

            else:
                raise Exception(f"Modo inválido de leitura do Frame buffer ({mode})")

    @staticmethod
    def read_pixel(coord: Coord, mode: PixelFormat) -> npt.NDArray[np.number] | None:
        """
        Retorna o valor do pixel no framebuffer.
        """
        data = None
        if coord:
            if mode in (PixelFormat.RGB8, PixelFormat.RGBA8):  # cores

                #  Verifica se o Framebuffer do canal de cor foi alocado
                if GPU.frame_buffer[GPU.draw_framebuffer].color.size != 0:

                    # Coleta a dimensão do Framebuffer para o canal de cor
                    fb_dim = GPU.frame_buffer[GPU.read_framebuffer].color.shape

                    # Verifica se leitura é em um local válido
                    fora_dos_limites = (coord[0] < 0 or coord[0] >= fb_dim[1]
                                        or coord[1] < 0 or coord[1] >= fb_dim[0])
                    if fora_dos_limites:
                        raise Exception(
                            f"Acesso irregular de leitura na posição [{coord[0]}, {coord[1]}] "
                            f"do Framebuffer {fb_dim[1], fb_dim[0]}")

                    data = GPU.frame_buffer[GPU.read_framebuffer].color[coord[1]][coord[0]]

                else:
                    raise Exception(
                        f"Frame buffer {GPU.draw_framebuffer} não alocado com o canal de cor")

            elif mode in (PixelFormat.DEPTH_COMPONENT16,
                        PixelFormat.DEPTH_COMPONENT32F):  # profundidade

                #  Verifica se o Framebuffer do canal de profundidade foi alocado
                if GPU.frame_buffer[GPU.draw_framebuffer].depth.size != 0:

                    # Coleta a dimensão do Framebuffer para o canal de profundidade
                    fb_dim = GPU.frame_buffer[GPU.read_framebuffer].depth.shape

                    # Verifica se leitura é em um local válido
                    fora_dos_limites = (coord[0] < 0 or coord[0] >= fb_dim[1]
                                        or coord[1] < 0 or coord[1] >= fb_dim[0])
                    if fora_dos_limites:
                        raise Exception(
                            f"Acesso irregular de leitura na posição [{coord[0]}, {coord[1]}] "
                            f"do Framebuffer {fb_dim[1], fb_dim[0]}")

                    data = GPU.frame_buffer[GPU.read_framebuffer].depth[coord[1]][coord[0]]

                else:
                    raise Exception(
                        f"Frame buffer {GPU.draw_framebuffer} "
                        "não alocado com o canal de profundidade")

            else:
                raise Exception(f"Modo inválido de leitura do Frame buffer ({mode})")

            # Retorna valor dos dados do Framebuffer
            return data
        return data

    @staticmethod
    def save_image() -> None:
        """
        Método para salvar a imagem do framebuffer em um arquivo.
        """
        if GPU.frame_buffer[GPU.read_framebuffer].color.shape[2] == 3:
            img = Image.fromarray(GPU.frame_buffer[GPU.read_framebuffer].color, 'RGB')
        else:
            img = Image.fromarray(GPU.frame_buffer[GPU.read_framebuffer].color, 'RGBA')
        counter = 0
        filename = GPU.image_file.split('.')
        while os.path.exists(filename[0]+str(counter).zfill(3)+'.'+filename[1]):
            counter += 1
        img.save(filename[0]+str(counter).zfill(3)+'.'+filename[1])

    @staticmethod
    def load_texture(textura: str) -> npt.NDArray[np.uint8]:
        """
        Método para ler textura.
        """
        file = os.path.join(GPU.path, textura)
        imagem = Image.open(file).transpose(Image.Transpose.TRANSPOSE)
        matriz = np.array(imagem, dtype=np.uint8)
        return matriz

    @staticmethod
    def get_frame_buffer() -> npt.NDArray[np.uint8]:
        """
        Retorna o Framebuffer atual para leitura.
        """
        return GPU.frame_buffer[GPU.read_framebuffer].color

    @staticmethod
    def swap_buffers() -> None:
        """
        Método para a troca dos buffers (NÃO IMPLEMENTADA).
        """
