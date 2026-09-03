#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Renderizador X3D.

Desenvolvido por: Luciano Soares <lpsoares@insper.edu.br>
Disciplina: Computação Gráfica
Data: 28 de Agosto de 2020
"""

import argparse  # Para tratar os parâmetros da linha de comando
import os  # Para rotinas do sistema operacional

import gl  # Recupera rotinas de suporte ao X3D
import gpu  # Simula os recursos de uma GPU
import interface  # Janela de visualização baseada no Matplotlib
import numpy as np
import numpy.typing as npt
import scenegraph  # Imprime o grafo de cena no console
import x3d  # Faz a leitura do arquivo X3D, gera o grafo de cena e faz traversal

LARGURA = 60  # Valor padrão para largura da tela
ALTURA = 40   # Valor padrão para altura da tela


class Renderizador:
    """
    Realiza a renderização da cena informada.
    """

    def __init__(self) -> None:
        """
        Definindo valores padrão.
        """
        self.width: int = LARGURA
        self.height: int = ALTURA
        self.x3d_file: str = ""
        self.image_file: str = "tela.png"
        self.scene: x3d.X3D | None = None
        self.framebuffers: dict[str, int] = {}
        # Fator de supersampling (SSAA) opcional, além do 4x MSAA feito pela
        # GL (GL.MSAA_AMOSTRAS): desenha internamente em resolução
        # width*fator x height*fator e reduz por média de blocos em pos(),
        # suavizando ainda mais. Se 1 só o MSAA da GL atua.
        self.supersampling: int = 1
        self.render_width: int = self.width
        self.render_height: int = self.height

    def setup(self) -> None:
        """
        Configura o sistema para a renderização.
        """
        # Configurando color buffers para exibição na tela

        # Cria duas posições de FrameBuffer na GPU: FRONT recebe o desenho em
        # resolução supersampled, SCREEN recebe o resultado final reduzido.
        fbo = gpu.GPU.gen_framebuffers(2)

        # Define o atributo FRONT como o FrameBuffer de desenho
        self.framebuffers["FRONT"] = fbo[0]
        self.framebuffers["SCREEN"] = fbo[1]

        # Define que a posição criada será usada para desenho e leitura
        gpu.GPU.bind_framebuffer(gpu.FramebufferTarget.FRAMEBUFFER, self.framebuffers["FRONT"])
        # Opções:
        # - DRAW_FRAMEBUFFER: Faz o bind só para escrever no framebuffer
        # - READ_FRAMEBUFFER: Faz o bind só para leitura no framebuffer
        # - FRAMEBUFFER: Faz o bind para leitura e escrita no framebuffer

        # Aloca memória no FrameBuffer para um tipo e tamanho especificado de buffer

        # Memória de Framebuffer para canal de cores: FRONT em resolução
        # supersampled (onde o GL desenha) e SCREEN na resolução final.
        gpu.GPU.framebuffer_storage(
            self.framebuffers["FRONT"],
            gpu.Attachment.COLOR_ATTACHMENT,
            gpu.PixelFormat.RGB8,
            self.render_width,
            self.render_height
        )
        gpu.GPU.framebuffer_storage(
            self.framebuffers["SCREEN"],
            gpu.Attachment.COLOR_ATTACHMENT,
            gpu.PixelFormat.RGB8,
            self.width,
            self.height
        )

        # Descomente as seguintes linhas se for usar um Framebuffer para profundidade
        # gpu.GPU.framebuffer_storage(
        #     self.framebuffers["FRONT"],
        #     gpu.Attachment.DEPTH_ATTACHMENT,
        #     gpu.PixelFormat.DEPTH_COMPONENT32F,
        #     self.width,
        #     self.height
        # )
    
        # Opções:
        # - COLOR_ATTACHMENT: alocações para as cores da imagem renderizada
        # - DEPTH_ATTACHMENT: alocações para as profundidades da imagem renderizada
        # Obs: Você pode chamar duas vezes a rotina com cada tipo de buffer.

        # Tipos de dados:
        # - RGB8: Para canais de cores (Vermelho, Verde, Azul) 8bits cada (0-255)
        # - RGBA8: Para canais de cores (Vermelho, Verde, Azul, Transparência) 8bits cada (0-255)
        # - DEPTH_COMPONENT16: Para canal de Profundidade de 16bits (half-precision) (0-65535)
        # - DEPTH_COMPONENT32F: Para canal de Profundidade de 32bits (single-precision) (float)

        # Define cor que ira apagar o FrameBuffer quando clear_buffer() invocado
        gpu.GPU.clear_color([0, 0, 0])

        # Define a profundidade que ira apagar o FrameBuffer quando clear_buffer() invocado
        # Assuma 1.0 o mais afastado e -1.0 o mais próximo da camera
        gpu.GPU.clear_depth(1.0)

        # Definindo tamanho do Viewport para renderização (resolução supersampled)
        assert self.scene is not None
        self.scene.viewport(width=self.render_width, height=self.render_height)

    def pre(self) -> None:
        """
        Rotinas pré renderização.
        """
        # Função invocada antes do processo de renderização iniciar.

        # Limpa o FrameBuffer do GPU e o buffer de multisample (4x MSAA) da GL
        gl.GL.clear()

        # Recursos que podem ser úteis:
        # Define o valor do pixel no framebuffer: draw_pixel(coord, mode, data)
        # Retorna o valor do pixel no framebuffer: read_pixel(coord, mode)

    def pos(self) -> None:
        """
        Rotinas pós renderização.
        """
        # Função invocada após o processo de renderização terminar.

        # Essa é uma chamada conveniente para manipulação de buffers
        # ao final da renderização de um frame. Como por exemplo, executar
        # downscaling da imagem.

        # Resolve o MSAA da GL: faz a média das subamostras de cada pixel
        # e escreve o resultado no FrameBuffer FRONT (a resolução em que a GL
        # desenhou). Precisa acontecer antes do box filter de supersampling
        # abaixo, que ainda reduz FRONT (width*fator x height*fator) para
        # SCREEN (resolução final), com fator=1 esse passo é um no-op, já que
        # MSAA sozinho já resolveu tudo em resolução final.
        gl.GL.resolve_multisample()

        # Reduz o FrameBuffer supersampled (FRONT) para a resolução final
        # (SCREEN) fazendo a média de cada bloco fator x fator (box filter),
        # suavizando as bordas em escada do rasterizador sem antialiasing.
        s = self.supersampling
        desenhado = gpu.GPU.frame_buffer[self.framebuffers["FRONT"]].color
        blocos = desenhado.reshape(self.height, s, self.width, s, -1)
        reduzido = blocos.mean(axis=(1, 3))
        tela = gpu.GPU.frame_buffer[self.framebuffers["SCREEN"]]
        tela.color = np.round(reduzido).astype(np.uint8)
        gpu.GPU.bind_framebuffer(
            gpu.FramebufferTarget.READ_FRAMEBUFFER, self.framebuffers["SCREEN"])

        # Método para a troca dos buffers (NÃO IMPLEMENTADO)
        # Esse método será utilizado na fase de implementação de animações
        gpu.GPU.swap_buffers()

    def mapping(self) -> None:
        """
        Mapeamento de funções para as rotinas de renderização.
        """
        # Rotinas encapsuladas na classe GL (Graphics Library)
        x3d.X3D.renderer["Polypoint2D"] = gl.GL.polypoint2D
        x3d.X3D.renderer["Polyline2D"] = gl.GL.polyline2D
        x3d.X3D.renderer["Circle2D"] = gl.GL.circle2D
        x3d.X3D.renderer["TriangleSet2D"] = gl.GL.triangleSet2D
        x3d.X3D.renderer["TriangleSet"] = gl.GL.triangleSet
        x3d.X3D.renderer["Viewpoint"] = gl.GL.viewpoint
        x3d.X3D.renderer["Transform_in"] = gl.GL.transform_in
        x3d.X3D.renderer["Transform_out"] = gl.GL.transform_out
        x3d.X3D.renderer["TriangleStripSet"] = gl.GL.triangleStripSet
        x3d.X3D.renderer["IndexedTriangleStripSet"] = gl.GL.indexedTriangleStripSet
        x3d.X3D.renderer["IndexedFaceSet"] = gl.GL.indexedFaceSet
        x3d.X3D.renderer["Box"] = gl.GL.box
        x3d.X3D.renderer["Sphere"] = gl.GL.sphere
        x3d.X3D.renderer["Cone"] = gl.GL.cone
        x3d.X3D.renderer["Cylinder"] = gl.GL.cylinder
        x3d.X3D.renderer["NavigationInfo"] = gl.GL.navigationInfo
        x3d.X3D.renderer["DirectionalLight"] = gl.GL.directionalLight
        x3d.X3D.renderer["PointLight"] = gl.GL.pointLight
        x3d.X3D.renderer["Fog"] = gl.GL.fog
        x3d.X3D.renderer["TimeSensor"] = gl.GL.timeSensor
        x3d.X3D.renderer["SplinePositionInterpolator"] = gl.GL.splinePositionInterpolator
        x3d.X3D.renderer["OrientationInterpolator"] = gl.GL.orientationInterpolator

    def render(self) -> npt.NDArray[np.uint8]:
        """
        Laço principal de renderização.
        """
        self.pre()  # executa rotina pré renderização
        assert self.scene is not None
        self.scene.render()  # faz o traversal no grafo de cena
        self.pos()  # executa rotina pós renderização
        return gpu.GPU.get_frame_buffer()

    def main(self) -> None:
        """
        Executa a renderização.
        """
        # Tratando entrada de parâmetro
        parser = argparse.ArgumentParser(add_help=False)   # parser para linha de comando
        parser.add_argument("-i", "--input", help="arquivo X3D de entrada")
        parser.add_argument("-o", "--output", help="arquivo 2D de saída (imagem)")
        parser.add_argument("-w", "--width", help="resolução horizonta", type=int)
        parser.add_argument("-h", "--height", help="resolução vertical", type=int)
        parser.add_argument("-g", "--graph", help="imprime o grafo de cena", action='store_true')
        parser.add_argument("-p", "--pause", help="começa simulação em pausa", action='store_true')
        parser.add_argument("-q", "--quiet", help="não exibe janela", action='store_true')
        parser.add_argument("-s", "--supersampling",
                            help="fator de supersampling (antialiasing)", type=int)
        args = parser.parse_args() # parse the arguments
        if args.input:
            self.x3d_file = args.input
        if args.output:
            self.image_file = args.output
        if args.width:
            self.width = args.width
        if args.height:
            self.height = args.height
        if args.supersampling:
            self.supersampling = args.supersampling
        self.render_width = self.width * self.supersampling
        self.render_height = self.height * self.supersampling

        path = os.path.dirname(os.path.abspath(self.x3d_file))

        # Iniciando simulação de GPU
        gpu.GPU(self.image_file, path)

        # Abre arquivo X3D
        self.scene = x3d.X3D(self.x3d_file)

        # Iniciando Biblioteca Gráfica (resolução supersampled)
        gl.GL.setup(
            self.render_width,
            self.render_height,
            near=0.01,
            far=1000
        )

        # Funções que irão fazer o rendering
        self.mapping()

        # Se no modo silencioso não configurar janela de visualização
        window: interface.Interface | None = None
        if not args.quiet:
            window = interface.Interface(self.width, self.height, self.x3d_file)
            self.scene.set_preview(window)

        # carrega os dados do grafo de cena
        if self.scene:
            self.scene.parse()
            if args.graph:
                scenegraph.Graph(self.scene.root)

        # Configura o sistema para a renderização.
        self.setup()

        # Se no modo silencioso salvar imagem e não mostrar janela de visualização
        if args.quiet:
            self.render()  # executa a renderização da cena
            gpu.GPU.save_image()  # Salva imagem em arquivo
        else:
            assert window is not None
            window.set_saver(gpu.GPU.save_image)  # pasa a função para salvar imagens
            window.preview(args.pause, self.render)  # mostra visualização

if __name__ == '__main__':
    renderizador = Renderizador()
    renderizador.main()
