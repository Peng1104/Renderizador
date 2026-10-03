"""
Câmera (Viewpoint) e pilha de transformações (Transform).
"""

import math

import numpy as np

from ._estado import estado
from ._matrizes import perspective_matrix, rotation_matrix, scale_matrix, translation_matrix


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
        Atualiza estado.view_matrix e estado.perspective_matrix; não há retorno.
    """
    # Matriz de transformação da câmera (câmera -> mundo): rotação seguida de translação.
    camera_para_mundo = translation_matrix(position) @ rotation_matrix(orientation)

    # A view é a inversa: para uma matriz de rotação + translação, a inversa é a
    # transposta do bloco de rotação seguida da translação negada.
    estado.view_matrix = np.linalg.inv(camera_para_mundo)
    estado.camera_position = np.asarray(position, dtype=np.float64)

    aspect = estado.width / estado.height

    # O fieldOfView do X3D se aplica à menor dimensão da tela sem alteração; a maior
    # dimensão recebe o ângulo mais largo, calculado a partir da razão de aspecto.
    if aspect > 1:  # tela mais larga que alta: a vertical (menor) recebe o fov cru
        fovy = fieldOfView
    else:  # tela mais alta que larga: a horizontal (menor) recebe o fov cru
        fovy = 2 * math.atan(math.tan(fieldOfView / 2) / aspect)

    estado.perspective_matrix = perspective_matrix(fovy, aspect, estado.near, estado.far)


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
        Empilha a matriz resultante em estado.transform_stack.
    """
    t = translation if translation else [0.0, 0.0, 0.0]
    s = scale if scale else [1.0, 1.0, 1.0]
    r = rotation if rotation else [0.0, 0.0, 1.0, 0.0]

    # Ordem de aplicação em um ponto local: primeiro escala, depois rotação,
    # depois translação — ou seja, local_para_pai = T @ R @ S.
    local_para_pai = translation_matrix(t) @ rotation_matrix(r) @ scale_matrix(s)

    local_para_mundo = estado.transform_stack[-1] @ local_para_pai
    estado.transform_stack.append(local_para_mundo)


def transform_out() -> None:
    """
    Sai de um nó Transform: desempilha a matriz de transformação corrente.

    Chamada ao sair de um nó X3D do tipo Transform do grafo de cena, para
    recuperar a matriz de transformação do Transform ancestral.

    Returns
    -------
    None
        Remove o topo de estado.transform_stack.
    """
    estado.transform_stack.pop()
