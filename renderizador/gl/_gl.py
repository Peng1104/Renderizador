"""
Biblioteca Gráfica / Graphics Library.

Desenvolvido por: Lucas Hix
Disciplina: Computação Gráfica
Data: 19/08/2026

A classe GL é a fachada pública: o renderizador a conhece por `gl.GL.<função>`,
e cada função vive no módulo do seu domínio, dentro deste pacote.
"""

from ._animacao import orientationInterpolator, splinePositionInterpolator, timeSensor
from ._framebuffer import clear, resolve_multisample, setup
from ._luzes import directionalLight, fog, navigationInfo, pointLight
from ._nos2d import circle2D, polyline2D, polypoint2D, triangleSet2D
from ._nos3d import indexedFaceSet, indexedTriangleStripSet, triangleSet, triangleStripSet
from ._primitivas import box, cone, cylinder, sphere
from ._transformacoes import transform_in, transform_out, viewpoint


class GL:
    """
    Classe que representa a biblioteca gráfica (Graphics Library).
    """

    setup = staticmethod(setup)
    clear = staticmethod(clear)
    resolve_multisample = staticmethod(resolve_multisample)
    polypoint2D = staticmethod(polypoint2D)
    polyline2D = staticmethod(polyline2D)
    circle2D = staticmethod(circle2D)
    triangleSet2D = staticmethod(triangleSet2D)
    viewpoint = staticmethod(viewpoint)
    transform_in = staticmethod(transform_in)
    transform_out = staticmethod(transform_out)
    triangleSet = staticmethod(triangleSet)
    triangleStripSet = staticmethod(triangleStripSet)
    indexedTriangleStripSet = staticmethod(indexedTriangleStripSet)
    indexedFaceSet = staticmethod(indexedFaceSet)
    box = staticmethod(box)
    sphere = staticmethod(sphere)
    cone = staticmethod(cone)
    cylinder = staticmethod(cylinder)
    navigationInfo = staticmethod(navigationInfo)
    directionalLight = staticmethod(directionalLight)
    pointLight = staticmethod(pointLight)
    fog = staticmethod(fog)
    timeSensor = staticmethod(timeSensor)
    splinePositionInterpolator = staticmethod(splinePositionInterpolator)
    orientationInterpolator = staticmethod(orientationInterpolator)

    # Para o futuro (Não para versão atual do projeto.)
    def vertex_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um vertex shader.

        Parameters
        ----------
        shader : str
            Código-fonte do vertex shader.

        Returns
        -------
        None
            Não implementado; não há retorno.
        """

    def fragment_shader(self, shader: str) -> None:
        """
        Para no futuro implementar um fragment shader.

        Parameters
        ----------
        shader : str
            Código-fonte do fragment shader.

        Returns
        -------
        None
            Não implementado; não há retorno.
        """
