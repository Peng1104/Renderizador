"""
Triangulação de faces (leque) e de tiras de triângulos.
"""

import numpy as np
import numpy.typing as npt

from ._estado import estado


def fan_triangulate(idxs: npt.NDArray[np.int64]
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


def fan_triangulate_cached(idxs: list[int]
                            ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                       npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    """
    Versão cacheada de `fan_triangulate`, por identidade da lista de índices.

    Um nó de geometria é parseado uma única vez do XML na carga da
    cena; suas listas de índices (`coordIndex`, `colorIndex`,
    `texCoordIndex`) são os mesmos objetos de lista reusados a cada
    frame renderizado, para malhas estáticas (nada no grafo de cena
    substitui essas listas depois do parse). Cachear o resultado da
    triangulação em leque por `id()` da lista evita repetir esse
    trabalho a cada frame para uma malha que não muda: o ganho cresce
    com o número de vértices da malha e o número de frames
    renderizados, o caso comum de uma cena parada ou com só a câmera
    se movendo.

    A chave usada é a identidade do objeto Python (`id()`), não o seu
    conteúdo: é seguro aqui porque os nós do grafo de cena, e portanto
    suas listas de índice, permanecem vivos durante toda a sessão de
    renderização (nunca são descartados nem substituídos por outro
    objeto), então o mesmo `id()` nunca passa a apontar para uma lista
    de conteúdo diferente entre uma chamada e outra.

    Parameters
    ----------
    idxs : list[int]
        Índices concatenados de várias faces, com -1 separando cada
        uma (mesmo formato de `fan_triangulate`).

    Returns
    -------
    Mesmo retorno de `fan_triangulate`.
    """
    chave = id(idxs)

    if chave not in estado.fan_cache:
        estado.fan_cache[chave] = fan_triangulate(np.asarray(idxs, dtype=np.int64))

    return estado.fan_cache[chave]


def strip_triangle_indices(tiras: list[npt.NDArray[np.int64]]
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
