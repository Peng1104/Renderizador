# Anti-Aliasing de Linhas (Algoritmo de Xiaolin Wu)

## 1. Por que uma técnica separada para linhas

Uma reta desenhada por um algoritmo clássico (Bresenham, por exemplo) escolhe um único pixel "cheio" por passo ao longo do eixo dominante, o que produz uma borda em escada visível mesmo com MSAA de poucas subamostras por pixel, já que a reta tem espessura de um pixel e a maior parte de cada pixel tocado está, na verdade, fora da reta ideal. O algoritmo de Xiaolin Wu ataca isso calculando analiticamente, para cada passo, o quanto de dois pixels vizinhos a reta cobre, e distribui a cor entre eles de forma proporcional, sem precisar de subamostras.

## 2. Eixo dominante

Dado um segmento de $(x_0, y_0)$ a $(x_1, y_1)$, com $dx = x_1 - x_0$ e $dy = y_1 - y_0$, o algoritmo determina qual eixo tem maior variação:

$$
\text{íngreme} = |dy| > |dx|
$$

Se a reta é mais íngreme que horizontal (varia mais em $y$ que em $x$), os papéis de $x$ e $y$ são trocados para o restante do cálculo, e trocados de volta só no final. Isso garante que o eixo percorrido em passos inteiros seja sempre aquele com menor variação por passo, evitando buracos na reta (mais de um passo de diferença entre pixels consecutivos no eixo secundário).

Depois da troca de eixo se necessário, os extremos são ordenados para que $x_0 \le x_1$ (trocando também $y_0, y_1$ e invertendo o sinal de $dx, dy$ se preciso), para que a reta seja sempre percorrida da esquerda para a direita.

## 3. Gradiente e posição exata

O gradiente da reta no eixo secundário por unidade do eixo dominante é:

$$
g = \frac{dy}{dx} \quad (g = 0 \text{ se } dx = 0)
$$

Para cada posição inteira $x$ no intervalo $[\lfloor x_0 \rfloor, \lfloor x_1 \rfloor]$, a posição exata (fracionária) da reta no eixo secundário é:

$$
y(x) = y_0 + g \cdot (x - x_0)
$$

## 4. Cobertura complementar entre dois pixels

Como $y(x)$ cai, em geral, entre dois pixels inteiros, os dois recebem cobertura complementar: o pixel principal $\lfloor y(x) \rfloor$, mais próximo da reta, e o secundário $\lfloor y(x) \rfloor + 1$, logo abaixo (ou à direita, se os eixos foram trocados). Com a parte fracionária $\text{frac} = y(x) - \lfloor y(x) \rfloor$:

$$
\text{cobertura}(\lfloor y(x) \rfloor) = 1 - \text{frac}, \qquad \text{cobertura}(\lfloor y(x) \rfloor + 1) = \text{frac}
$$

As duas coberturas somam sempre 1, o que corresponde a distribuir toda a intensidade da reta naquele passo entre os dois pixels que ela efetivamente cruza, na proporção de quão perto de cada um a reta passa. Quando $\text{frac} = 0$ (a reta passa exatamente pelo centro de um pixel), toda a cobertura vai para o pixel principal e nenhuma para o secundário.

## 5. Integração com o buffer de multisample

As coberturas contínuas calculadas por este algoritmo não escrevem cor diretamente; elas alimentam o mesmo buffer de subamostras usado pelo MSAA de triângulos (ver documento de MSAA), sendo quantizadas para a quantidade de subamostras que ocupariam na grade $m \times m$ de cada pixel. Isso mantém uma única representação de cobertura parcial no renderizador, usada tanto por geometria triangular quanto por linhas.
