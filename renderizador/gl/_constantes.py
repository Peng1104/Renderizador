"""
Constantes de configuração da biblioteca gráfica.
"""

import numpy as np
import numpy.typing as npt

# 4x MSAA: grade de MSAA_AMOSTRAS x MSAA_AMOSTRAS subamostras por pixel (2x2=4).
# ms_buffer guarda, para cada pixel e cada subamostra, a última cor escrita
# nela (por ordem de desenho, como um MSAA de verdade faria com os
# fragmentos que cobrem cada subamostra). O resolve (média das subamostras
# de cada pixel) só acontece uma vez por frame, em resolve_multisample(),
# depois que toda a cena já foi desenhada, por isso o anti-aliasing não
# sofre do problema de "blend duplicado" que geometria adjacente causaria
# se cada primitivo misturasse sua cobertura parcial direto no framebuffer
# final.
MSAA_AMOSTRAS: int = 2

# Quantidade mínima de triângulos de um draw call a partir da qual vale a
# pena pré-calcular arestas/bbox em lote (batch_edges_and_bbox): abaixo
# disso, o custo fixo de montar os arrays em lote (stack, roll, listas de
# retorno) supera a economia de não recalcular por triângulo, medido em
# bound500.x3d (500 draw calls de 1 triângulo cada, ver prepare_edges_and_bbox).
LOTE_MINIMO: int = 8

# Resolução da tesselação das primitivas curvas: fatias ao redor do eixo
# (esfera, cone, cilindro) e faixas de latitude da esfera.
SEGMENTOS: int = 48

SPHERE_FAIXAS: int = 24

# UV dos 4 cantos de cada face do Box, na ordem de box_mesh (canto
# inferior esquerdo, inferior direito, superior direito, superior esquerdo,
# vistos de fora): a textura inteira em cada face.
BOX_FACE_UV: npt.NDArray[np.float64] = np.array(
    [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
