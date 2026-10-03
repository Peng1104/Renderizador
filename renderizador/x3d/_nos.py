"""
Nós X3D suportados. Importá-los aqui é o que registra cada classe por tag em _registro.
"""

from ._agrupamento import Transform
from ._ambiente import Fog
from ._aparencia import Appearance, ImageTexture, Material, Shape
from ._geometria2d import Circle2D, Polyline2D, Polypoint2D, TriangleSet2D
from ._geometria3d import Box, Cone, Cylinder, IndexedFaceSet, Sphere
from ._iluminacao import DirectionalLight, PointLight
from ._interpoladores import OrientationInterpolator, SplinePositionInterpolator
from ._malhas import IndexedTriangleStripSet, TriangleSet, TriangleStripSet
from ._navegacao import NavigationInfo, Viewpoint
from ._propriedades import Color, Coordinate, TextureCoordinate
from ._tempo import TimeSensor

NOS_SUPORTADOS: tuple[type, ...] = (
    Shape,
    Transform,
    Appearance,
    Material,
    ImageTexture,
    Coordinate,
    Color,
    TextureCoordinate,
    Polypoint2D,
    Polyline2D,
    Circle2D,
    TriangleSet2D,
    TriangleSet,
    TriangleStripSet,
    IndexedTriangleStripSet,
    Box,
    Sphere,
    Cone,
    Cylinder,
    IndexedFaceSet,
    TimeSensor,
    NavigationInfo,
    Viewpoint,
    DirectionalLight,
    PointLight,
    Fog,
    SplinePositionInterpolator,
    OrientationInterpolator,
)
