# Anti-Aliasing por Multisampling (MSAA)

## 1. O problema do serrilhado

Um rasterizador que decide, por pixel inteiro, se o centro (ou qualquer ponto único) do pixel está dentro ou fora de um triângulo produz bordas em escada (aliasing): um pixel cujo centro cai fora do triângulo por uma fração mínima de distância recebe cor de fundo inteira, mesmo que a maior parte da área do pixel esteja coberta pelo triângulo.

## 2. Grade de subamostras por pixel

O MSAA resolve isso avaliando a cobertura em vários pontos dentro de cada pixel, não só no centro. Este renderizador usa uma grade $m \times m$ de subamostras por pixel (com $m = 2$, 4 subamostras por pixel, 4x MSAA), centralizadas em cada célula de $1/m$ de um pixel:

$$
\text{deslocamentos} = \left\{ \frac{k + 0.5}{m} : k = 0, 1, \dots, m-1 \right\}
$$

Com $m = 2$, isso dá os deslocamentos $0.25$ e $0.75$ dentro do pixel, tanto no eixo $x$ quanto no $y$, gerando 4 pontos de amostra por pixel.

## 3. Teste de cobertura por subamostra

Cada uma das $m \times m$ subamostras de cada pixel do bounding box do triângulo é testada individualmente contra as 3 funções de aresta (ver documento de rasterização de triângulos), da mesma forma que um pixel inteiro seria testado num rasterizador sem antialiasing. As subamostras que caem dentro do triângulo recebem a cor do triângulo (ou, num preenchimento não-flat, o atributo interpolado naquele ponto exato); as demais permanecem com o que já estava lá.

## 4. Buffer de multisample e resolve

Cada subamostra de cada pixel guarda sua própria cor, num buffer com uma dimensão extra em relação a um framebuffer comum: para uma tela de $\text{largura} \times \text{altura}$ pixels, o buffer tem forma $(\text{altura}, \text{largura}, m, m, 3)$. Ao longo do desenho de uma cena, cada subamostra é sobrescrita pela cor do último triângulo que a cobriu, exatamente como um framebuffer comum seria sobrescrito por primitivo, só que por subamostra em vez de por pixel inteiro.

Depois que toda a cena de um frame foi desenhada, um único passo de resolve calcula a cor final de cada pixel como a média das suas $m \times m$ subamostras:

$$
\text{cor}(x, y) = \frac{1}{m^2} \sum_{i=0}^{m-1} \sum_{j=0}^{m-1} \text{buffer}(x, y, i, j)
$$

Fazer esse resolve só uma vez ao final do frame, em vez de misturar a cobertura parcial de cada primitivo direto no framebuffer final no momento em que é desenhado, evita blending duplicado em bordas de geometria adjacente: dois triângulos vizinhos que compartilham uma aresta exata não deixam nenhuma lacuna nem sobreposição visível entre si, porque cada subamostra é decidida uma única vez pelo último primitivo que a cobriu, e a média só acontece depois que a cena inteira já decidiu o dono de cada subamostra.

## 5. Cobertura fracionária vinda de outra fonte

Quando a cobertura de um pixel já vem calculada como um valor contínuo em $[0, 1]$ por outro algoritmo (como o anti-aliasing analítico de linhas, ver documento correspondente), essa fração é quantizada para o número de subamostras que ela ocuparia na grade $m \times m$: com cobertura $c$, o número de subamostras marcadas é $\text{round}(c \cdot m^2)$, escolhendo sempre as primeiras dessa contagem numa ordem fixa entre as $m^2$ posições da grade. Isso reproduz a mesma limitação de qualquer MSAA real, cobertura representável só em $m^2 + 1$ níveis discretos, não um contínuo, mas mantém a cobertura fracionária de linhas compatível com o mesmo buffer usado para triângulos.
