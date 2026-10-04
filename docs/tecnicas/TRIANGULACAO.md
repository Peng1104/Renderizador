# Triangulação de Faces e Tiras

## 1. Por que triangular

O rasterizador desenha apenas triângulos: um triângulo é sempre plano e convexo, e a função de aresta que decide se um ponto está dentro dele (ver [Rasterização de Triângulos por Função de Aresta](RASTERIZACAO_TRIANGULOS.md)) só funciona para três arestas. Os nós X3D de malha descrevem a geometria de outras formas, por polígonos com qualquer número de lados ou por tiras de triângulos. A triangulação converte essas descrições em uma lista única de triplas de índices $(i_0, i_1, i_2)$ sobre a mesma lista de vértices, sem criar vértices novos.

Todas as triplas seguem a convenção anti-horária vista de fora do objeto, que é o critério usado pelo descarte de faces de costas (ver [Back-Face Culling](BACKFACE_CULLING.md)).

## 2. Faces em leque (IndexedFaceSet)

A lista de índices de um IndexedFaceSet concatena as faces, separadas pelo valor $-1$:

```
0 1 2 3 -1   4 5 6 -1   7 8 9 10 11 -1
```

Uma face com vértices $v_0, v_1, \dots, v_{n-1}$ é dividida em um leque de triângulos que partem de $v_0$:

$$
(v_0, v_1, v_2),\ (v_0, v_2, v_3),\ \dots,\ (v_0, v_{n-2}, v_{n-1})
$$

Uma face de $n$ vértices gera $n - 2$ triângulos. Os passos são:

1. Dividir a lista nos separadores $-1$.
2. Descartar as faces com menos de 3 vértices, que não têm área.
3. Para cada face restante, gerar as $n - 2$ triplas acima.
4. Registrar, para cada triângulo, a posição da face de origem na lista (contando também as descartadas).

O registro da face de origem existe para o caso em que a cor é definida por face: todos os triângulos de uma mesma face recebem a cor daquela face.

A mesma triangulação vale para os índices de cor e de coordenada de textura, que seguem a mesma estrutura de faces e separadores que os índices de vértice. Assim o triângulo $t$ de índices de posição corresponde ao triângulo $t$ de índices de cor e de textura.

O leque só reproduz o polígono original quando ele é convexo; uma face côncava pode gerar triângulos que saem do seu contorno.

### 2.1 Reuso entre frames

O resultado depende só da lista de índices, que não muda ao longo da animação para uma malha estática (o que se move é a transformação, não a topologia). Por isso a triangulação de cada lista é calculada uma vez e reaproveitada nos frames seguintes, enquanto a lista for a mesma. O ganho cresce com o tamanho da malha e com o número de frames.

## 3. Tiras de triângulos (TriangleStripSet e IndexedTriangleStripSet)

Uma tira com vértices $s_0, s_1, \dots, s_{n-1}$ forma um triângulo para cada janela de três vértices consecutivos, compartilhando dois vértices com o anterior. Uma tira de $n$ vértices gera $n - 2$ triângulos e tiras com menos de 3 vértices não geram nenhum.

Tomar as janelas na ordem crua inverte o sentido de giro a cada triângulo, porque cada novo triângulo reaproveita a aresta do anterior no sentido oposto. Para manter o sentido anti-horário em todos, os dois primeiros índices são trocados nos triângulos de posição ímpar:

| Triângulo $i$ | Tripla gerada |
| :--- | :--- |
| $i$ par | $(s_i,\ s_{i+1},\ s_{i+2})$ |
| $i$ ímpar | $(s_{i+1},\ s_i,\ s_{i+2})$ |

Para a tira $s = (0, 1, 2, 3, 4)$ o resultado é $(0,1,2)$, $(2,1,3)$, $(2,3,4)$. Os três têm o mesmo sentido de giro.

No TriangleStripSet os vértices são lidos em sequência e um contador por tira diz quantos vértices cada uma consome. No IndexedTriangleStripSet as tiras são listas de índices separadas por $-1$, como nas faces da seção 2.
