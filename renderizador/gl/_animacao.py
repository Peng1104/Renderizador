"""
TimeSensor e interpoladores (spline de posição e orientação).
"""

import math
import time
from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from ._estado import estado
from ._matrizes import axis_angle_to_quaternion

# Relógio dos TimeSensors, em segundos. Fica no módulo, e não na classe, para
# que testes possam fixar o instante renderizado chamando `definir_relogio`.
_relogio: Callable[[], float] = time.time


def definir_relogio(relogio: Callable[[], float], origem: float | None = None) -> None:
    """
    Troca o relógio dos TimeSensors, para renderizar a cena num instante conhecido.

    Parameters
    ----------
    relogio : Callable[[], float]
        Função sem argumentos que devolve o instante atual, em segundos.
    origem : float or None, optional
        Instante em que os ciclos começam. Com `origem=0.0` e um relógio que
        devolve sempre T, um único frame sai no instante T da animação. Se
        None, os ciclos contam a partir da primeira avaliação de um TimeSensor.
    """
    global _relogio
    _relogio = relogio
    estado.origem_fixa = origem


def timeSensor(cycleInterval: float, loop: bool) -> float:
    """
    Gera eventos conforme o tempo passa (TimeSensor).

    Parameters
    ----------
    cycleInterval : float
        Duração de um ciclo do TimeSensor, em segundos. Deve ser maior
        que zero.
    loop : bool
        Se True, o TimeSensor continua a execução no próximo ciclo ao
        final de cada ciclo; se False, a execução é encerrada.

    Returns
    -------
    float
        Fração de tempo decorrida no ciclo atual, em [0, 1) com `loop`.
        Sem `loop`, cresce até 1.0 ao fim do primeiro ciclo e fica lá.
        O tempo conta a partir da primeira avaliação de um TimeSensor.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/time.html#TimeSensor
    # Os nós TimeSensor podem ser usados para muitas finalidades, incluindo:
    # Condução de simulações e animações contínuas; Controlar atividades periódicas;
    # iniciar eventos de ocorrência única, como um despertador;
    # Se, no final de um ciclo, o valor do loop for FALSE, a execução é encerrada.
    # Por outro lado, se o loop for TRUE no final de um ciclo, um nó dependente do
    # tempo continua a execução no próximo ciclo. O ciclo de um nó TimeSensor dura
    # cycleInterval segundos. O valor de cycleInterval deve ser maior que zero.

    # Deve retornar a fração de tempo passada em fraction_changed
    agora = _relogio()

    if estado.t0 is None:
        estado.t0 = agora

    decorrido = agora - estado.t0
    
    if loop:
        return (decorrido % cycleInterval) / cycleInterval
    
    return min(decorrido / cycleInterval, 1.0)


def key_segment(key: list[float], fracao: float) -> tuple[int, float]:
    """
    Localiza o intervalo de chaves que contém uma fração.

    Parameters
    ----------
    key : list[float]
        Chaves em ordem crescente, com ao menos duas.
    fracao : float
        Fração dentro de `[key[0], key[-1]]`.

    Returns
    -------
    int
        Índice `i` do início do intervalo `[key[i], key[i + 1]]`.
    float
        Posição de `fracao` dentro do intervalo, em [0, 1].
    """
    chaves = np.asarray(key, dtype=np.float64)
    i = int(np.clip(np.searchsorted(chaves, fracao, side="right") - 1, 0, len(chaves) - 2))
    return i, (fracao - chaves[i]) / max(chaves[i + 1] - chaves[i], 1e-12)


def spline_derivatives(chaves: npt.NDArray[np.float64], valores: npt.NDArray[np.float64],
                        fechado: bool) -> npt.NDArray[np.float64]:
    """
    Calcula a derivada (Catmull-Rom) do spline em cada chave.

    É a diferença central em relação às chaves vizinhas, que para chaves
    igualmente espaçadas dá a tangente $(v_{i+1} - v_{i-1}) / 2$ da spec.
    Num spline aberto os extremos têm derivada nula. Num fechado, os
    vizinhos dão a volta: o anterior à primeira chave é a penúltima, e o
    posterior à última é a segunda.

    Parameters
    ----------
    chaves : NDArray[float64]
        Chaves, array (N,).
    valores : NDArray[float64]
        Vetores 3D de cada chave, array (N, 3).
    fechado : bool
        Se o spline é fechado (primeiro e último valores idênticos).

    Returns
    -------
    NDArray[float64]
        Derivada em relação à chave, array (N, 3).
    """
    derivadas = np.zeros_like(valores)
    if not fechado:
        derivadas[1:-1] = ((valores[2:] - valores[:-2])
                           / np.maximum(chaves[2:] - chaves[:-2], 1e-12)[:, None])
        return derivadas

    mais, menos = np.roll(valores, -1, axis=0), np.roll(valores, 1, axis=0)
    k_mais, k_menos = np.roll(chaves, -1), np.roll(chaves, 1)
    menos[0], k_menos[0] = valores[-2], chaves[0] - (chaves[-1] - chaves[-2])
    mais[-1], k_mais[-1] = valores[1], chaves[-1] + (chaves[1] - chaves[0])
    return (mais - menos) / np.maximum(k_mais - k_menos, 1e-12)[:, None]


def splinePositionInterpolator(set_fraction: float, key: list[float], keyValue: list[float],
                               closed: bool) -> list[float]:
    """
    Interpola não linearmente entre uma lista de vetores 3D.

    Usa a spline cúbica de Hermite com tangentes Catmull-Rom (ver
    `spline_derivatives`). Fora do intervalo das chaves, mantém o
    primeiro ou o último valor.

    Parameters
    ----------
    set_fraction : float
        Fração a ser interpolada, em [0, 1].
    key : list[float]
        Chaves (quadros-chave) correspondentes a `keyValue`.
    keyValue : list[float]
        Vetores 3D a interpolar, no formato [x0, y0, z0, x1, y1, z1, ...] —
        um vetor por chave em `key`.
    closed : bool
        Se True, trata a malha de chaves como fechada, com uma transição
        da última chave para a primeira (ignorado se os keyValues da
        primeira e da última chave não forem idênticos).

    Returns
    -------
    list[float]
        Vetor 3D interpolado [x, y, z] para `set_fraction`.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/interpolators.html#SplinePositionInterpolator
    # Interpola não linearmente entre uma lista de vetores 3D. O campo keyValue possui
    # uma lista com os valores a serem interpolados, key possui uma lista respectiva de chaves
    # dos valores em keyValue, a fração a ser interpolada vem de set_fraction que varia de
    # zeroa a um. O campo keyValue deve conter exatamente tantos vetores 3D quanto os
    # quadros-chave no key. O campo closed especifica se o interpolador deve tratar a malha
    # como fechada, com uma transições da última chave para a primeira chave. Se os keyValues
    # na primeira e na última chave não forem idênticos, o campo closed será ignorado.
    valores = np.asarray(keyValue, dtype=np.float64).reshape(-1, 3)
    if len(key) == 0 or len(valores) != len(key):
        return [0.0, 0.0, 0.0]
    if len(key) == 1 or set_fraction <= key[0]:
        return valores[0].tolist()
    if set_fraction >= key[-1]:
        return valores[-1].tolist()

    chaves = np.asarray(key, dtype=np.float64)
    fechado = closed and len(key) > 2 and bool(np.allclose(valores[0], valores[-1]))
    derivadas = spline_derivatives(chaves, valores, fechado)

    i, t = key_segment(key, set_fraction)
    dt = chaves[i + 1] - chaves[i]
    h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
    h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2

    value_changed = (h00 * valores[i] + h10 * dt * derivadas[i]
                     + h01 * valores[i + 1] + h11 * dt * derivadas[i + 1])
    return value_changed.tolist()


def slerp(q0: npt.NDArray[np.float64], q1: npt.NDArray[np.float64], t: float
           ) -> npt.NDArray[np.float64]:
    """
    Interpola esfericamente (slerp) entre dois quatérnios unitários, pelo caminho mais curto.

    Parameters
    ----------
    q0, q1 : NDArray[float64]
        Quatérnios unitários [w, x, y, z].
    t : float
        Posição entre `q0` (0) e `q1` (1).

    Returns
    -------
    NDArray[float64]
        Quatérnio unitário interpolado. Se os quatérnios são quase
        paralelos, usa interpolação linear normalizada, que evita a
        divisão por um seno quase nulo.
    """
    cosseno = float(np.dot(q0, q1))
    if cosseno < 0:  # q e -q são a mesma rotação; escolhe o caminho curto
        q1, cosseno = -q1, -cosseno

    if cosseno > 0.9995:
        q = q0 + t * (q1 - q0)
        return q / np.linalg.norm(q)

    angulo = math.acos(cosseno)
    return (math.sin((1 - t) * angulo) * q0 + math.sin(t * angulo) * q1) / math.sin(angulo)


def quaternion_to_axis_angle(q: npt.NDArray[np.float64]) -> list[float]:
    """
    Converte um quatérnio unitário [w, x, y, z] para eixo e ângulo [x, y, z, t].

    Parameters
    ----------
    q : NDArray[float64]
        Quatérnio unitário [w, x, y, z].

    Returns
    -------
    list[float]
        Rotação [x, y, z, t], com t em radianos. Para rotação nula
        devolve [0, 0, 1, 0].
    """
    w = float(np.clip(q[0], -1.0, 1.0))
    seno_metade = math.sqrt(1.0 - w * w)
    if seno_metade < 1e-9:
        return [0.0, 0.0, 1.0, 0.0]
    eixo = q[1:] / seno_metade
    return [*eixo.tolist(), 2 * math.acos(w)]


def orientationInterpolator(set_fraction: float, key: list[float],
                            keyValue: list[float]) -> list[float]:
    """
    Interpola entre uma lista de valores de rotação específicos.

    Converte cada rotação para quatérnio e faz slerp pelo caminho mais
    curto (ver `slerp`). Fora do intervalo das chaves, mantém a
    primeira ou a última rotação.

    Parameters
    ----------
    set_fraction : float
        Fração a ser interpolada, em [0, 1].
    key : list[float]
        Chaves (quadros-chave) correspondentes a `keyValue`.
    keyValue : list[float]
        Rotações a interpolar, no formato [x0, y0, z0, t0, x1, y1, z1, t1,
        ...] — uma rotação (eixo + ângulo) por chave em `key`.

    Returns
    -------
    list[float]
        Rotação interpolada [x, y, z, t] para `set_fraction`.
    """
    # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/interpolators.html#OrientationInterpolator
    # Interpola rotações são absolutas no espaço do objeto e, portanto, não são cumulativas.
    # Uma orientação representa a posição final de um objeto após a aplicação de uma rotação.
    # Um OrientationInterpolator interpola entre duas orientações calculando o caminho mais
    # curto na esfera unitária entre as duas orientações. A interpolação é linear em
    # comprimento de arco ao longo deste caminho. Os resultados são indefinidos se as duas
    # orientações forem diagonalmente opostas. O campo keyValue possui uma lista com os
    # valores a serem interpolados, key possui uma lista respectiva de chaves
    # dos valores em keyValue, a fração a ser interpolada vem de set_fraction que varia de
    # zeroa a um. O campo keyValue deve conter exatamente tantas rotações 3D quanto os
    # quadros-chave no key.
    rotacoes = np.asarray(keyValue, dtype=np.float64).reshape(-1, 4)
    if len(key) == 0 or len(rotacoes) != len(key):
        return [0.0, 0.0, 1.0, 0.0]
    if len(key) == 1 or set_fraction <= key[0]:
        return rotacoes[0].tolist()
    if set_fraction >= key[-1]:
        return rotacoes[-1].tolist()

    i, t = key_segment(key, set_fraction)
    q0 = axis_angle_to_quaternion(rotacoes[i].tolist())
    q1 = axis_angle_to_quaternion(rotacoes[i + 1].tolist())
    return quaternion_to_axis_angle(slerp(q0, q1, t))
