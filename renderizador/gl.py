#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# pylint: disable=invalid-name

"""
Biblioteca Gráfica / Graphics Library.

Desenvolvido por: Lucas Hix
Disciplina: Computação Gráfica
Data: 19/08/2026
"""

import math  # Funções matemáticas
import time  # Para operações com tempo
from typing import ClassVar, TypedDict

import gpu  # Simula os recursos de uma GPU
import numpy as np  # Biblioteca do Numpy
import numpy.typing as npt


class Colors(TypedDict):
    """
    Conjunto de cores resolvidas a partir de um nó Appearance/Material.
    """

    diffuseColor: list[float]
    emissiveColor: list[float]
    specularColor: list[float]
    shininess: float
    transparency: float
    ambientIntensity: float

class Pointo2D:
    """
    Classe que representa um ponto 2D.
    """

    x: int
    y: int

class GL:
    """
    Classe que representa a biblioteca gráfica (Graphics Library).
    """

    width: ClassVar[int]  # largura da tela
    height: ClassVar[int] # altura da tela
    near: ClassVar[float] # plano de corte próximo
    far: ClassVar[float]  # plano de corte distante

    # Matriz view (mundo -> câmera) e de projeção perspectiva (câmera -> clip),
    # calculadas em GL.viewpoint(). Identidade até que um Viewpoint seja lido.
    view_matrix: ClassVar[npt.NDArray[np.float64]]
    perspective_matrix: ClassVar[npt.NDArray[np.float64]]

    # Pilha de matrizes de transformação (objeto -> mundo). O topo (última posição)
    # é a matriz corrente, acumulada dos Transforms ancestrais no grafo de cena.
    transform_stack: ClassVar[list[npt.NDArray[np.float64]]]

    @staticmethod
    def setup(width: int, height: int, near: float = 0.01, far: float = 1000) -> None:
        """
        Definr parametros para câmera de razão de aspecto, plano próximo e distante.
        """
        GL.width = width
        GL.height = height
        GL.near = near
        GL.far = far
        GL.view_matrix = np.identity(4)
        GL.perspective_matrix = np.identity(4)
        GL.transform_stack = [np.identity(4)]

    @staticmethod
    def _translation_matrix(t: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de translação.
        """
        m = np.identity(4)
        m[:3, 3] = t
        return m

    @staticmethod
    def _scale_matrix(s: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de escala.
        """
        m = np.identity(4)
        m[0, 0], m[1, 1], m[2, 2] = s
        return m

    @staticmethod
    def _axis_angle_to_quaternion(rotation: list[float]) -> npt.NDArray[np.float64]:
        """
        Converte eixo [x, y, z] e ângulo t (radianos) num quatérnio unitário.

        Segue a regra da mão direita. Retorna [w, x, y, z], com w=1 (identidade)
        quando o eixo é nulo.
        """
        eixo = np.asarray(rotation[:3], dtype=np.float64)
        norma = np.linalg.norm(eixo)

        if norma == 0:
            return np.array([1.0, 0.0, 0.0, 0.0])

        eixo = eixo / norma
        t = rotation[3]
        metade = t / 2
        return np.array([math.cos(metade), *(eixo * math.sin(metade))])

    @staticmethod
    def _quaternion_to_rotation_matrix(q: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de rotação a partir de um quatérnio unitário [w, x, y, z].
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

    @staticmethod
    def _rotation_matrix(rotation: list[float]) -> npt.NDArray[np.float64]:
        """
        Monta a matriz 4x4 homogênea de rotação a partir de eixo e ângulo.

        Eixo [x, y, z] e ângulo t (radianos), seguindo a regra da mão direita.
        """
        return GL._quaternion_to_rotation_matrix(GL._axis_angle_to_quaternion(rotation))

    @staticmethod
    def _perspective_matrix(field_of_view: float, aspect: float, near: float,
                            far: float) -> npt.NDArray[np.float64]:
        """
        Monta a matriz de projeção perspectiva.

        Recebe o campo de visão vertical (já ajustado à razão de aspecto),
        a razão de aspecto e os planos de corte próximo e distante.
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

    # Matrizes de reflexão e rotação usadas para gerar
    # os 8 octantes simétricos de um círculo a partir de um único octante calculado.
    _CIRCLE_OCTANT_REFLECTIONS: ClassVar[npt.NDArray[np.float64]] = np.array([
        [[1, 0], [0, 1]], [[0, 1], [1, 0]],
        [[0, -1], [1, 0]], [[-1, 0], [0, 1]],
        [[-1, 0], [0, -1]], [[0, -1], [-1, 0]],
        [[0, 1], [-1, 0]], [[1, 0], [0, -1]],
    ], dtype=np.float64)

    @staticmethod
    def _round(valor: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """
        Converte coordenada contínua para índice de pixel.

        Cada pixel n cobre o intervalo [n, n+1), entao o indice correto e o
        piso da coordenada.
        """
        return np.floor(np.asarray(valor, dtype=np.float64))

    @staticmethod
    def _to_rgb8(cor: list[float]) -> npt.NDArray[np.int64]:
        """
        Converte uma cor X3D (0 a 1) para o intervalo 0-255 usado pelo matplotlib.
        """
        return np.clip(
            GL._round(np.asarray(cor, dtype=np.float64) * 255), 0, 255).astype(np.int64).tolist()

    @staticmethod
    def _draw_points(xs: npt.NDArray[np.int64], ys: npt.NDArray[np.int64],
                     cor: list[int] | npt.NDArray[np.int64]) -> None:
        """
        Desenha um conjunto de pixels, descartando os que caem fora da tela.
        """
        dentro = (xs >= 0) & (xs < GL.width) & (ys >= 0) & (ys < GL.height)

        for x, y in zip(xs[dentro].tolist(), ys[dentro].tolist()):
            gpu.GPU.draw_pixel([x, y], gpu.PixelFormat.RGB8, cor)

    @staticmethod
    def _line_points(x0: float, y0: float, x1: float,
                     y1: float) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        """
        Interpola os pontos de uma linha entre dois pontos.

        (bremsenham, mas usando numpy para vetorização)
        """
        steps = max(round(abs(x1 - x0)), round(abs(y1 - y0)), 1)
        # Normaliza o numero de passos
        t = np.linspace(0.0, 1.0, steps + 1)
        xs = GL._round(x0 + t * (x1 - x0)).astype(np.int64)
        ys = GL._round(y0 + t * (y1 - y0)).astype(np.int64)
        return xs, ys

    @staticmethod
    def _fill_triangle(x0: float, y0: float, x1: float, y1: float,
                       x2: float, y2: float, cor: npt.NDArray[np.int64]) -> None:
        """
        Preenche um triângulo 2D.

        Usa funções de aresta calculadas por multiplicação de matrizes.
        """
        min_x = max(0, math.floor(min(x0, x1, x2)))
        max_x = min(GL.width - 1, math.ceil(max(x0, x1, x2)))
        min_y = max(0, math.floor(min(y0, y1, y2)))
        max_y = min(GL.height - 1, math.ceil(max(y0, y1, y2)))

        if min_x > max_x or min_y > max_y:
            return

        # Cada aresta (a -> b) define uma reta cuja função de aresta é
        # edge(p) = dy*px - dx*py + (ay*dx - ax*dy), com [dx, dy] = b - a.
        verts = np.array([
            [x0, y0],
            [x1, y1],
            [x2, y2]
        ], dtype=np.float64)

        a = verts
        b = np.roll(verts, -1, axis=0) # Rotaciona
        d = b - a

        arestas = np.column_stack([
            d[:,  1],                               # dy
            -d[:, 0],                               # -dx
            a[:,  1] * d[:, 0] - a[:, 0] * d[:, 1], # (ay*dx - ax*dy)
        ])

        retangulo_limitador  = np.meshgrid(
            np.arange(min_x, max_x + 1),
            np.arange(min_y, max_y + 1)
        )
        px, py = retangulo_limitador

        pontos = np.stack([px.ravel(), py.ravel(), np.ones(px.size)])

        baricentro = arestas @ pontos

        # Verifica se o ponto esta dentro do triangulo
        dentro = np.all(baricentro >= 0, axis=0) | np.all(baricentro <= 0, axis=0)

        # Pinta
        GL._draw_points(px.ravel()[dentro], py.ravel()[dentro], cor)

    @staticmethod
    def polypoint2D(point: list[float], colors: Colors) -> None:
        """
        Função usada para renderizar Polypoint2D.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        pontos = GL._round(np.asarray(point).reshape(-1, 2)).astype(np.int64)

        GL._draw_points(pontos[:, 0], pontos[:, 1], cor)

    @staticmethod
    def polyline2D(lineSegments: list[float], colors: Colors) -> None:
        """
        Função usada para renderizar Polyline2D.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        pontos = np.asarray(lineSegments, dtype=np.float64).reshape(-1, 2)

        for (x0, y0), (x1, y1) in zip(pontos[:-1].tolist(), pontos[1:].tolist()):
            xs, ys = GL._line_points(x0, y0, x1, y1)
            GL._draw_points(xs, ys, cor)

    @staticmethod
    def circle2D(radius: float, colors: Colors) -> None:
        """
        Função usada para renderizar Circle2D.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])
        r = round(radius)

        # Sem For: Calcula octante aplica as matrizes identidade e
        # gera o circulo completo 

        # Calcula um único octante (0 <= x <= y)
        xs_octant = np.arange(0, int(r / math.sqrt(2)) + 1, dtype=np.float64)
        ys_octant = GL._round(np.sqrt(r ** 2 - xs_octant ** 2))

        octant = np.stack([xs_octant, ys_octant], axis=1)  # (N, 2)

        # Aplica as 8 matrizes de reflexão para gerar todos os octantes do círculo
        all_points = np.concatenate([octant @ m.T for m in GL._CIRCLE_OCTANT_REFLECTIONS])

        GL._draw_points(all_points[:, 0].astype(np.int64), all_points[:, 1].astype(np.int64), cor)

    @staticmethod
    def triangleSet2D(vertices: list[float], colors: Colors) -> None:
        """
        Função usada para renderizar TriangleSet2D.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])

        for i in range(0, len(vertices) - 5, 6):

            GL._fill_triangle(vertices[i], vertices[i + 1],
                              vertices[i + 2], vertices[i + 3],
                              vertices[i + 4], vertices[i + 5], cor)


    @staticmethod
    def triangleSet(point: list[float], colors: Colors) -> None:
        """
        Função usada para renderizar TriangleSet.
        """
        cor = GL._to_rgb8(colors["emissiveColor"])

        # Matriz completa: objeto -> mundo -> câmera -> clip.
        transformacao = GL.perspective_matrix @ GL.view_matrix @ GL.transform_stack[-1]

        pontos = np.asarray(point, dtype=np.float64).reshape(-1, 3)
        homogeneos = np.hstack([pontos, np.ones((pontos.shape[0], 1))])

        clip = (transformacao @ homogeneos.T).T
        # Divisão de perspectiva: normaliza pelo componente w.
        ndc = clip[:, :3] / clip[:, 3:4]

        # Mapeia de NDC ([-1, 1]) para coordenadas de tela (eixo y invertido).
        tela_x = (ndc[:, 0] + 1) / 2 * GL.width
        tela_y = (1 - ndc[:, 1]) / 2 * GL.height

        for i in range(0, len(tela_x) - 2, 3):
            GL._fill_triangle(tela_x[i], tela_y[i],
                              tela_x[i + 1], tela_y[i + 1],
                              tela_x[i + 2], tela_y[i + 2], cor)

    @staticmethod
    def viewpoint(position: list[float], orientation: list[float], fieldOfView: float) -> None:
        """
        Função usada para renderizar (na verdade coletar os dados) de Viewpoint.
        """
        # Matriz de transformação da câmera (câmera -> mundo): rotação seguida de translação.
        camera_para_mundo = GL._translation_matrix(position) @ GL._rotation_matrix(orientation)

        # A view é a inversa: para uma matriz de rotação + translação, a inversa é a
        # transposta do bloco de rotação seguida da translação negada.
        GL.view_matrix = np.linalg.inv(camera_para_mundo)

        aspect = GL.width / GL.height

        # O fieldOfView do X3D se aplica à menor dimensão da tela sem alteração; a maior
        # dimensão recebe o ângulo mais largo, calculado a partir da razão de aspecto.
        if aspect > 1:  # tela mais larga que alta: a vertical (menor) recebe o fov cru
            fovy = fieldOfView
        else:  # tela mais alta que larga: a horizontal (menor) recebe o fov cru
            fovy = 2 * math.atan(math.tan(fieldOfView / 2) / aspect)

        GL.perspective_matrix = GL._perspective_matrix(fovy, aspect, GL.near, GL.far)

    @staticmethod
    def transform_in(translation: list[float], scale: list[float], rotation: list[float]) -> None:
        """
        Função usada para renderizar (na verdade coletar os dados) de Transform.
        """
        # A função transform_in será chamada quando se entrar em um nó X3D do tipo Transform
        # do grafo de cena. Os valores passados são a escala em um vetor [x, y, z]
        # indicando a escala em cada direção, a translação [x, y, z] nas respectivas
        # coordenadas e finalmente a rotação por [x, y, z, t] sendo definida pela rotação
        # do objeto ao redor do eixo x, y, z por t radianos, seguindo a regra da mão direita.
        # Quando se entrar em um nó transform se deverá salvar a matriz de transformação dos
        # modelos do mundo para depois potencialmente usar em outras chamadas.
        # Quando se usa Transforms dentro de outros Transforms, a matriz corrente acumula
        # sobre o topo da pilha, que guarda a transformação do Transform ancestral.

        t = translation if translation else [0.0, 0.0, 0.0]
        s = scale if scale else [1.0, 1.0, 1.0]
        r = rotation if rotation else [0.0, 0.0, 1.0, 0.0]

        # Ordem de aplicação em um ponto local: primeiro escala, depois rotação,
        # depois translação — ou seja, local_para_pai = T @ R @ S.
        local_para_pai = GL._translation_matrix(t) @ GL._rotation_matrix(r) @ GL._scale_matrix(s)

        local_para_mundo = GL.transform_stack[-1] @ local_para_pai
        GL.transform_stack.append(local_para_mundo)

    @staticmethod
    def transform_out() -> None:
        """
        Função usada para renderizar (na verdade coletar os dados) de Transform.
        """
        # A função transform_out será chamada quando se sair em um nó X3D do tipo Transform do
        # grafo de cena. Não são passados valores, porém quando se sai de um nó transform se
        # deverá recuperar a matriz de transformação dos modelos do mundo da estrutura de
        # pilha implementada.

        GL.transform_stack.pop()

    @staticmethod
    def triangleStripSet(point: list[float], stripCount: list[int], colors: Colors) -> None:
        """
        Função usada para renderizar TriangleStripSet.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/rendering.html#TriangleStripSet
        # A função triangleStripSet é usada para desenhar tiras de triângulos interconectados,
        # você receberá as coordenadas dos pontos no parâmetro point, esses pontos são uma
        # lista de pontos x, y, e z sempre na ordem. Assim point[0] é o valor da coordenada x
        # do primeiro ponto, point[1] o valor y do primeiro ponto, point[2] o valor z da
        # coordenada z do primeiro ponto. Já point[3] é a coordenada x do segundo ponto e assim
        # por diante. No TriangleStripSet a quantidade de vértices a serem usados é informado
        # em uma lista chamada stripCount (perceba que é uma lista). Ligue os vértices na ordem,
        # primeiro triângulo será com os vértices 0, 1 e 2, depois serão os vértices 1, 2 e 3,
        # depois 2, 3 e 4, e assim por diante. Cuidado com a orientação dos vértices, ou seja,
        # todos no sentido horário ou todos no sentido anti-horário, conforme especificado.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("TriangleStripSet : pontos = {0} ".format(point), end='')
        for i, strip in enumerate(stripCount):
            print("strip[{0}] = {1} ".format(i, strip), end='')
        print("")
        print("TriangleStripSet : colors = {0}".format(colors)) # imprime no terminal as cores

        # Exemplo de desenho de um pixel branco na coordenada 10, 10
        gpu.GPU.draw_pixel([10, 10], gpu.PixelFormat.RGB8, [255, 255, 255])  # altera pixel

    @staticmethod
    def indexedTriangleStripSet(point: list[float], index: list[int], colors: Colors) -> None:
        """
        Função usada para renderizar IndexedTriangleStripSet.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/rendering.html#IndexedTriangleStripSet
        # A função indexedTriangleStripSet é usada para desenhar tiras de triângulos
        # interconectados, você receberá as coordenadas dos pontos no parâmetro point, esses
        # pontos são uma lista de pontos x, y, e z sempre na ordem. Assim point[0] é o valor
        # da coordenada x do primeiro ponto, point[1] o valor y do primeiro ponto, point[2]
        # o valor z da coordenada z do primeiro ponto. Já point[3] é a coordenada x do
        # segundo ponto e assim por diante. No IndexedTriangleStripSet uma lista informando
        # como conectar os vértices é informada em index, o valor -1 indica que a lista
        # acabou. A ordem de conexão será de 3 em 3 pulando um índice. Por exemplo: o
        # primeiro triângulo será com os vértices 0, 1 e 2, depois serão os vértices 1, 2 e 3,
        # depois 2, 3 e 4, e assim por diante. Cuidado com a orientação dos vértices, ou seja,
        # todos no sentido horário ou todos no sentido anti-horário, conforme especificado.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("IndexedTriangleStripSet : pontos = {0}, index = {1}".format(point, index))
        print("IndexedTriangleStripSet : colors = {0}".format(colors)) # imprime as cores

        # Exemplo de desenho de um pixel branco na coordenada 10, 10
        gpu.GPU.draw_pixel([10, 10], gpu.PixelFormat.RGB8, [255, 255, 255])  # altera pixel

    @staticmethod
    def indexedFaceSet(coord: list[float], coordIndex: list[int], colorPerVertex: bool,
                       color: list[float], colorIndex: list[int],
                       texCoord: list[float], texCoordIndex: list[int],
                       colors: Colors, current_texture: list[str]) -> None:
        """
        Função usada para renderizar IndexedFaceSet.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#IndexedFaceSet
        # A função indexedFaceSet é usada para desenhar malhas de triângulos. Ela funciona de
        # forma muito simular a IndexedTriangleStripSet porém com mais recursos.
        # Você receberá as coordenadas dos pontos no parâmetro cord, esses
        # pontos são uma lista de pontos x, y, e z sempre na ordem. Assim coord[0] é o valor
        # da coordenada x do primeiro ponto, coord[1] o valor y do primeiro ponto, coord[2]
        # o valor z da coordenada z do primeiro ponto. Já coord[3] é a coordenada x do
        # segundo ponto e assim por diante. No IndexedFaceSet uma lista de vértices é informada
        # em coordIndex, o valor -1 indica que a lista acabou.
        # A ordem de conexão não possui uma ordem oficial, mas em geral se o primeiro ponto
        # com os dois seguintes e depois este mesmo primeiro ponto com o terçeiro e quarto
        # ponto. Por exemplo: numa sequencia 0, 1, 2, 3, 4, -1 o primeiro triângulo será
        # com os vértices 0, 1 e 2, depois serão
        # os vértices 0, 2 e 3, e depois 0, 3 e 4, e assim por diante, até chegar no final da lista.
        # Adicionalmente essa implementação do IndexedFace aceita cores por vértices, assim
        # se a flag colorPerVertex estiver habilitada, os vértices também possuirão cores
        # que servem para definir a cor interna dos poligonos, para isso faça um cálculo
        # baricêntrico de que cor deverá ter aquela posição. Da mesma forma se pode definir uma
        # textura para o poligono, para isso, use as coordenadas de textura e depois aplique a
        # cor da textura conforme a posição do mapeamento. Dentro da classe GPU já está
        # implementadado um método para a leitura de imagens.

        # Os prints abaixo são só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("IndexedFaceSet : ")
        if coord:
            print("\tpontos(x, y, z) = {0}, coordIndex = {1}".format(coord, coordIndex))
        print("colorPerVertex = {0}".format(colorPerVertex))
        if colorPerVertex and color and colorIndex:
            print("\tcores(r, g, b) = {0}, colorIndex = {1}".format(color, colorIndex))
        if texCoord and texCoordIndex:
            print("\tpontos(u, v) = {0}, texCoordIndex = {1}".format(texCoord, texCoordIndex))
        if current_texture:
            image = gpu.GPU.load_texture(current_texture[0])
            print("\t Matriz com image = {0}".format(image))
            print("\t Dimensões da image = {0}".format(image.shape))
        print("IndexedFaceSet : colors = {0}".format(colors))  # imprime no terminal as cores

        # Exemplo de desenho de um pixel branco na coordenada 10, 10
        gpu.GPU.draw_pixel([10, 10], gpu.PixelFormat.RGB8, [255, 255, 255])  # altera pixel

    @staticmethod
    def box(size: list[float], colors: Colors) -> None:
        """
        Função usada para renderizar Boxes.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Box
        # A função box é usada para desenhar paralelepípedos na cena. O Box é centrada no
        # (0, 0, 0) no sistema de coordenadas local e alinhado com os eixos de coordenadas
        # locais. O argumento size especifica as extensões da caixa ao longo dos eixos X, Y
        # e Z, respectivamente, e cada valor do tamanho deve ser maior que zero. Para desenha
        # essa caixa você vai provavelmente querer tesselar ela em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Box : size = {0}".format(size)) # imprime no terminal pontos
        print("Box : colors = {0}".format(colors)) # imprime no terminal as cores

        # Exemplo de desenho de um pixel branco na coordenada 10, 10
        gpu.GPU.draw_pixel([10, 10], gpu.PixelFormat.RGB8, [255, 255, 255])  # altera pixel

    @staticmethod
    def sphere(radius: float, colors: Colors) -> None:
        """
        Função usada para renderizar Esferas.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Sphere
        # A função sphere é usada para desenhar esferas na cena. O esfera é centrada no
        # (0, 0, 0) no sistema de coordenadas local. O argumento radius especifica o
        # raio da esfera que está sendo criada. Para desenha essa esfera você vai
        # precisar tesselar ela em triângulos, para isso encontre os vértices e defina
        # os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Sphere : radius = {0}".format(radius)) # imprime no terminal o raio da esfera
        print("Sphere : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def cone(bottomRadius: float, height: float, colors: Colors) -> None:
        """
        Função usada para renderizar Cones.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Cone
        # A função cone é usada para desenhar cones na cena. O cone é centrado no
        # (0, 0, 0) no sistema de coordenadas local. O argumento bottomRadius especifica o
        # raio da base do cone e o argumento height especifica a altura do cone.
        # O cone é alinhado com o eixo Y local. O cone é fechado por padrão na base.
        # Para desenha esse cone você vai precisar tesselar ele em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Cone : bottomRadius = {0}".format(bottomRadius)) # imprime no terminal o raio da base
        print("Cone : height = {0}".format(height)) # imprime no terminal a altura do cone
        print("Cone : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def cylinder(radius: float, height: float, colors: Colors) -> None:
        """
        Função usada para renderizar Cilindros.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/geometry3D.html#Cylinder
        # A função cylinder é usada para desenhar cilindros na cena. O cilindro é centrado no
        # (0, 0, 0) no sistema de coordenadas local. O argumento radius especifica o
        # raio da base do cilindro e o argumento height especifica a altura do cilindro.
        # O cilindro é alinhado com o eixo Y local. O cilindro é fechado por padrão em
        # ambas as extremidades.
        # Para desenha esse cilindro você vai precisar tesselar ele em triângulos, para isso
        # encontre os vértices e defina os triângulos.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("Cylinder : radius = {0}".format(radius)) # imprime no terminal o raio do cilindro
        print("Cylinder : height = {0}".format(height)) # imprime no terminal a altura do cilindro
        print("Cylinder : colors = {0}".format(colors)) # imprime no terminal as cores

    @staticmethod
    def navigationInfo(headlight: bool) -> None:
        """
        Características físicas do avatar do visualizador e do modelo de visualização.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/navigation.html#NavigationInfo
        # O campo do headlight especifica se um navegador deve acender um luz direcional que
        # sempre aponta na direção que o usuário está olhando. Definir este campo como TRUE
        # faz com que o visualizador forneça sempre uma luz do ponto de vista do usuário.
        # A luz headlight deve ser direcional, ter intensidade = 1, cor = (1 1 1),
        # ambientIntensity = 0,0 e direção = (0 0 −1).

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("NavigationInfo : headlight = {0}".format(headlight)) # imprime no terminal

    @staticmethod
    def directionalLight(ambientIntensity: float, color: list[float], intensity: float,
                         direction: list[float]) -> None:
        """
        Luz direcional ou paralela.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/lighting.html#DirectionalLight
        # Define uma fonte de luz direcional que ilumina ao longo de raios paralelos
        # em um determinado vetor tridimensional. Possui os campos básicos ambientIntensity,
        # cor, intensidade. O campo de direção especifica o vetor de direção da iluminação
        # que emana da fonte de luz no sistema de coordenadas local. A luz é emitida ao
        # longo de raios paralelos de uma distância infinita.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("DirectionalLight : ambientIntensity = {0}".format(ambientIntensity))
        print("DirectionalLight : color = {0}".format(color)) # imprime no terminal
        print("DirectionalLight : intensity = {0}".format(intensity)) # imprime no terminal
        print("DirectionalLight : direction = {0}".format(direction)) # imprime no terminal

    @staticmethod
    def pointLight(ambientIntensity: float, color: list[float], intensity: float,
                  location: list[float]) -> None:
        """
        Luz pontual.
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

    @staticmethod
    def fog(visibilityRange: float, color: list[float]) -> None:
        """
        Névoa.
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

    @staticmethod
    def timeSensor(cycleInterval: float, loop: bool) -> float:
        """
        Gera eventos conforme o tempo passa.
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

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("TimeSensor : cycleInterval = {0}".format(cycleInterval)) # imprime no terminal
        print("TimeSensor : loop = {0}".format(loop))

        # Esse método já está implementado para os alunos como exemplo
        epoch = time.time()  # time in seconds since the epoch as a floating point number.
        fraction_changed = (epoch % cycleInterval) / cycleInterval

        return fraction_changed

    @staticmethod
    def splinePositionInterpolator(set_fraction: float, key: list[float], keyValue: list[float],
                                   closed: bool) -> list[float]:
        """
        Interpola não linearmente entre uma lista de vetores 3D.
        """
        # https://www.web3d.org/specifications/X3Dv4/ISO-IEC19775-1v4-IS/Part01/components/interpolators.html#SplinePositionInterpolator
        # Interpola não linearmente entre uma lista de vetores 3D. O campo keyValue possui
        # uma lista com os valores a serem interpolados, key possui uma lista respectiva de chaves
        # dos valores em keyValue, a fração a ser interpolada vem de set_fraction que varia de
        # zeroa a um. O campo keyValue deve conter exatamente tantos vetores 3D quanto os
        # quadros-chave no key. O campo closed especifica se o interpolador deve tratar a malha
        # como fechada, com uma transições da última chave para a primeira chave. Se os keyValues
        # na primeira e na última chave não forem idênticos, o campo closed será ignorado.

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("SplinePositionInterpolator : set_fraction = {0}".format(set_fraction))
        print("SplinePositionInterpolator : key = {0}".format(key)) # imprime no terminal
        print("SplinePositionInterpolator : keyValue = {0}".format(keyValue))
        print("SplinePositionInterpolator : closed = {0}".format(closed))

        # Abaixo está só um exemplo de como os dados podem ser calculados e transferidos
        value_changed = [0.0, 0.0, 0.0]
        
        return value_changed

    @staticmethod
    def orientationInterpolator(set_fraction: float, key: list[float],
                                keyValue: list[float]) -> list[float]:
        """
        Interpola entre uma lista de valores de rotação especificos.
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

        # O print abaixo é só para vocês verificarem o funcionamento, DEVE SER REMOVIDO.
        print("OrientationInterpolator : set_fraction = {0}".format(set_fraction))
        print("OrientationInterpolator : key = {0}".format(key)) # imprime no terminal
        print("OrientationInterpolator : keyValue = {0}".format(keyValue))

        # Abaixo está só um exemplo de como os dados podem ser calculados e transferidos
        value_changed = [0.0, 0.0, 1.0, 0.0]

        return value_changed

    # Para o futuro (Não para versão atual do projeto.)
    def vertex_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um vertex shader.
        """

    def fragment_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um fragment shader.
        """
