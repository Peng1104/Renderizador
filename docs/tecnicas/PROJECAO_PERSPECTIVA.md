# Projeção Perspectiva

## 1. Pipeline de transformação de um ponto

Um ponto de um objeto passa por 4 espaços de coordenadas até virar um pixel na tela:

$$
\text{objeto} \xrightarrow{M_{\text{modelo}}} \text{mundo} \xrightarrow{M_{\text{view}}} \text{câmera} \xrightarrow{M_{\text{proj}}} \text{clip} \xrightarrow{\div w} \text{NDC} \xrightarrow{\text{viewport}} \text{tela}
$$

$M_{\text{modelo}}$ é a matriz acumulada de transformações do nó do objeto (ver documento de transformações geométricas). As demais etapas são descritas abaixo.

## 2. Matriz de câmera e matriz de view

Um nó de câmera define sua posição $p$ e orientação $r$ (eixo-ângulo) no espaço do mundo. A matriz que leva um ponto do sistema de coordenadas da câmera para o mundo é:

$$
M_{\text{câmera} \to \text{mundo}} = T(p) \cdot R(r)
$$

A matriz de view faz o caminho inverso, de mundo para câmera, e é a inversa dessa matriz. Para uma transformação rígida (rotação seguida de translação, sem escala), a inversa tem forma fechada: a transposta do bloco de rotação, seguida da translação negada, o que evita calcular uma inversão de matriz genérica a cada frame.

## 3. Campo de visão e razão de aspecto

O campo de visão (field of view) do X3D é definido para a menor dimensão da tela; a maior dimensão recebe um ângulo mais largo, ajustado pela razão de aspecto $a = \text{largura} / \text{altura}$:

$$
\text{fov}_y =
\begin{cases}
\text{fov} & \text{se } a > 1 \text{ (tela mais larga que alta)} \\
2 \arctan\!\left(\dfrac{\tan(\text{fov}/2)}{a}\right) & \text{se } a \le 1 \text{ (tela mais alta que larga)}
\end{cases}
$$

## 4. Matriz de projeção perspectiva

Com o campo de visão vertical $\text{fov}_y$, a razão de aspecto $a$, e os planos de corte próximo ($n$) e distante ($f$):

$$
\text{top} = n \tan\!\left(\frac{\text{fov}_y}{2}\right), \qquad \text{right} = \text{top} \cdot a
$$

$$
M_{\text{proj}} = \begin{bmatrix}
n / \text{right} & 0 & 0 & 0 \\
0 & n / \text{top} & 0 & 0 \\
0 & 0 & -\dfrac{f + n}{f - n} & -\dfrac{2fn}{f - n} \\
0 & 0 & -1 & 0
\end{bmatrix}
$$

A quarta linha $(0, 0, -1, 0)$ é o que faz o componente $w$ do ponto em clip space ficar igual a $-z_{\text{câmera}}$: pontos mais distantes da câmera (mais negativos em $z$, já que a câmera olha na direção $-z$) recebem $w$ maior, o que é a base da correção de perspectiva na interpolação de atributos (ver documento correspondente).

## 5. Divisão de perspectiva e NDC

Um ponto em clip space, $(x_c, y_c, z_c, w_c)$, é levado a coordenadas normalizadas de dispositivo (NDC) dividindo pelo componente $w$:

$$
(x_{\text{ndc}}, y_{\text{ndc}}, z_{\text{ndc}}) = \left(\frac{x_c}{w_c}, \frac{y_c}{w_c}, \frac{z_c}{w_c}\right)
$$

Com a matriz de projeção acima, um ponto exatamente no plano próximo ($z_{\text{câmera}} = -n$) mapeia para $z_{\text{ndc}} = -1$, e um ponto no plano distante ($z_{\text{câmera}} = -f$) mapeia para $z_{\text{ndc}} = 1$; qualquer profundidade intermediária cai em $[-1, 1]$ de forma monótona. Esse é o valor usado pelo teste de z-buffer (ver documento correspondente).

## 6. Viewport: de NDC para pixels de tela

O NDC está em $[-1, 1]$ nos dois eixos, com origem no centro da tela e $y$ crescendo para cima. A transformação de viewport mapeia isso para pixels, com origem no canto superior esquerdo e $y$ crescendo para baixo (convenção de imagem):

$$
x_{\text{tela}} = \frac{x_{\text{ndc}} + 1}{2} \cdot \text{largura}, \qquad y_{\text{tela}} = \frac{1 - y_{\text{ndc}}}{2} \cdot \text{altura}
$$

O termo $1 - y_{\text{ndc}}$ é o que inverte o eixo $y$: $y_{\text{ndc}} = 1$ (topo do NDC) mapeia para $y_{\text{tela}} = 0$ (topo da imagem).
