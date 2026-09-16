# Mapeamento de Textura

## 1. Coordenadas UV por vértice

Cada vértice de uma face texturizada carrega, além da posição 3D, uma coordenada de textura $(u, v)$ com $u$ e $v$ tipicamente em $[0, 1]$, referenciando uma posição relativa dentro da imagem da textura, independente da resolução real dessa imagem em pixels. Durante a rasterização, a coordenada UV de cada subamostra dentro do triângulo é obtida pela mesma interpolação perspectiva-correta usada para cor por vértice (ver documento correspondente), a partir das coordenadas UV dos 3 vértices e dos pesos baricêntricos corrigidos pela perspectiva.

## 2. Wrap (repeat) fora de [0, 1]

O padrão X3D para textura é repetir (wrap) a textura indefinidamente fora do intervalo $[0, 1]$, em vez de recortar (clamp) na borda. Isso é obtido pelo resto da divisão por 1:

$$
u' = u \bmod 1, \qquad v' = v \bmod 1
$$

Uma coordenada $u = 1.3$, por exemplo, vira $u' = 0.3$: a textura se repete a cada unidade inteira de UV, permitindo padrões que se repetem várias vezes sobre uma mesma superfície com um único conjunto de coordenadas.

## 3. De UV para índice de texel

Com a textura tendo $\text{largura} \times \text{altura}$ texels, a coordenada UV normalizada é convertida num índice inteiro de texel:

$$
t_x = \left\lfloor u' \cdot \text{largura} \right\rfloor, \qquad t_y = \left\lfloor (1 - v') \cdot \text{altura} \right\rfloor
$$

ambos recortados ao intervalo $[0, \text{dimensão} - 1]$ para evitar estourar o array por erro de arredondamento numérico bem na borda ($u' = 1.0$ ou $v' = 1.0$ exatos). O termo $1 - v'$ inverte o eixo verde da textura: a convenção X3D define $v = 0$ como a base da imagem, enquanto a matriz de pixels carregada do arquivo tem a linha de índice 0 no topo.

## 4. Amostragem nearest-neighbor

A cor do texel no índice $(t_x, t_y)$ é usada diretamente como a cor daquela subamostra, sem nenhuma interpolação entre texels vizinhos (amostragem nearest-neighbor, ao contrário de filtragem bilinear). Isso significa que, quando um texel cobre vários pixels de tela (textura ampliada além de sua resolução original), blocos quadrados visíveis aparecem na imagem; e quando vários texels caem no mesmo pixel de tela (textura reduzida abaixo de sua resolução original), apenas um deles é amostrado, descartando os demais, o que produz aliasing sem uma técnica adicional de minificação (ver documento de mipmap).
