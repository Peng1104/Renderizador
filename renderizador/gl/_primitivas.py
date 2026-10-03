"""
Nós X3D das primitivas 3D: Box, Sphere, Cone e Cylinder.
"""

from ._constantes import SEGMENTOS
from ._malhas import box_mesh, cached_mesh, cap_mesh, join_meshes, side_mesh, sphere_mesh
from ._preenchimento import draw_mesh
from ._texturas import optional_mipmaps
from ._tipos import Colors, Malha


def box(size: list[float], colors: Colors, current_texture: list[str] | None = None
        ) -> None:
    """
    Renderiza Box: um paralelepípedo centrado na origem local.

    Parameters
    ----------
    size : list[float]
        Extensões da caixa [x, y, z] ao longo dos eixos locais; cada
        valor deve ser maior que zero.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    current_texture : list[str] or None, optional
        Caminho(s) da textura atual do Appearance, se houver. Cada face
        mostra a textura inteira, com U para a direita e V para cima
        vistos de fora (mapeamento X3D do Box).

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    x, y, z = size
    malha = cached_mesh(("box", x, y, z), lambda: box_mesh((x, y, z)))
    draw_mesh(malha, colors, optional_mipmaps(current_texture))


def sphere(radius: float, colors: Colors, current_texture: list[str] | None = None) -> None:
    """
    Renderiza Sphere: uma esfera centrada na origem local.

    Parameters
    ----------
    radius : float
        Raio da esfera.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    current_texture : list[str] or None, optional
        Caminho(s) da textura atual do Appearance, se houver.
        A textura dá a volta na esfera, com a costura no
        fundo (-Z) e v = 1 no polo norte.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    malha = cached_mesh(("sphere", radius), lambda: sphere_mesh(radius))
    draw_mesh(malha, colors, optional_mipmaps(current_texture))


def cone(bottomRadius: float, height: float, colors: Colors,
         current_texture: list[str] | None = None) -> None:
    """
    Renderiza Cone: um cone centrado na origem local, alinhado ao eixo Y.

    O vértice fica em +height/2 e a base (fechada) em -height/2.

    Parameters
    ----------
    bottomRadius : float
        Raio da base do cone.
    height : float
        Altura do cone.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    current_texture : list[str] or None, optional
        Caminho(s) da textura atual do Appearance, se houver.
        A lateral dá a volta no cone (v = 1 no vértice) e a
        base mostra um recorte circular da textura.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    def construir() -> Malha:
        lateral = side_mesh(0.0, bottomRadius, height, SEGMENTOS, bottomRadius)
        tampa = cap_mesh(bottomRadius, -height / 2, -1.0, SEGMENTOS, 0)
        return join_meshes([lateral, tampa])

    malha = cached_mesh(("cone", bottomRadius, height), construir)
    draw_mesh(malha, colors, optional_mipmaps(current_texture))


def cylinder(radius: float, height: float, colors: Colors,
             current_texture: list[str] | None = None) -> None:
    """
    Renderiza Cylinder: um cilindro centrado na origem local, alinhado ao eixo Y.

    Fechado nas duas extremidades.

    Parameters
    ----------
    radius : float
        Raio da base do cilindro.
    height : float
        Altura do cilindro.
    colors : Colors
        Cores resolvidas do Appearance/Material do nó.
    current_texture : list[str] or None, optional
        Caminho(s) da textura atual do Appearance, se houver.
        A lateral dá a volta no cilindro e as tampas mostram
        um recorte circular da textura.

    Returns
    -------
    None
        A função escreve no buffer de multisample da GL (estado.ms_buffer); não há
        retorno.
    """
    def construir() -> Malha:
        lateral = side_mesh(radius, radius, height, SEGMENTOS, 0.0)
        topo = cap_mesh(radius, height / 2, 1.0, SEGMENTOS, 0)
        baixo = cap_mesh(radius, -height / 2, -1.0, SEGMENTOS, 0)
        return join_meshes([lateral, topo, baixo])

    malha = cached_mesh(("cylinder", radius, height), construir)
    draw_mesh(malha, colors, optional_mipmaps(current_texture))
