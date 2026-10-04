# Modelo de Iluminação de Phong

## 1. O problema da iluminação local

Uma superfície pintada com uma única cor constante parece plana, porque a aparência real de um objeto depende da orientação da superfície em relação à luz e ao observador. O modelo de Phong é um modelo empírico e local: calcula a cor de um ponto usando apenas a normal da superfície no ponto, a direção da luz, a direção da câmera e as propriedades do material, sem simular reflexões entre objetos nem sombras. É barato o bastante para ser avaliado em cada pixel e reproduz os três efeitos visuais dominantes: o escurecimento onde a luz não chega, a variação suave de brilho com a inclinação e o brilho pontual de superfícies polidas.

## 2. Vetores envolvidos

Todos os vetores são unitários e expressos em coordenadas de mundo, no ponto $P$ sendo iluminado.

| Vetor | Significado |
| :--- | :--- |
| $N$ | Normal da superfície em $P$ |
| $L$ | Direção de $P$ para a luz |
| $V$ | Direção de $P$ para a câmera |
| $R$ | Reflexo de $L$ em torno de $N$: $R = 2(N \cdot L)N - L$ |
| $H$ | Vetor intermediário: $H = \dfrac{L + V}{\lVert L + V \rVert}$ |

## 3. Componentes

A cor final soma três componentes, cada um com uma cor de material associada.

### 3.1 Ambiente

Aproxima a luz indireta espalhada pela cena como um termo constante, independente de $N$, $L$ e $V$. Sem ele, toda região não alcançada pela luz direta seria preta.

$$
I_{\text{amb}} = a_L \, k_a \, D
$$

onde $a_L$ é a intensidade ambiente da luz, $k_a$ a fração de luz ambiente que o material aceita e $D$ a cor difusa do material.

### 3.2 Difusa

Modela superfícies foscas, que espalham a luz igualmente em todas as direções. Pela lei de Lambert, o brilho é proporcional ao cosseno do ângulo entre $N$ e $L$, e fica em zero quando a superfície está de costas para a luz:

$$
I_{\text{dif}} = D \, \max(N \cdot L,\ 0)
$$

### 3.3 Especular

Modela o brilho concentrado de superfícies polidas, visível apenas quando a câmera está perto da direção de reflexão da luz. O formato original usa $(R \cdot V)^n$; a variante de Blinn-Phong troca $R$ por $H$, o que evita calcular o reflexo e produz um brilho de aparência equivalente:

$$
I_{\text{esp}} = S \, \max(N \cdot H,\ 0)^{n}
$$

onde $S$ é a cor especular e $n$ o expoente de brilho. Quanto maior $n$, menor e mais concentrado o realce. O termo só é aplicado onde $N \cdot L > 0$, para que uma superfície voltada para longe da luz não receba realce.

## 4. Equação completa

Somando os componentes de cada luz $l$ da cena, com a emissiva $E$ do material (luz que o próprio objeto emite, independente de qualquer fonte):

$$
C = E + \sum_{l} c_l \Big[ a_l \, k_a \, D + i_l \big( D \max(N \cdot L_l, 0) + S \max(N \cdot H_l, 0)^{n} \big) \Big]
$$

onde $c_l$ é a cor da luz e $i_l$ a sua intensidade. O resultado é recortado ao intervalo $[0, 1]$ em cada canal.

## 5. Parâmetros do material no X3D

O nó `Material` do X3D fornece as constantes da equação:

| Campo X3D | Símbolo | Papel |
| :--- | :--- | :--- |
| `diffuseColor` | $D$ | Cor base do objeto |
| `specularColor` | $S$ | Cor do realce |
| `emissiveColor` | $E$ | Luz própria do objeto |
| `ambientIntensity` | $k_a$ | Fração de luz ambiente aceita |
| `shininess` | $s \in [0, 1]$ | Controla o realce, com $n = 128\,s$ |

Quando o objeto tem textura, a cor amostrada da textura substitui $D$ em cada ponto, de modo que a textura também é iluminada. Se a cena não tem nenhuma luz, o resultado é apenas $E$. A construção da lista de luzes está em [Luzes](LUZES.md).

## 6. Onde a equação é avaliada

A equação pode ser avaliada em três granularidades, que definem o nome do *shading*:

| Técnica | Onde a iluminação é calculada | Resultado |
| :--- | :--- | :--- |
| Flat | Uma vez por face | Faces facetadas, realce inexistente ou serrilhado |
| Gouraud | Nos vértices, com a cor interpolada pelo triângulo | Suave, mas o realce some se cair dentro do triângulo |
| Phong | Em cada pixel, com a normal interpolada e renormalizada | Realce preciso, ao custo de uma avaliação por pixel |

Não confundir *modelo* de iluminação de Phong (a equação da seção 4) com *shading* de Phong (a avaliação por pixel): o modelo pode ser aplicado em qualquer uma das três granularidades.

Este renderizador interpola a posição e a normal de mundo com os pesos baricêntricos de cada pixel coberto, renormaliza a normal, e só então aplica a equação da seção 4. A interpolação usa os pesos corrigidos pela perspectiva (ver [Interpolação Perspectiva-Correta](INTERPOLACAO_PERSPECTIVA.md)), e a cor resultante segue o fluxo normal de escrita, incluindo mistura por transparência (ver [Transparência](TRANSPARENCIA.md)).
