#from treelib import Node, Tree
import xml.etree.ElementTree as ET

# Desenha o Grafo de Cena no console
class Graph:
    # def parse(self, node):
    #     for child in node:
    #         tag = child.tag + (" "+str(child.attrib) if child.attrib else "")
    #         self.tree.create_node(tag, child.__hash__(), node.__hash__())
    #         self.parse(child)

    def __init__(self, node: ET.Element) -> None:
        # self.tree = Tree()
        # self.tree.create_node(node.tag, node.__hash__())
        # self.parse(node)
        # self.tree.show()
        pass
