# Rasterização de Triângulos por Função de Aresta

## 1. O problema

Depois que os 3 vértices de um triângulo já estão projetados em coordenadas de tela, é preciso decidir, para cada pixel candidato, se ele está dentro ou fora do triângulo. A técnica usada aqui é a de função de aresta (edge function), que testa esse pertencimento com uma única operação aritmética por aresta, sem percorrer o contorno do polígono nem calcular interseções de retas.

## 2. Função de aresta

Para uma aresta que vai do vértice $a = (a_x, a_y)$ até o vértice $b = (b_x, b_y)$, com $(dx, dy) = (b_x - a_x,\, b_y - a_y)$, a função de aresta de um ponto $p = (p_x, p_y)$ é:

$$
E(p) = dy \cdot p_x - dx \cdot p_y + (a_y \cdot dx - a_x \cdot dy)
$$

Essa expressão é o componente $z$ do produto vetorial entre o vetor da aresta $(b - a)$ e o vetor do vértice ao ponto $(p - a)$, e seu sinal indica de que lado da reta que passa por $a$ e $b$ o ponto $p$ está: positivo de um lado, negativo do outro, zero exatamente sobre a reta.

## 3. Teste de dentro do triângulo

Um triângulo com vértices $v_0, v_1, v_2$ tem 3 arestas, $v_0 \to v_1$, $v_1 \to v_2$ e $v_2 \to v_0$. Um ponto está dentro do triângulo quando o sinal da função de aresta é o mesmo (todas positivas ou todas negativas, dependendo do sentido de enrolamento dos vértices) nas 3 arestas simultaneamente:

$$
p \in \triangle v_0 v_1 v_2 \iff \big(E_0(p) \ge 0 \land E_1(p) \ge 0 \land E_2(p) \ge 0\big) \lor \big(E_0(p) \le 0 \land E_1(p) \le 0 \land E_2(p) \le 0\big)
$$

Testar as duas polaridades em vez de fixar uma só torna o teste independente do sentido de enrolamento do triângulo (horário ou anti-horário), o que importa porque a projeção em tela pode inverter a orientação original de um triângulo dependendo da posição da câmera.

## 4. Varredura por bounding box

Calcular a função de aresta para cada pixel da tela seria desperdício; em vez disso, delimita-se um retângulo (bounding box) que envolve os 3 vértices projetados, recortado aos limites da tela:

$$
x_{\min} = \max(0, \lfloor \min(x_0, x_1, x_2) \rfloor), \qquad x_{\max} = \min(\text{largura} - 1, \lceil \max(x_0, x_1, x_2) \rceil)
$$

e de forma análoga para $y_{\min}$ e $y_{\max}$. Só os pixels dentro desse retângulo são testados contra as 3 funções de aresta; se o retângulo cai inteiramente fora da tela ($x_{\min} > x_{\max}$ ou $y_{\min} > y_{\max}$), o triângulo não cobre pixel algum e a varredura é descartada sem nenhum teste.

## 5. Coordenadas baricêntricas a partir da função de aresta

Além de decidir dentro/fora, o valor de cada função de aresta num ponto é proporcional ao peso baricêntrico do vértice oposto àquela aresta. Como a soma das 3 funções de aresta é constante em todo o triângulo (o dobro da área assinada do triângulo, com sinal dependente do enrolamento), os pesos baricêntricos normalizados de um ponto $p$ são:

$$
\lambda_0 = \frac{E_1(p)}{E_0(p) + E_1(p) + E_2(p)}, \quad \lambda_1 = \frac{E_2(p)}{E_0(p) + E_1(p) + E_2(p)}, \quad \lambda_2 = \frac{E_0(p)}{E_0(p) + E_1(p) + E_2(p)}
$$

onde $E_1$ (a aresta $v_1 \to v_2$, oposta a $v_0$) dá o peso de $v_0$, e assim por diante em rotação. Esses pesos somam 1 e são a base tanto do preenchimento com cor sólida (onde não são necessários) quanto da interpolação de atributos por vértice, cor e coordenada de textura (documentada em interpolação perspectiva-correta).
