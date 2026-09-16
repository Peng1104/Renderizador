# Transformações Geométricas

## 1. Coordenadas homogêneas

Todo ponto e toda transformação do renderizador operam em coordenadas homogêneas: um ponto 3D $(x, y, z)$ é representado como o vetor de 4 componentes $(x, y, z, 1)$, e uma transformação (translação, escala ou rotação) é uma matriz $4 \times 4$ que multiplica esse vetor. A vantagem de acrescentar essa quarta coordenada é que translação, que não é uma operação linear em 3D (não existe matriz $3 \times 3$ que desloque a origem), passa a ser representável como uma multiplicação de matriz junto com escala e rotação, permitindo compor as três num único produto de matrizes.

## 2. Translação

$$
T(t_x, t_y, t_z) = \begin{bmatrix} 1 & 0 & 0 & t_x \\ 0 & 1 & 0 & t_y \\ 0 & 0 & 1 & t_z \\ 0 & 0 & 0 & 1 \end{bmatrix}
$$

Aplicada a um ponto homogêneo $(x, y, z, 1)$, desloca cada eixo pelo respectivo componente de $t$, sem afetar vetores de direção (que têm quarta coordenada 0, já que $0 \cdot t = 0$).

## 3. Escala

$$
S(s_x, s_y, s_z) = \begin{bmatrix} s_x & 0 & 0 & 0 \\ 0 & s_y & 0 & 0 \\ 0 & 0 & s_z & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}
$$

Multiplica cada coordenada pelo fator do respectivo eixo, sempre em torno da origem do sistema de coordenadas local.

## 4. Rotação via quatérnio

Rotações são armazenadas no formato eixo-ângulo do X3D: um eixo $(x, y, z)$ (não necessariamente unitário) e um ângulo $t$ em radianos, seguindo a regra da mão direita. Em vez de montar a matriz de rotação diretamente a partir desses 4 números, o eixo-ângulo é primeiro convertido num quatérnio unitário, que depois é convertido na matriz de rotação. Esse caminho evita o gimbal lock que apareceria ao compor rotações via ângulos de Euler.

### 4.1 Eixo-ângulo para quatérnio

Com o eixo normalizado $\hat{u} = (u_x, u_y, u_z)$ e o ângulo $t$:

$$
q = \left(\cos\frac{t}{2},\; u_x \sin\frac{t}{2},\; u_y \sin\frac{t}{2},\; u_z \sin\frac{t}{2}\right) = (w, x, y, z)
$$

Se o eixo é nulo (norma 0), não há rotação definida e usa-se o quatérnio identidade $(1, 0, 0, 0)$.

### 4.2 Quatérnio para matriz de rotação

Expandindo a rotação de um vetor $v$ por $v' = q v q^{-1}$, chega-se à forma fechada:

$$
R(q) = \begin{bmatrix}
1 - 2(y^2 + z^2) & 2(xy - wz) & 2(xz + wy) \\
2(xy + wz) & 1 - 2(x^2 + z^2) & 2(yz - wx) \\
2(xz - wy) & 2(yz + wx) & 1 - 2(x^2 + y^2)
\end{bmatrix}
$$

Cada elemento da diagonal permanece próximo de 1 menos a contribuição dos outros dois componentes vetoriais do quatérnio: a rotação em torno do eixo $x$ não deveria alterar a própria coordenada $x$, só $y$ e $z$. Fora da diagonal, cada par $(i, j)$ tem um termo simétrico de produto cruzado $2 q_i q_j$ somado ou subtraído de um termo antissimétrico $2 w q_k$; o sinal de $2 w q_k$ se inverte entre $R_{ij}$ e $R_{ji}$ porque segue a regra da mão direita em $(i, j, k)$.

## 5. Composição de transformações num nó

Um nó de transformação no grafo de cena tem três campos, translação $t$, escala $s$ e rotação $r$ (todos opcionais, com identidade como padrão: $t = (0,0,0)$, $s = (1,1,1)$, $r = $ ângulo 0). A transformação local para um ponto do sistema de coordenadas do próprio nó para o sistema do nó pai é:

$$
M_{\text{local} \to \text{pai}} = T(t) \cdot R(r) \cdot S(s)
$$

A ordem da multiplicação importa: aplicada da direita para a esquerda a um ponto, a escala ocorre primeiro (o objeto muda de tamanho em torno da própria origem), depois a rotação (em torno da origem já escalada), depois a translação (posiciona o resultado no sistema do pai).

## 6. Pilha de transformações e composição acumulada

O grafo de cena é percorrido em profundidade, e cada nó de transformação aninhado dentro de outro herda a transformação acumulada dos ancestrais. Isso é implementado como uma pilha: ao entrar num nó de transformação, a nova matriz local é multiplicada pelo topo da pilha (a transformação acumulada do pai) e o resultado é empilhado:

$$
M_{\text{local} \to \text{mundo}} = M_{\text{pai} \to \text{mundo}} \cdot M_{\text{local} \to \text{pai}}
$$

Ao sair do nó, a matriz é desempilhada, recuperando a transformação acumulada do ancestral anterior para os irmãos seguintes no grafo de cena. Essa é exatamente a mesma estrutura de dados usada por qualquer travessia de grafo de cena com transformações hierárquicas: uma pilha de matrizes que cresce ao entrar num nível e encolhe ao sair dele.
