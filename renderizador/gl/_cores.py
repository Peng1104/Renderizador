"""
Arredondamento e conversão de cores para o intervalo 0-255.
"""

import numpy as np
import numpy.typing as npt


def piso(valor: npt.ArrayLike) -> npt.NDArray[np.float64]:
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


def to_rgb8(cor: npt.ArrayLike) -> npt.NDArray[np.int64]:
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
        piso(np.asarray(cor, dtype=np.float64) * 255), 0, 255).astype(np.int64).tolist()
