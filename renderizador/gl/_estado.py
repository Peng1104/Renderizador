"""
Estado mutável compartilhado (matrizes, buffers, luzes, caches) e sua instância única.
"""

import numpy as np
import numpy.typing as npt

from ._tipos import Luz, Malha


class Estado:
    """
    Estado mutável da biblioteca gráfica, compartilhado pelos módulos do pacote.
    """

    width: int  # largura da tela

    height: int # altura da tela

    near: float # plano de corte próximo

    far: float  # plano de corte distante

    # Matriz view (mundo -> câmera) e de projeção perspectiva (câmera -> clip),
    # calculadas em viewpoint(). Identidade até que um Viewpoint seja lido.
    view_matrix: npt.NDArray[np.float64]

    perspective_matrix: npt.NDArray[np.float64]

    # Pilha de matrizes de transformação (objeto -> mundo). O topo (última posição)
    # é a matriz corrente, acumulada dos Transforms ancestrais no grafo de cena.
    transform_stack: list[npt.NDArray[np.float64]]

    ms_buffer: npt.NDArray[np.uint8]

    # Z-buffer: profundidade (Z de NDC, em [-1, 1], near=-1 e far=1) da última
    # subamostra vencedora em cada subamostra de ms_buffer, mesma grade
    # MSAA_AMOSTRAS x MSAA_AMOSTRAS por pixel. Inicializado (e limpo a cada
    # frame) com o valor do plano far (1.0), o mais distante possível, para
    # que qualquer triângulo desenhado vença o teste de profundidade por
    # padrão. Um fragmento só é escrito em ms_buffer se sua profundidade
    # interpolada for <= a já registrada aqui (mais perto da câmera vence),
    # o que resolve oclusão entre triângulos independente da ordem de
    # desenho, ao contrário de simplesmente confiar na ordem de travessia
    # do grafo de cena (um "painter's algorithm" implícito e incorreto para
    # geometria que se cruza).
    depth_buffer: npt.NDArray[np.float64]

    # Cache de texturas já carregadas (chave: caminho em current_texture), para
    # não reler o arquivo de imagem do disco a cada face que a usa.
    texture_cache: dict[str, npt.NDArray[np.uint8]] = {}

    # Cache das cadeias de mipmap já construídas (mesma chave de _texture_cache),
    # para não reconstruir a pirâmide de níveis a cada face que usa a textura.
    mipmap_cache: dict[str, list[npt.NDArray[np.uint8]]] = {}

    # Cache da triangulação em leque de IndexedFaceSet, por id() da lista de
    # índices (coordIndex/colorIndex/texCoordIndex), para não retriangular a
    # cada frame uma malha estática (ver fan_triangulate_cached).
    fan_cache: dict[int, tuple[npt.NDArray[np.int64], npt.NDArray[np.int64],
                                          npt.NDArray[np.int64], npt.NDArray[np.int64]]] = {}

    # Luzes direcionais do frame corrente, em coordenadas de mundo. Esvaziada em
    # clear() e preenchida por navigationInfo (headlight) e
    # directionalLight, que o grafo de cena visita antes das geometrias.
    lights: list[Luz]

    # Posição da câmera em coordenadas de mundo (definida em viewpoint), usada
    # no vetor até o observador do termo especular.
    camera_position: npt.NDArray[np.float64]

    # Instante do primeiro TimeSensor avaliado, de onde todos os ciclos contam
    # (None até lá e após setup). O relógio em si é `_relogio`, no módulo.
    t0: float | None = None

    # Cache das malhas das primitivas, por (tipo, parâmetros), para não
    # retesselar a cada frame (ver cached_mesh).
    mesh_cache: dict[tuple[object, ...], Malha] = {}

    # Instante fixo em que os ciclos dos TimeSensors começam, ou None para contar a partir da
    # primeira avaliação (ver `definir_relogio`).
    origem_fixa: float | None = None


estado = Estado()
