# Transparência (Alpha Blending)

## 1. Transparência como opacidade complementar

O material X3D define um campo de transparência em $[0, 1]$, onde 0 é totalmente opaco e 1 é totalmente transparente (invisível). A opacidade usada na mistura de cores é o complemento desse valor:

$$
\alpha = 1 - \text{transparency}
$$

Com $\alpha = 1$ (transparência 0, caso comum de geometria opaca), a mistura descrita abaixo se reduz a uma escrita direta, sem custo adicional de cálculo.

## 2. Equação de mistura (alpha blending)

Para cada subamostra que passa no teste de z-buffer (ver documento correspondente), a cor final escrita no buffer não substitui o que já estava lá; ela é combinada com a cor de fundo já presente naquela subamostra, ponderada por $\alpha$:

$$
\text{cor}_{\text{final}} = \alpha \cdot \text{cor}_{\text{frente}} + (1 - \alpha) \cdot \text{cor}_{\text{fundo}}
$$

Essa é a operação clássica de compositing "over": a cor da frente domina totalmente quando $\alpha = 1$, contribui nada quando $\alpha = 0$ (a subamostra permanece com a cor de fundo, como se a geometria fosse invisível), e mistura proporcionalmente nos valores intermediários.

## 3. Dependência da ordem de desenho

A mistura descrita acima só produz o resultado visualmente correto quando a geometria transparente é desenhada depois de tudo que deveria aparecer atrás dela, já que cada mistura usa como fundo o que já estava no buffer naquele instante, sem nenhuma forma de reordenar contribuições já escritas. Este renderizador não ordena a geometria por profundidade antes de desenhar; a correção da mistura depende inteiramente da ordem em que os nós aparecem no grafo de cena. Isso é suficiente para cenas onde a ordem de desenho já é aproximadamente de trás para frente, mas não resolve o caso geral de várias camadas transparentes que se cruzam em ordens diferentes dependendo do ponto de vista, problema conhecido na literatura como ordenação de transparência (transparency sorting) e que exigiria uma técnica adicional (ordenação por profundidade por primitivo, ou um algoritmo de composição independente de ordem) para ser resolvido de forma geral.

## 4. Interação com o teste de profundidade

Geometria transparente continua sendo testada contra o z-buffer e descartada onde geometria opaca mais próxima da câmera já a cobre (ver documento de z-buffer), mas não escreve sua própria profundidade no buffer. Isso evita que peças transparentes se ocluam umas às outras pelo teste de profundidade: duas superfícies transparentes sobrepostas, ambas mais próximas que qualquer geometria opaca ao redor, precisam de suas cores combinadas pela equação de mistura acima, não de uma delas vencendo e escondendo a outra como aconteceria com um teste de profundidade convencional de escrita habilitada.
