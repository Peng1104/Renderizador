# Back-Face Culling

## 1. Convenção de enrolamento

Todo triângulo 3D deste renderizador segue a convenção anti-horária (CCW, counter-clockwise) quando observado do lado de fora da superfície, olhando na direção contrária à câmera. Um triângulo cujos vértices, projetados em tela, aparecem em sentido horário está de costas para a câmera: é a face interna de um sólido fechado, ou a parte de trás de uma superfície aberta, e não deveria contribuir pixel algum à imagem final.

## 2. Área assinada como teste de orientação

A área assinada de um triângulo com vértices $(x_0, y_0)$, $(x_1, y_1)$, $(x_2, y_2)$, já em coordenadas de tela, é:

$$
A = (x_1 - x_0)(y_2 - y_0) - (y_1 - y_0)(x_2 - x_0)
$$

O valor absoluto de $A$ é o dobro da área geométrica do triângulo; o sinal indica o sentido de enrolamento. Como o eixo $y$ da tela cresce para baixo (convenção de imagem, ao contrário do eixo $y$ do NDC), um triângulo que é CCW no espaço da câmera aparece com área assinada negativa em coordenadas de tela:

$$
\text{triângulo de frente} \iff A < 0
$$

## 3. Descarte antes da rasterização

Triângulos com $A \ge 0$ (de costas, ou degenerados com área nula) são descartados antes de qualquer varredura de pixels: nenhuma função de aresta é avaliada para eles. Numa malha fechada típica, isso elimina cerca de metade dos triângulos do custo de rasterização, já que toda malha fechada tem aproximadamente tantas faces de frente quanto de costas em relação a uma câmera qualquer.

## 4. Vetorização sobre vários triângulos

Como o teste depende só das coordenadas de tela já projetadas dos 3 vértices, ele é calculado para todos os triângulos de uma malha de uma só vez, antes do laço que rasteriza cada um individualmente: um array de áreas assinadas é obtido substituindo os índices de vértice de cada triângulo na fórmula acima, e a máscara booleana resultante ($A < 0$) filtra de uma vez os índices dos triângulos de frente, sem laço explícito por triângulo nessa etapa.
