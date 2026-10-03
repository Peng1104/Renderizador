"""
Modelo de iluminação de Phong.
"""

import numpy as np
import numpy.typing as npt

from ._estado import estado
from ._tipos import Colors


def shade(pos: npt.NDArray[np.float64], normal: npt.NDArray[np.float64],
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
