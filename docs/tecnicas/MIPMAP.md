# Mipmap

## 1. O problema da minificação

Amostragem nearest-neighbor direto na textura original (ver documento de mapeamento de textura) funciona bem quando um texel da textura corresponde a um pixel de tela ou menos. Quando a textura aparece muito menor em tela do que sua resolução original, por exemplo várias cópias distantes do mesmo objeto texturizado, vários texels vizinhos caberiam dentro de um único pixel de tela, mas a amostragem nearest-neighbor escolhe só um deles, descartando toda a informação de alta frequência dos texels vizinhos não amostrados. O resultado é aliasing: padrões de moiré e ruído que mudam de forma imprevisível conforme a distância ou o ângulo da câmera variam.

## 2. Cadeia de níveis por filtro de caixa

O mipmap resolve isso pré-computando uma pirâmide de versões cada vez menores da textura original, cada uma já filtrada (com a alta frequência removida por média) antes da redução, em vez de simplesmente descartar texels na redução. O nível 0 é a textura original, $\text{largura}_0 \times \text{altura}_0$. Cada nível seguinte tem metade da resolução do anterior em cada eixo, obtido pela média de cada bloco $2 \times 2$ de texels do nível anterior:

$$
\text{nível}_{k+1}(i, j) = \frac{1}{4} \sum_{di=0}^{1} \sum_{dj=0}^{1} \text{nível}_k(2i + di,\; 2j + dj)
$$

Quando uma dimensão do nível atual é ímpar, sua última linha ou coluna é duplicada antes da redução, para que só existam blocos $2\times2$ completos de texels a reduzir. A cadeia termina no nível $1 \times 1$: um único texel com a cor média de toda a textura original.

## 3. Escolha do nível por triângulo

Para cada triângulo texturizado, o nível de mipmap a amostrar é escolhido comparando a área do triângulo em pixels de tela com a área que ele ocupa em texels da textura original (nível 0). A área em tela, a partir das coordenadas de tela dos 3 vértices, é:

$$
A_{\text{tela}} = \frac{1}{2} \left| (x_1 - x_0)(y_2 - y_0) - (y_1 - y_0)(x_2 - x_0) \right|
$$

A área em UV, calculada da mesma forma sobre as coordenadas de textura dos 3 vértices, é convertida em área de texels multiplicando pela resolução do nível 0:

$$
A_{\text{uv}} = \frac{1}{2} \left| (u_1 - u_0)(v_2 - v_0) - (v_1 - v_0)(u_2 - u_0) \right|, \qquad A_{\text{texel}} = A_{\text{uv}} \cdot \text{largura}_0 \cdot \text{altura}_0
$$

Se $A_{\text{texel}} \le A_{\text{tela}}$ (a textura já não tem mais detalhe do que cabe no espaço em tela, magnificação ou proporção 1:1), usa-se o nível 0 diretamente. Caso contrário, o nível é escolhido de modo que a razão de área entre texel e pixel se aproxime de 1 naquele nível: como cada nível reduz a área em 4 vezes (2 vezes por eixo), o nível é

$$
\text{nível} = \left\lfloor \frac{1}{2} \log_2\!\left(\frac{A_{\text{texel}}}{A_{\text{tela}}}\right) \right\rfloor
$$

recortado ao intervalo $[0, \text{n\_níveis} - 1]$ da cadeia disponível.

## 4. Granularidade por triângulo, não por pixel

O nível de mipmap é escolhido uma única vez para o triângulo inteiro, não recalculado por pixel ou subamostra dentro dele. Essa é a mesma granularidade de aproximação já usada no resto do pipeline de textura deste renderizador, que também não calcula derivadas de UV por subamostra; um mipmap com seleção por pixel (a técnica usual em GPUs reais, baseada nas derivadas parciais de UV em relação a x e y de tela) reagiria com mais precisão a triângulos muito inclinados em relação à câmera, onde a razão texel/pixel varia bastante dentro do próprio triângulo, mas exigiria essas derivadas por subamostra.

## 5. Amostragem dentro do nível escolhido

Depois de escolhido o nível, a amostragem dentro dele segue exatamente o mesmo processo nearest-neighbor descrito no documento de mapeamento de textura, usando as dimensões daquele nível específico em vez das dimensões do nível 0.
