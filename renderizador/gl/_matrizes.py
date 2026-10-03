"""
Matrizes de transformação 4x4 e conversões de rotação (quatérnios).
"""

import math

import numpy as np
import numpy.typing as npt


def translation_matrix(t: list[float]) -> npt.NDArray[np.float64]:
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


def scale_matrix(s: list[float]) -> npt.NDArray[np.float64]:
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


def axis_angle_to_quaternion(rotation: list[float]) -> npt.NDArray[np.float64]:
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


def quaternion_to_rotation_matrix(q: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
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


def rotation_matrix(rotation: list[float]) -> npt.NDArray[np.float64]:
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
    return quaternion_to_rotation_matrix(axis_angle_to_quaternion(rotation))


def perspective_matrix(field_of_view: float, aspect: float, near: float,
                        far: float) -> npt.NDArray[np.float64]:
    """
    Monta a matriz de projeção perspectiva.

    Parameters
    ----------
    field_of_view : float
        Campo de visão vertical, em radianos, já ajustado à razão de
        aspecto (ver viewpoint).
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
