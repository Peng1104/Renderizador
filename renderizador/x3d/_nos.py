"""
Nós X3D suportados. Importá-los aqui é o que registra cada classe por tag em _registro.
"""

from ._agrupamento import Transform
from ._aparencia import Appearance, ImageTexture, Material, Shape
from ._nucleo import (
    Box,
    Circle2D,
    Cone,
    Cylinder,
    DirectionalLight,
    Fog,
    IndexedFaceSet,
    IndexedTriangleStripSet,
    NavigationInfo,
    OrientationInterpolator,
    PointLight,
    Polyline2D,
    Polypoint2D,
    Sphere,
    SplinePositionInterpolator,
    TriangleSet,
    TriangleSet2D,
    TriangleStripSet,
    Viewpoint,
)
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
