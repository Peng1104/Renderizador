# Animação: TimeSensor, ROUTE e Interpoladores

## 1. Visão geral

Uma animação X3D é uma cadeia de três nós ligados por eventos. O relógio gera uma fração de tempo, o interpolador converte essa fração em um valor (uma posição ou uma rotação) e um nó de transformação consome o valor:

$$
\text{TimeSensor} \xrightarrow{\text{fraction\_changed}} \text{Interpolador} \xrightarrow{\text{value\_changed}} \text{Transform}
$$

Cada seta é uma ligação declarada por um `ROUTE`. Tudo é recalculado a cada frame; nada é acumulado de um frame para o outro além do instante em que o relógio começou.

## 2. Fração de tempo (TimeSensor)

O relógio mede o tempo decorrido $\Delta t$ desde a primeira vez que um TimeSensor foi avaliado e o converte em uma fração do ciclo de duração $T$ (`cycleInterval`):

| Modo | Fração $f$ |
| :--- | :--- |
| `loop` verdadeiro | $f = \dfrac{\Delta t \bmod T}{T}$, sempre em $[0, 1)$ |
| `loop` falso | $f = \min\!\left(\dfrac{\Delta t}{T},\ 1\right)$, cresce até 1 e fica lá |

## 3. Propagação de eventos (ROUTE)

Um `ROUTE` copia o valor de um campo de saída de um nó nomeado para um campo de entrada de outro. A ordem em que os `ROUTE` aparecem no arquivo não pode importar, então a atualização é resolvida por dependência, a partir dos nós de destino:

1. Para cada nó de destino, procurar todos os `ROUTE` que chegam nele.
2. Antes de copiar o valor de cada um, resolver recursivamente o nó de origem daquele `ROUTE` (que, por sua vez, resolve as origens que chegam nele).
3. Executar os `ROUTE` e, por fim, atualizar o próprio nó.

Cada nó é resolvido no máximo uma vez por frame. Isso garante que a cadeia relógio, interpolador e Transform saia consistente no mesmo frame, e impede laços infinitos entre `ROUTE` que se referenciam em círculo. Só depois dessa fase os nós visuais da cena são desenhados, já enxergando os valores atualizados.

## 4. Localização do segmento de chaves

Um interpolador recebe uma lista de chaves $k_0 < k_1 < \dots < k_{N-1}$ e um valor associado a cada uma. Dada a fração $f$ de entrada, o primeiro passo é achar o segmento $[k_i, k_{i+1}]$ que a contém e a posição relativa $t$ dentro dele:

$$
t = \frac{f - k_i}{k_{i+1} - k_i}
$$

Se $f \le k_0$ o resultado é o primeiro valor; se $f \ge k_{N-1}$ é o último. Uma lista de chaves vazia, ou com tamanho diferente da lista de valores, produz o valor neutro (posição na origem, rotação nula).

## 5. Posição: spline cúbica de Hermite (SplinePositionInterpolator)

Interpolar linearmente entre posições produz um caminho com quinas nas chaves. A spline cúbica de Hermite passa por todas as chaves com velocidade contínua, usando como entrada os valores $v_i$ e as derivadas $m_i$ de cada chave.

### 5.1 Derivadas (Catmull-Rom)

A derivada em cada chave interna é a diferença central entre os vizinhos, dividida pela distância entre as chaves vizinhas:

$$
m_i = \frac{v_{i+1} - v_{i-1}}{k_{i+1} - k_{i-1}}
$$

Para chaves igualmente espaçadas isso vale $(v_{i+1} - v_{i-1})/2$ na escala de $t$. Os extremos dependem do campo `closed`:

| Caso | Derivadas das extremidades |
| :--- | :--- |
| Aberto | $m_0 = m_{N-1} = 0$ (o movimento começa e termina parado) |
| Fechado | Os vizinhos dão a volta: o anterior à primeira chave é a penúltima, e o posterior à última é a segunda; as duas extremidades recebem a mesma derivada, o que fecha o laço sem quina |

O modo fechado só vale se houver mais de duas chaves e o primeiro e o último valor forem idênticos; caso contrário é tratado como aberto.

### 5.2 Avaliação

Com $t$ do segmento e $\Delta k = k_{i+1} - k_i$, a posição é a combinação dos quatro polinômios de base de Hermite:

$$
\begin{aligned}
h_{00}(t) &= 2t^3 - 3t^2 + 1 & h_{10}(t) &= t^3 - 2t^2 + t \\
h_{01}(t) &= -2t^3 + 3t^2 & h_{11}(t) &= t^3 - t^2
\end{aligned}
$$

$$
P(t) = h_{00}\, v_i + h_{10}\, \Delta k\, m_i + h_{01}\, v_{i+1} + h_{11}\, \Delta k\, m_{i+1}
$$

Os fatores $h_{00}$ e $h_{01}$ ponderam os valores nas pontas; $h_{10}$ e $h_{11}$ ponderam as tangentes. A multiplicação por $\Delta k$ converte a derivada em relação à chave para a escala local $t \in [0, 1]$.

## 6. Orientação: SLERP de quatérnios (OrientationInterpolator)

Interpolar eixo e ângulo componente a componente não gira o objeto a uma velocidade constante e pode passar por rotações intermediárias sem sentido. A interpolação é feita sobre quatérnios unitários, onde cada rotação é um ponto na esfera unitária de $\mathbb{R}^4$.

### 6.1 Conversões

Uma rotação de ângulo $\theta$ em torno do eixo unitário $\hat{u}$ vira o quatérnio $q = (w, \mathbf{v})$:

$$
q = \left(\cos\tfrac{\theta}{2},\ \sin\tfrac{\theta}{2}\, \hat{u}\right)
$$

A volta é $\theta = 2\arccos(w)$ e $\hat{u} = \mathbf{v}/\sqrt{1 - w^2}$. Quando $\sqrt{1 - w^2}$ é quase zero a rotação é nula e o eixo é indefinido; o resultado é a rotação nula $(0, 0, 1, 0)$.

### 6.2 Slerp

O slerp percorre o arco de círculo máximo entre $q_0$ e $q_1$ com velocidade angular constante. Com $\cos\Omega = q_0 \cdot q_1$:

$$
\text{slerp}(q_0, q_1, t) = \frac{\sin((1-t)\,\Omega)}{\sin \Omega}\, q_0 + \frac{\sin(t\,\Omega)}{\sin \Omega}\, q_1
$$

Dois detalhes numéricos são tratados antes da fórmula:

1. **Caminho mais curto:** $q$ e $-q$ representam a mesma rotação. Se $q_0 \cdot q_1 < 0$, $q_1$ é negado, para que a interpolação percorra o arco menor em vez de dar a volta longa.
2. **Quatérnios quase paralelos:** se $q_0 \cdot q_1 > 0{,}9995$, $\sin\Omega$ é quase zero e a divisão é instável. Nesse caso usa-se a interpolação linear $q_0 + t(q_1 - q_0)$, seguida de normalização, que é indistinguível do slerp para ângulos tão pequenos.

O quatérnio resultante é convertido de volta para eixo e ângulo, que é o formato que o campo de rotação do Transform consome.

## 7. Encadeamento no frame

Para um frame num instante $\Delta t$, com um TimeSensor, um SplinePositionInterpolator ligado a `translation` e um OrientationInterpolator ligado a `rotation` de um mesmo Transform:

1. O relógio calcula $f$ a partir de $\Delta t$ (seção 2).
2. Os dois interpoladores localizam o segmento de $f$ (seção 4).
3. A posição sai da spline de Hermite (seção 5) e a rotação, do slerp (seção 6).
4. Os `ROUTE` gravam os dois resultados nos campos do Transform (seção 3).
5. Ao desenhar, o Transform monta sua matriz com a translação e a rotação recém-gravadas.
