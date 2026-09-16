# Interpolação Perspectiva-Correta

## 1. O problema da interpolação linear em tela

Um atributo por vértice (cor, coordenada de textura) varia linearmente sobre a superfície do triângulo no espaço 3D do objeto. Mas a projeção perspectiva não preserva linearidade: a projeção de um segmento de reta 3D em tela ainda é um segmento de reta, porém a posição de um ponto ao longo desse segmento, em função da fração de distância percorrida no espaço 3D original, deixa de corresponder à mesma fração de distância percorrida em tela, porque pontos mais distantes da câmera ocupam menos espaço em tela por unidade de profundidade.

Interpolar um atributo diretamente pelos pesos baricêntricos calculados em coordenadas de tela (ver documento de rasterização de triângulos) ignora essa distorção: um vértice muito mais distante que os outros dois acaba influenciando o atributo numa fração da área em tela maior do que deveria, já que a área em tela por si só não reflete a profundidade real de cada vértice na câmera.

## 2. Correção pelo componente w

O componente $w$ de um ponto em espaço de clip é proporcional à profundidade do ponto na câmera (ver documento de projeção perspectiva: $w = -z_{\text{câmera}}$ com a matriz de projeção usada aqui). A interpolação perspectiva-correta de um atributo $\phi$, dados os pesos baricêntricos brutos $\lambda_0, \lambda_1, \lambda_2$ calculados em tela, e os valores do atributo $\phi_0, \phi_1, \phi_2$ e os componentes $w_0, w_1, w_2$ nos 3 vértices, é:

$$
\phi(p) = \dfrac{\dfrac{\lambda_0 \phi_0}{w_0} + \dfrac{\lambda_1 \phi_1}{w_1} + \dfrac{\lambda_2 \phi_2}{w_2}}{\dfrac{\lambda_0}{w_0} + \dfrac{\lambda_1}{w_1} + \dfrac{\lambda_2}{w_2}}
$$

Na prática, isso se decompõe em dois passos: primeiro, cada peso bruto é dividido pelo $w$ do respectivo vértice, produzindo pesos corrigidos não normalizados $\lambda_i' = \lambda_i / w_i$; depois, esses pesos corrigidos são renormalizados para voltar a somar 1, $\hat\lambda_i = \lambda_i' / \sum_j \lambda_j'$. O atributo final é então a combinação linear direta $\phi(p) = \hat\lambda_0 \phi_0 + \hat\lambda_1 \phi_1 + \hat\lambda_2 \phi_2$, sem precisar carregar o atributo original dividido por $w$ separadamente.

Esse é o mesmo mecanismo, aplicado a cor por vértice (Gouraud shading), a coordenadas de textura UV, e a qualquer outro atributo interpolado por vértice.

## 3. A exceção: profundidade já é afim em tela

A própria coordenada $z$ de NDC, usada no teste de z-buffer, não precisa dessa correção: ao contrário de um atributo arbitrário do vértice, $z_{\text{ndc}}$ é uma função afim das coordenadas de tela $(x, y)$ do triângulo, propriedade que decorre diretamente da forma da matriz de projeção perspectiva usada (a razão $1/w$ já é afim em tela, e $z_{\text{ndc}}$ é uma função afim de $1/w$). Por isso a profundidade é interpolada com os pesos baricêntricos brutos $\lambda_0, \lambda_1, \lambda_2$, sem a correção de perspectiva, e o resultado ainda é exato. Ver o documento de z-buffer para a derivação completa dessa propriedade.
