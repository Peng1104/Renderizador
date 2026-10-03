"""
Nós X3D de luz e ambiente: NavigationInfo, luzes e Fog.
"""

import numpy as np

from ._estado import estado
from ._projecao import to_world


def navigationInfo(headlight: bool) -> None:
    """
    Processa NavigationInfo: características do avatar e do modo de visualização.

    Com `headlight` ligado, acrescenta às luzes do frame uma luz direcional
    branca presa à câmera. Deve ser chamada depois de `viewpoint`.

    Parameters
    ----------
    headlight : bool
        Se True, o visualizador deve acender uma luz direcional que
        sempre aponta na direção em que o usuário está olhando.

    Returns
    -------
    None
        Acrescenta a luz da câmera a estado.lights quando `headlight` é True;
        não há retorno.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/navigation.html#NavigationInfo
    # O campo do headlight especifica se um navegador deve acender um luz direcional que
    # sempre aponta na direção que o usuário está olhando. Definir este campo como TRUE
    # faz com que o visualizador forneça sempre uma luz do ponto de vista do usuário.
    # A luz headlight deve ser direcional, ter intensidade = 1, cor = (1 1 1),
    # ambientIntensity = 0,0 e direção = (0 0 −1).

    if headlight:
        # A direção (0, 0, -1) do headlight está no espaço da câmera; a rotação
        # da view é ortogonal, então a inversa dela (camera -> mundo) é a transposta.
        direcao = estado.view_matrix[:3, :3].T @ np.array([0.0, 0.0, -1.0])
        estado.lights.append({"direcao": direcao, "cor": np.ones(3),
                          "intensidade": 1.0, "ambiente": 0.0})


def directionalLight(ambientIntensity: float, color: list[float], intensity: float,
                     direction: list[float]) -> None:
    """
    Processa DirectionalLight: uma luz direcional (raios paralelos).

    A direção é levada ao espaço de mundo pela transformação corrente, de
    modo que luzes dentro de um Transform giram com ele.

    Parameters
    ----------
    ambientIntensity : float
        Contribuição de luz ambiente da fonte, em [0, 1].
    color : list[float]
        Cor da luz [r, g, b], cada canal em [0, 1].
    intensity : float
        Intensidade (brilho) da luz.
    direction : list[float]
        Vetor de direção [x, y, z] da luz, no sistema de coordenadas
        local.

    Returns
    -------
    None
        Acrescenta a luz a estado.lights; não há retorno.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#DirectionalLight
    # Define uma fonte de luz direcional que ilumina ao longo de raios paralelos
    # em um determinado vetor tridimensional. Possui os campos básicos ambientIntensity,
    # cor, intensidade. O campo de direção especifica o vetor de direção da iluminação
    # que emana da fonte de luz no sistema de coordenadas local. A luz é emitida ao
    # longo de raios paralelos de uma distância infinita.

    _, direcao = to_world(np.zeros((1, 3)), np.array([direction], dtype=np.float64))
    assert direcao is not None
    estado.lights.append({"direcao": direcao[0], "cor": np.asarray(color, dtype=np.float64),
                      "intensidade": intensity, "ambiente": ambientIntensity})


def pointLight(ambientIntensity: float, color: list[float], intensity: float,
              location: list[float]) -> None:
    """
    Processa PointLight: uma luz pontual omnidirecional.

    Ainda não implementado (stub) — ver comentário abaixo.

    Parameters
    ----------
    ambientIntensity : float
        Contribuição de luz ambiente da fonte, em [0, 1].
    color : list[float]
        Cor da luz [r, g, b], cada canal em [0, 1].
    intensity : float
        Intensidade (brilho) da luz.
    location : list[float]
        Posição [x, y, z] da luz, no sistema de coordenadas local.

    Returns
    -------
    None
        Não há retorno.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#PointLight
    # Fonte de luz pontual em um local 3D no sistema de coordenadas local. Uma fonte
    # de luz pontual emite luz igualmente em todas as direções; ou seja, é omnidirecional.
    # Possui os campos básicos ambientIntensity, cor, intensidade. Um nó PointLight ilumina
    # a geometria em um raio de sua localização. O campo do raio deve ser maior ou igual a
    # zero. A iluminação do nó PointLight diminui com a distância especificada.

    # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
    print("PointLight : ambientIntensity = {0}".format(ambientIntensity))
    print("PointLight : color = {0}".format(color)) # imprime no terminal
    print("PointLight : intensity = {0}".format(intensity)) # imprime no terminal
    print("PointLight : location = {0}".format(location)) # imprime no terminal


def fog(visibilityRange: float, color: list[float]) -> None:
    """
    Processa Fog: névoa que mistura objetos distantes com uma cor constante.

    Ainda não implementado (stub) — ver comentário abaixo.

    Parameters
    ----------
    visibilityRange : float
        Distância, no sistema de coordenadas local, na qual os objetos
        ficam totalmente obscurecidos pela névoa.
    color : list[float]
        Cor da névoa [r, g, b], cada canal em [0, 1].

    Returns
    -------
    None
        Não há retorno.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/environmentalEffects.html#Fog
    # O nó Fog fornece uma maneira de simular efeitos atmosféricos combinando objetos
    # com a cor especificada pelo campo de cores com base nas distâncias dos
    # vários objetos ao visualizador. A visibilidadeRange especifica a distância no
    # sistema de coordenadas local na qual os objetos são totalmente obscurecidos
    # pela névoa. Os objetos localizados fora de visibilityRange do visualizador são
    # desenhados com uma cor de cor constante. Objetos muito próximos do visualizador
    # são muito pouco misturados com a cor do nevoeiro.

    # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
    print("Fog : color = {0}".format(color)) # imprime no terminal
    print("Fog : visibilityRange = {0}".format(visibilityRange))
