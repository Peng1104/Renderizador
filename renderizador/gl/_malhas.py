"""
Tesselação das primitivas 3D em malhas de triângulos.
"""

import math
from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from ._constantes import BOX_FACE_UV, SEGMENTOS, SPHERE_FAIXAS
from ._estado import estado
from ._tipos import Malha


def circle_xz(segmentos: int) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Gera os cossenos e senos de uma volta completa, usados nos anéis de cone e cilindro.

    Parameters
    ----------
    segmentos : int
        Quantidade de fatias da volta.

    Returns
    -------
    NDArray[float64]
        Cosseno de cada ângulo, com `segmentos + 1` valores (o último
        repete o primeiro, para fechar a costura sem reindexar).
    NDArray[float64]
        Seno de cada ângulo, mesmo tamanho do retorno anterior.
    """
    angulos = np.linspace(0.0, 2 * math.pi, segmentos + 1)
    return np.cos(angulos), np.sin(angulos)


def cap_mesh(raio: float, y: float, normal_y: float, segmentos: int, base: int
              ) -> Malha:
    """
    Gera uma tampa circular (disco) em triângulos, com normal ao longo de Y.

    Parameters
    ----------
    raio : float
        Raio do disco.
    y : float
        Altura do plano do disco, em coordenadas de objeto.
    normal_y : float
        Sentido da normal: +1 para tampa voltada para cima, -1 para baixo.
    segmentos : int
        Quantidade de fatias do disco.
    base : int
        Índice do primeiro vértice da tampa na malha final, somado aos
        índices dos triângulos para que apontem para os vértices certos.

    Returns
    -------
    Malha
        Posições, normais, triângulos (índices já deslocados por `base`)
        e UVs do disco, em ordem anti-horária vista de fora. Os UVs são
        um recorte circular da textura (centro em (0.5, 0.5), raio 0.5),
        com a imagem em pé vista de fora: na tampa de cima, com o fundo
        (-Z) para o alto da imagem; na de baixo, com +Z para o alto.
    """
    c, s = circle_xz(segmentos)
    anel = np.stack([raio * c, np.full_like(c, y), raio * s], axis=1)
    posicoes = np.vstack([[0.0, y, 0.0], anel])
    normais = np.tile([0.0, normal_y, 0.0], (len(posicoes), 1))
    sentido_v = -normal_y  # vista de baixo, o alto da imagem passa de -Z para +Z
    uv = 0.5 + 0.5 * np.stack([posicoes[:, 0], sentido_v * posicoes[:, 2]], axis=1) / raio

    j = np.arange(segmentos)
    centro = np.zeros(segmentos, dtype=np.int64)
    atual, proximo = j + 1, j + 2
    # Vista de cima, φ crescente é horário; a tampa de baixo inverte a ordem.
    pares = (proximo, atual) if normal_y > 0 else (atual, proximo)
    triangulos = np.stack([centro, pares[0], pares[1]], axis=1) + base
    return posicoes, normais, triangulos, uv


def join_meshes(malhas: list[Malha]) -> Malha:
    """
    Concatena várias malhas numa só, reindexando os triângulos.

    Parameters
    ----------
    malhas : list[Malha]
        Malhas cujos triângulos indexam apenas os próprios vértices.

    Returns
    -------
    Malha
        Malha única com os vértices, normais, triângulos e UVs de todas.
    """
    deslocamento = np.cumsum([0] + [len(m[0]) for m in malhas[:-1]])
    posicoes = np.vstack([m[0] for m in malhas])
    normais = np.vstack([m[1] for m in malhas])
    triangulos = np.vstack([m[2] + d for m, d in zip(malhas, deslocamento)])
    uv = np.vstack([m[3] for m in malhas])
    return posicoes, normais, triangulos, uv


def side_mesh(raio_topo: float, raio_base: float, altura: float, segmentos: int,
               normal_y: float) -> Malha:
    """
    Gera a superfície lateral de um cone ou cilindro (anel de cima e anel de baixo).

    Os vértices são duplicados em cada fatia (e a costura repetida), para
    que cada fatia tenha a própria normal e a lateral fique suave.

    Parameters
    ----------
    raio_topo : float
        Raio do anel de cima (0 para um cone, com o vértice no topo).
    raio_base : float
        Raio do anel de baixo.
    altura : float
        Altura total; o sólido fica centrado na origem em Y.
    segmentos : int
        Quantidade de fatias.
    normal_y : float
        Componente Y (antes de normalizar) da normal lateral: 0 para
        cilindro e `raio_base` para cone, junto com o componente
        horizontal `altura`.

    Returns
    -------
    Malha
        Posições, normais, triângulos e UVs da lateral, em ordem
        anti-horária vista de fora. A textura dá a volta no sentido
        anti-horário visto de cima, a partir do fundo (-Z): u vale 0 no
        fundo, e o desenrolado (sem módulo) evita um salto de UV na
        costura da malha. v vai de 0 na base a 1 no topo.
    """
    c, s = circle_xz(segmentos)
    topo = np.stack([raio_topo * c, np.full_like(c, altura / 2), raio_topo * s], axis=1)
    base = np.stack([raio_base * c, np.full_like(c, -altura / 2), raio_base * s], axis=1)
    horizontal = altura if normal_y else 1.0
    n = np.stack([horizontal * c, np.full_like(c, normal_y), horizontal * s], axis=1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)

    j = np.arange(segmentos)
    t, t1 = j, j + 1
    b, b1 = j + segmentos + 1, j + segmentos + 2
    triangulos = np.vstack([np.stack([b1, b, t], axis=1), np.stack([b1, t, t1], axis=1)])
    if raio_topo == 0:  # cone: o segundo triângulo do quad degenera no vértice
        triangulos = triangulos[:segmentos]
    u = 0.75 - np.arange(segmentos + 1) / segmentos
    uv = np.vstack([np.stack([u, np.ones_like(u)], axis=1),
                    np.stack([u, np.zeros_like(u)], axis=1)])
    return np.vstack([topo, base]), np.vstack([n, n]), triangulos, uv


def box_mesh(tamanho: tuple[float, float, float]) -> Malha:
    """
    Gera a malha de um Box centrado na origem, com 4 vértices por face.

    Parameters
    ----------
    tamanho : tuple[float, float, float]
        Extensões da caixa ao longo de X, Y e Z.

    Returns
    -------
    Malha
        24 vértices (normais planas por face), 12 triângulos e, em cada
        face, a textura inteira (U para a direita e V para cima vistos de fora).
    """
    meio = np.asarray(tamanho, dtype=np.float64) / 2
    # Cada face: normal e 4 cantos em ordem anti-horária vista de fora.
    faces = [
        ((0, 0, 1), [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]),
        ((0, 0, -1), [(1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)]),
        ((1, 0, 0), [(1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)]),
        ((-1, 0, 0), [(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)]),
        ((0, 1, 0), [(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)]),
        ((0, -1, 0), [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)]),
    ]
    posicoes = np.array([c for _, cantos in faces for c in cantos], dtype=np.float64) * meio
    normais = np.array([n for n, _ in faces for _ in range(4)], dtype=np.float64)
    quad = np.array([[0, 1, 2], [0, 2, 3]])
    triangulos = np.vstack([quad + 4 * f for f in range(len(faces))])
    return posicoes, normais, triangulos, np.tile(BOX_FACE_UV, (len(faces), 1))


def sphere_mesh(raio: float) -> Malha:
    """
    Gera a malha de uma Sphere centrada na origem (latitude por longitude).

    Parameters
    ----------
    raio : float
        Raio da esfera.

    Returns
    -------
    Malha
        Vértices, normais (direção radial), triângulos e UVs; nos polos os
        triângulos degenerados têm área zero e são descartados pelo culling.
        A textura dá a volta no sentido anti-horário visto de cima, a
        partir do fundo (-Z), com v = 1 no polo norte (ver `side_mesh`).
    """
    faixas, fatias = SPHERE_FAIXAS, SEGMENTOS
    theta = np.linspace(0.0, math.pi, faixas + 1)[:, None]
    phi = np.linspace(0.0, 2 * math.pi, fatias + 1)[None, :]
    normais = np.stack([np.sin(theta) * np.cos(phi),
                        np.cos(theta) * np.ones_like(phi),
                        np.sin(theta) * np.sin(phi)], axis=-1).reshape(-1, 3)

    i, j = np.meshgrid(np.arange(faixas), np.arange(fatias), indexing="ij")
    a = (i * (fatias + 1) + j).ravel()
    b, c, d = a + 1, a + fatias + 1, a + fatias + 2
    triangulos = np.vstack([np.stack([d, c, a], axis=1), np.stack([d, a, b], axis=1)])
    u = np.broadcast_to(0.75 - phi / (2 * math.pi), (faixas + 1, fatias + 1))
    v = np.broadcast_to(1.0 - theta / math.pi, (faixas + 1, fatias + 1))
    uv = np.stack([u, v], axis=-1).reshape(-1, 2)
    return normais * raio, normais, triangulos, uv


def cached_mesh(chave: tuple[object, ...], construir: Callable[[], Malha]) -> Malha:
    """
    Devolve a malha de uma primitiva, construindo-a só na primeira vez.

    Parameters
    ----------
    chave : tuple[object, ...]
        Identifica a primitiva e seus parâmetros (por exemplo, `("box", x, y, z)`).
    construir : Callable[[], Malha]
        Função sem argumentos que gera a malha quando não está em cache.

    Returns
    -------
    Malha
        Malha da primitiva, compartilhada entre frames.
    """
    if chave not in estado.mesh_cache:
        estado.mesh_cache[chave] = construir()
    return estado.mesh_cache[chave]
