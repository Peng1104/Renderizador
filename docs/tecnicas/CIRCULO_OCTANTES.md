# Desenho de Círculo por Simetria de Octantes

## 1. Redução ao primeiro octante

Um círculo de raio $r$ centrado na origem tem simetria de 8 vias: o contorno inteiro pode ser obtido refletindo e trocando eixos de um único octante, o trecho onde $0 \le x \le y$ (do ponto mais à direita no eixo $x$ até 45 graus, subindo). Calcular só esse octante e gerar os outros 7 por transformação evita recalcular a equação do círculo 8 vezes.

## 2. Equação do octante

Para cada coordenada inteira $x$ no intervalo $\left[0,\; \lfloor r/\sqrt{2} \rfloor\right]$ (o limite onde $x = y$ no octante, já que além desse ponto $x$ passaria a exceder $y$), a coordenada $y$ correspondente vem diretamente da equação do círculo $x^2 + y^2 = r^2$:

$$
y = \left\lfloor \sqrt{r^2 - x^2} \right\rfloor
$$

Isso gera um conjunto de pontos $(x, y)$ com $x$ variando em passos inteiros de 0 até o limite do octante.

## 3. Reflexões para os 8 octantes

Cada um dos 8 octantes do círculo é obtido do primeiro por uma das 8 transformações lineares de reflexão e troca de eixo, cada uma representável como uma matriz $2 \times 2$ aplicada a cada ponto $(x, y)$ do octante base:

| Octante | Matriz | Efeito |
| :--- | :--- | :--- |
| 1 (base) | $\begin{bmatrix}1&0\\0&1\end{bmatrix}$ | identidade |
| 2 | $\begin{bmatrix}0&1\\1&0\end{bmatrix}$ | troca $x \leftrightarrow y$ |
| 3 | $\begin{bmatrix}0&-1\\1&0\end{bmatrix}$ | troca e reflete em $x$ |
| 4 | $\begin{bmatrix}-1&0\\0&1\end{bmatrix}$ | reflete em $x$ |
| 5 | $\begin{bmatrix}-1&0\\0&-1\end{bmatrix}$ | reflete em $x$ e $y$ |
| 6 | $\begin{bmatrix}0&-1\\-1&0\end{bmatrix}$ | troca e reflete em $x$ e $y$ |
| 7 | $\begin{bmatrix}0&1\\-1&0\end{bmatrix}$ | troca e reflete em $y$ |
| 8 | $\begin{bmatrix}1&0\\0&-1\end{bmatrix}$ | reflete em $y$ |

Aplicando as 8 matrizes a cada ponto do octante base e concatenando os resultados, obtém-se o contorno completo do círculo sem nenhuma chamada trigonométrica repetida por octante, só a raiz quadrada usada na equação do octante base.

## 4. Ausência de laço explícito

Como tanto o cálculo do octante base quanto a aplicação das 8 reflexões são operações vetorizadas (a equação do octante é avaliada para todo o intervalo de $x$ de uma vez, e as 8 multiplicações de matriz são aplicadas ao array inteiro de pontos do octante), o círculo inteiro é gerado sem um laço percorrendo pixel por pixel ou octante por octante.
