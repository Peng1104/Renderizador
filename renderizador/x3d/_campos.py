"""
Leitores dos tipos de campo X3D (SFFloat, MFVec3f, ...).
"""

import re
import xml.etree.ElementTree as ET

Element = ET.Element


def clean(child: Element) -> None:
    """
    Recebe um nó XML e remove dele o namespace do atributo tag se houver.
    """
    _, _, child.tag = child.tag.rpartition('}') # remove os namespaces


def SFTime(node: Element | None, field: str, default: float) -> float:
    """
    Especifica um único valor de tempo.
    """
    if node is not None and field in node.attrib:
        return float(node.attrib[field].strip())
    return default


def SFFloat(node: Element | None, field: str, default: float) -> float:
    """
    Especifica um único valor em ponto flutuante.
    """
    if node is not None and field in node.attrib:
        return float(node.attrib[field].strip())
    return default


def MFFloat(node: Element | None, field: str, default: list[float] | None) -> list[float] | None:
    """
    Especifica uma cor.
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def MFInt32(node: Element | None, field: str, default: list[int]) -> list[int]:
    """
    Especifica zero ou mais valores inteiros.
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [int(value) for value in val_str]
        return []
    return default


def SFBool(node: Element | None, field: str, default: bool) -> bool:
    """
    Especifica um único valor booleano.
    """
    if node is not None and field in node.attrib:
        val_str = node.attrib[field].strip().lower()
        return val_str == "true"
    return default


def SFRotation(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica uma rotação única.
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def SFColor(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica uma cor.
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def MFColor(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica uma cor.
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def SFVec3f(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica um vetor tridimensional (3D).
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def MFVec3f(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica zero ou mais vetores tridimensionais (3D).
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def MFVec2f(node: Element | None, field: str, default: list[float]) -> list[float]:
    """
    Especifica zero ou mais vetores bidimensionais (2D).
    """
    if node is not None and field in node.attrib:
        val = node.attrib[field].strip()
        if val:
            val_str = re.split(r'[,\s]\s*', val)
            return [float(value) for value in val_str]
        return []
    return default


def SFString(node: Element | None, field: str, default: str) -> str:
    """
    Especifica uma strings.
    """
    if node is not None and field in node.attrib:
        return node.attrib[field].strip()
    return default


def MFString(node: Element | None, field: str, default: list[str]) -> list[str]:
    """
    Especifica zero ou mais strings.
    """
    if node is not None and field in node.attrib:
        val_str = re.split(r'[,\s]\s*', node.attrib[field].strip())
        return [addr.replace('"', '').replace("'", '') for addr in val_str if addr != '']
    return default
