"""
Carga de texturas, cadeia de mipmaps e amostragem.
"""

import math

import gpu  # Simula os recursos de uma GPU
import numpy as np
import numpy.typing as npt

from ._cores import piso
from ._estado import estado
from ._tipos import VerticeProjetado


def select_mip_level(x0: float, y0: float, x1: float, y1: float, x2: float, y2: float,
                      uv0: npt.NDArray[np.float64], uv1: npt.NDArray[np.float64],
                      uv2: npt.NDArray[np.float64], largura: int, altura: int,
                      n_niveis: int) -> int:
    """
    Escolhe o nível de mipmap a amostrar para um triângulo texturizado.

    Compara a área do triângulo em pixels de tela com a área que ele
    ocupa em texels da textura original (nível 0): quanto maior a razão
    texels-por-pixel, mais a textura está sendo minificada (mais textura
    precisa ser condensada em cada pixel de tela), e mais alto (mais
    reduzido) deve ser o nível de mipmap amostrado, para que cada pixel
    de tela amostre aproximadamente um texel do nível escolhido em vez
    de descartar informação de alta frequência (aliasing) ao amostrar
    direto do nível 0. Cada dobra de nível reduz a área em 4x (2x por
    eixo), daí o log2 de base 4 (equivalente a `0.5 * log2(razão)`).

    O nível é escolhido uma única vez por triângulo, não por pixel: o
    resto do rasterizador (`triangle_coverage`) também não calcula
    derivadas por subamostra, então essa é a mesma granularidade de
    aproximação já usada em todo o pipeline de textura.

    Parameters
    ----------
    x0, y0, x1, y1, x2, y2 : float
        Coordenadas de tela dos 3 vértices do triângulo.
    uv0, uv1, uv2 : NDArray[float64]
        Coordenada de textura [u, v] de cada vértice (na mesma ordem).
    largura : int
        Largura (texels) da textura no nível 0.
    altura : int
        Altura (texels) da textura no nível 0.
    n_niveis : int
        Quantidade de níveis disponíveis na cadeia de mipmaps.

    Returns
    -------
    int
        Índice do nível de mipmap a usar, em [0, n_niveis - 1].
    """
    area_tela = abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)) / 2

    # Triângulo degenerado em tela (área ~0): não há como estimar a
    # razão texel/pixel, usa-se o nível mais reduzido (cor média).
    if area_tela <= 0:
        return n_niveis - 1

    area_uv = abs((uv1[0] - uv0[0]) * (uv2[1] - uv0[1])
                  - (uv1[1] - uv0[1]) * (uv2[0] - uv0[0])) / 2
    area_texel = area_uv * largura * altura

    # Magnificação (menos texels que pixels, ou UV degenerado): nível 0,
    # a textura já não tem detalhe demais para o espaço em tela.
    if area_texel <= area_tela:
        return 0

    nivel = math.floor(0.5 * math.log2(area_texel / area_tela))
    return int(np.clip(nivel, 0, n_niveis - 1))


def sample_texture(pesos: npt.NDArray[np.float64],
                    verts: tuple[VerticeProjetado, VerticeProjetado, VerticeProjetado],
                    uvs: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64],
                               npt.NDArray[np.float64]],
                    mipmaps: list[npt.NDArray[np.uint8]]) -> npt.NDArray[np.uint8]:
    """
    Amostra a textura nas subamostras cobertas de um triângulo.

    Amostragem nearest-neighbor no nível de mipmap escolhido por
    `select_mip_level`, com wrap (repeat) das coordenadas UV fora de
    [0, 1], que é o padrão X3D (`repeatS`/`repeatT` = TRUE).

    Parameters
    ----------
    pesos : NDArray[float64]
        Pesos baricêntricos perspectiva-corretos das subamostras, array
        (3, K), devolvidos por `triangle_coverage`.
    verts : tuple[VerticeProjetado, VerticeProjetado, VerticeProjetado]
        Vértices do triângulo, em coordenadas de tela.
    uvs : tuple[NDArray[float64], NDArray[float64], NDArray[float64]]
        Coordenada de textura [u, v] de cada vértice.
    mipmaps : list[NDArray[uint8]]
        Cadeia de mipmaps da textura (ver `get_texture_mipmaps`).

    Returns
    -------
    NDArray[uint8]
        Cor RGB (K, 3) da textura em cada subamostra.
    """
    (x0, y0, *_), (x1, y1, *_), (x2, y2, *_) = verts
    uv0, uv1, uv2 = uvs
    uv = pesos[0][:, None] * uv0 + pesos[1][:, None] * uv1 + pesos[2][:, None] * uv2

    largura0, altura0 = mipmaps[0].shape[0], mipmaps[0].shape[1]
    nivel = select_mip_level(x0, y0, x1, y1, x2, y2, uv0, uv1, uv2,
                                 largura0, altura0, len(mipmaps))
    textura = mipmaps[nivel]
    largura, altura = textura.shape[0], textura.shape[1]

    u = uv[:, 0] % 1.0
    v = uv[:, 1] % 1.0

    tx = np.clip((u * largura).astype(np.int64), 0, largura - 1)
    # V=0 no X3D é a base da textura, mas a linha 0 da imagem (após o
    # transpose de GPU.load_texture) é o topo, daí o (1 - v).
    ty = np.clip(((1.0 - v) * altura).astype(np.int64), 0, altura - 1)

    return textura[tx, ty, :3]


def get_texture(current_texture: list[str]) -> npt.NDArray[np.uint8] | None:
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

    if nome not in estado.texture_cache:
        estado.texture_cache[nome] = gpu.GPU.load_texture(nome)

    return estado.texture_cache[nome]


def build_mipmaps(textura: npt.NDArray[np.uint8]) -> list[npt.NDArray[np.uint8]]:
    """
    Gera a cadeia de mipmaps de uma textura por filtragem de caixa.

    Cada nível seguinte tem metade da resolução do anterior (uma
    dimensão ímpar tem sua última linha/coluna duplicada antes de
    reduzir, para que só existam blocos 2x2 completos de texels) e é
    obtido pela média de cada bloco 2x2 de texels do nível anterior.
    Isso pré-filtra a alta frequência espacial da textura em cada
    redução, ao contrário de simplesmente pular texels (nearest-
    neighbor na redução), que preservaria aliasing em vez de eliminá-lo.
    A cadeia termina no nível 1x1, a cor média de toda a textura.

    Parameters
    ----------
    textura : NDArray[uint8]
        Nível 0 (textura original), no formato devolvido por
        `gpu.GPU.load_texture` (eixos [u][v]).

    Returns
    -------
    list[NDArray[uint8]]
        Cadeia de mipmaps, do nível 0 (original) ao 1x1, nessa ordem.
    """
    niveis = [textura]
    atual = textura

    while atual.shape[0] > 1 or atual.shape[1] > 1:
        if atual.shape[0] % 2:
            atual = np.concatenate([atual, atual[-1:, :, :]], axis=0)
        if atual.shape[1] % 2:
            atual = np.concatenate([atual, atual[:, -1:, :]], axis=1)

        blocos = atual.astype(np.float64).reshape(
            atual.shape[0] // 2, 2, atual.shape[1] // 2, 2, atual.shape[2])
        atual = piso(blocos.mean(axis=(1, 3))).astype(np.uint8)

        niveis.append(atual)

    return niveis


def get_texture_mipmaps(current_texture: list[str]) -> list[npt.NDArray[np.uint8]] | None:
    """
    Carrega (com cache) a cadeia de mipmaps da textura atual do Appearance.

    Reaproveita o cache de textura de `get_texture` para o nível 0 e
    constrói (uma única vez por textura, também cacheada) o restante da
    cadeia com `build_mipmaps`.

    Parameters
    ----------
    current_texture : list[str]
        Caminho(s) da textura atual do Appearance/ImageTexture; usa-se
        apenas o primeiro, como o restante da GL faz para as demais
        propriedades resolvidas do Appearance.

    Returns
    -------
    list[NDArray[uint8]] or None
        Cadeia de mipmaps (ver `build_mipmaps`), ou None se
        `current_texture` estiver vazio.
    """
    if not current_texture:
        return None

    nome = current_texture[0]

    if nome not in estado.mipmap_cache:
        textura = get_texture(current_texture)
        assert textura is not None
        estado.mipmap_cache[nome] = build_mipmaps(textura)

    return estado.mipmap_cache[nome]


def optional_mipmaps(current_texture: list[str] | None) -> list[npt.NDArray[np.uint8]] | None:
    """
    Devolve os mipmaps da textura atual, ou None se o Appearance não tem textura.

    Parameters
    ----------
    current_texture : list[str] or None
        Caminho(s) da textura atual do Appearance.

    Returns
    -------
    list[NDArray[uint8]] or None
        Cadeia de mipmaps (ver `get_texture_mipmaps`), ou None.
    """
    return get_texture_mipmaps(current_texture) if current_texture else None
