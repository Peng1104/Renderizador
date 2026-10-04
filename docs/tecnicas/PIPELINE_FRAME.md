# Como um Frame é Gerado

Este documento segue um frame do início ao fim, na ordem em que as técnicas são aplicadas. Cada etapa diz o que entra, qual técnica transforma o dado e o que sai para a etapa seguinte. Os detalhes matemáticos de cada técnica estão nos documentos citados.

## 1. Visão geral

$$
\text{Arquivo X3D} \to \text{Cena} \to \underbrace{\text{Eventos} \to \text{Câmera} \to \text{Luzes} \to \text{Geometria}}_{\text{percorrido a cada frame}} \to \text{Buffers} \to \text{Imagem}
$$

| Fase | Etapas | Resultado |
| :--- | :--- | :--- |
| Preparação (uma vez) | 2 | Buffers alocados e cena lida |
| Por frame | 3 a 9 | Buffer de subamostras preenchido |
| Fim do frame | 10 | Imagem final |

## 2. Preparação (uma vez por execução)

1. O arquivo X3D é lido e a árvore de nós é montada. Os nós são reordenados para que a câmera venha primeiro, depois a informação de navegação, as luzes, a geometria na ordem do arquivo e, por último, a névoa.
2. A imagem é renderizada em uma resolução ampliada pelo fator de supersampling $s$: com largura $W$ e altura $H$ finais, o desenho acontece em $sW \times sH$ (ver [Anti-Aliasing por Supersampling](ANTIALIASING_SUPERSAMPLING.md)).
3. Dois buffers são alocados nessa resolução ampliada, ambos com uma grade $2 \times 2$ de subamostras por pixel (ver [Anti-Aliasing por Multisampling](ANTIALIASING_MSAA.md)):

| Buffer | Conteúdo por subamostra | Valor inicial |
| :--- | :--- | :--- |
| Cor | RGB de 8 bits | Cor de limpeza |
| Profundidade | $z$ de NDC | $1$ (plano distante) |

## 3. Início do frame: limpeza

Os dois buffers voltam ao valor inicial e a lista de luzes é esvaziada. Nada do frame anterior sobrevive, exceto o instante em que o relógio de animação começou.

## 4. Eventos: animação

Se a cena tem animação, os valores que ela produz precisam estar prontos antes que qualquer coisa seja desenhada. Ordem das técnicas (ver [Animação: TimeSensor, ROUTE e Interpoladores](ANIMACAO_INTERPOLADORES.md)):

1. **TimeSensor** converte o tempo decorrido em uma fração $f \in [0, 1]$ do ciclo.
2. **ROUTE** leva $f$ ao interpolador, resolvendo as dependências entre nós de trás para frente.
3. **Interpolador** localiza o segmento de chaves de $f$ e calcula o valor: spline de Hermite para posição, slerp de quatérnios para rotação.
4. **ROUTE** grava o valor nos campos `translation` e `rotation` de um Transform.

## 5. Câmera

O nó Viewpoint define as duas matrizes que levam o mundo à tela (ver [Transformações Geométricas](TRANSFORMACOES.md) e [Projeção Perspectiva](PROJECAO_PERSPECTIVA.md)):

$$
M_{\text{view}} = (T_{\text{cam}} R_{\text{cam}})^{-1}, \qquad M_{\text{proj}} = \text{perspectiva}(\text{fov}, \text{aspecto}, n, f)
$$

A posição da câmera em mundo também é guardada, pois o brilho especular depende dela. O campo de visão se aplica à menor dimensão da tela.

## 6. Luzes

Antes de qualquer geometria, as luzes entram na lista do frame (ver [Luzes](LUZES.md)):

1. Se `headlight` está ligado, a luz da câmera é criada com a direção do olhar em mundo.
2. Cada luz direcional tem sua direção levada ao mundo pela transformação corrente e é guardada com cor, intensidade e componente ambiente.

## 7. Percurso da árvore: transformações

A árvore é percorrida em profundidade. A cada nó Transform, a matriz local $T R S$ (escala, depois rotação, depois translação) é multiplicada pela do topo de uma pilha e empilhada; ao sair do nó, é desempilhada. Qualquer geometria visitada dentro dele usa a matriz do topo da pilha como sua matriz de modelo $M$. O Transform animado da etapa 4 entra aqui, já com os valores novos.

## 8. Geometria 3D: de nó a triângulos projetados

Cada nó Shape combina uma aparência (cores do Material, textura, transparência) com uma geometria. A geometria passa pelas seguintes técnicas, nesta ordem.

### 8.1 Obter triângulos

| Nó | Técnica | Documento |
| :--- | :--- | :--- |
| Box, Sphere, Cone, Cylinder | Tesselação paramétrica | [Tesselação das Primitivas](TESSELACAO_PRIMITIVAS.md) |
| IndexedFaceSet | Triangulação de faces em leque | [Triangulação](TRIANGULACAO.md) |
| TriangleStripSet, IndexedTriangleStripSet | Triangulação de tiras | [Triangulação](TRIANGULACAO.md) |
| TriangleSet | Cada três vértices já são um triângulo | |

### 8.2 Projetar os vértices

Cada vértice $\mathbf{p}$ em coordenadas de objeto percorre o pipeline geométrico (ver [Projeção Perspectiva](PROJECAO_PERSPECTIVA.md)):

$$
\mathbf{c} = M_{\text{proj}}\, M_{\text{view}}\, M\, \begin{pmatrix}\mathbf{p} \\ 1\end{pmatrix}
\quad\to\quad
\text{NDC} = \frac{\mathbf{c}_{xyz}}{c_w}
\quad\to\quad
\begin{cases} x_t = \dfrac{x_{\text{ndc}} + 1}{2}\, sW \\[2mm] y_t = \dfrac{1 - y_{\text{ndc}}}{2}\, sH \end{cases}
$$

Cada vértice produz então quatro números: a posição de tela $(x_t, y_t)$, o $w$ de clip (guardado para a correção de perspectiva) e o $z$ de NDC (guardado para o z-buffer).

### 8.3 Descartar faces de costas

A área assinada de cada triângulo na tela decide se ele está voltado para a câmera (ver [Back-Face Culling](BACKFACE_CULLING.md)):

$$
A = (x_1 - x_0)(y_2 - y_0) - (y_1 - y_0)(x_2 - x_0)
$$

Triângulos com $A \ge 0$ (de costas ou degenerados) são removidos antes de qualquer outro cálculo, o que elimina cerca de metade dos triângulos de um sólido fechado.

### 8.4 Preparar a rasterização

Para cada triângulo restante, calculam-se os coeficientes das três funções de aresta e a bounding box em pixels (ver [Rasterização de Triângulos por Função de Aresta](RASTERIZACAO_TRIANGULOS.md)).

### 8.5 Escolher a fonte de cor

A cor depende do nó e do que o material e a cena oferecem. Em um IndexedFaceSet, textura e cor por vértice ou por face têm prioridade sobre o resto e são aplicadas sem iluminação; a iluminação só entra no caso final:

| Ordem | Condição | Cor da subamostra |
| :--- | :--- | :--- |
| 1 | IndexedFaceSet com textura e coordenadas de textura | Cor amostrada da textura, sem iluminação (ver [Mapeamento de Textura](MAPEAMENTO_TEXTURA.md)) |
| 2 | IndexedFaceSet com cor por vértice | Cor interpolada entre os vértices, sem iluminação |
| 3 | IndexedFaceSet com cor por face | Cor da face de origem do triângulo, sem iluminação |
| 4 | Cena com luzes | Equação de Phong (ver [Modelo de Iluminação de Phong](MODELO_PHONG.md)); nas primitivas com textura, a difusa vem da textura |
| 5 | Primitiva com textura, sem luzes | Cor amostrada da textura |
| 6 | Nenhuma das anteriores | Cor emissiva do material |

Para a iluminação, as posições e as normais são levadas ao mundo (as normais pela inversa transposta, ver [Luzes](LUZES.md)). As primitivas trazem normais por vértice da tesselação; as demais geometrias usam a normal plana de cada triângulo, o produto vetorial de duas arestas.

## 9. Rasterização

Aqui os triângulos viram cor nas subamostras. Há dois caminhos para o mesmo resultado (ver [Rasterização em Lote](RASTERIZACAO_LOTE.md)):

| Caminho | Quando é usado |
| :--- | :--- |
| Em lote | Geometria opaca, pelo menos 8 triângulos e poucas subamostras por triângulo |
| Triângulo a triângulo | Todo o resto, incluindo toda geometria translúcida |

Em ambos, cada subamostra passa por esta sequência:

1. **Cobertura:** a subamostra está dentro do triângulo se as três funções de aresta têm o mesmo sinal. Isso dá os pesos baricêntricos $\lambda_i$.
2. **Teste de profundidade:** $z = \sum \lambda_i z_i$ é comparado ao z-buffer, e a subamostra só segue se $z \le z_{\text{buffer}}$ (ver [Z-Buffer](ZBUFFER.md)). Geometria translúcida faz o teste, mas não grava a profundidade.
3. **Pesos perspectiva-corretos:** $\lambda_i' \propto \lambda_i / w_i$, normalizados para somar 1 (ver [Interpolação Perspectiva-Correta](INTERPOLACAO_PERSPECTIVA.md)).
4. **Atributos:** com $\lambda'$, interpolam-se a cor, o UV, e para a iluminação, a posição e a normal de mundo.
5. **Cor:** a fonte escolhida em 8.5 produz o RGB. Se houver textura, o nível de mipmap é escolhido por triângulo (ver [Mipmap](MIPMAP.md)).
6. **Escrita:** o RGB vai para a subamostra. Com $\alpha = 1 - \text{transparência} < 1$ a cor é misturada ao que já estava lá (ver [Transparência](TRANSPARENCIA.md)):

$$
C = \alpha\, C_{\text{frente}} + (1 - \alpha)\, C_{\text{fundo}}
$$

## 10. Geometria 2D

Os nós 2D não passam pelas etapas 8.1 a 8.3: as coordenadas já estão em pixels, não há câmera, matriz de modelo nem iluminação, e a cor é sempre a emissiva do material.

| Nó | Técnica |
| :--- | :--- |
| Polypoint2D | Escrita direta do pixel de cada ponto |
| Polyline2D | Linha com anti-aliasing por cobertura (ver [Anti-Aliasing de Linhas](ANTIALIASING_LINHAS.md)) |
| Circle2D | Um octante calculado e refletido nos outros sete (ver [Desenho de Círculo por Simetria de Octantes](CIRCULO_OCTANTES.md)) |
| TriangleSet2D | Rasterização por função de aresta, com cobertura e escrita como na etapa 9 |

## 11. Fim do frame: da subamostra à imagem

Quando toda a árvore foi percorrida, o buffer de cor ainda tem $2 \times 2$ valores por pixel. Dois filtros de média o reduzem à resolução final, nesta ordem:

1. **Resolve do multisampling:** a cor de cada pixel é a média das suas 4 subamostras. O resultado tem tamanho $sW \times sH$.
2. **Redução do supersampling:** cada bloco $s \times s$ vira um pixel pela média (filtro de caixa), arredondada. O resultado tem tamanho $W \times H$, a resolução final.

A imagem final é exibida na janela ou salva em arquivo. Com $s = 1$ a segunda etapa não altera nada, e o anti-aliasing vem só do multisampling.

## 12. Exemplo completo: esfera texturizada e iluminada

Cena: uma Sphere com textura de imagem, dentro de um Transform animado por um TimeSensor, com uma DirectionalLight. Para um frame, a cadeia de técnicas e o dado que passa entre elas:

| # | Técnica | Entra | Sai |
| :--- | :--- | :--- | :--- |
| 1 | Limpeza | Buffers do frame anterior | Cor de fundo e profundidade 1 |
| 2 | TimeSensor | Tempo decorrido | Fração $f$ |
| 3 | ROUTE | $f$ | $f$ no interpolador |
| 4 | Slerp | $f$ e rotações-chave | Rotação do Transform |
| 5 | Viewpoint | Posição, orientação, fov | $M_{\text{view}}$ e $M_{\text{proj}}$ |
| 6 | Luz direcional | Direção local | Direção em mundo na lista de luzes |
| 7 | Transform | Translação, rotação, escala | Matriz $M$ no topo da pilha |
| 8 | Tesselação | Raio | 2304 triângulos com normais e UV |
| 9 | Projeção | Vértices e $M_{\text{proj}} M_{\text{view}} M$ | $(x_t, y_t, w, z)$ por vértice |
| 10 | Back-face culling | Triângulos projetados | Triângulos voltados para a câmera |
| 11 | Funções de aresta | Triângulos restantes | Coeficientes e bounding boxes |
| 12 | Rasterização em lote | Triângulos opacos | Subamostras vencedoras no z-buffer |
| 13 | Interpolação perspectiva-correta | Pesos $\lambda$ e $w$ | Posição, normal e UV por subamostra |
| 14 | Mapeamento de textura e mipmap | UV e nível | Cor difusa da textura |
| 15 | Phong | Normal, posição, difusa, luz | Cor iluminada |
| 16 | Resolve MSAA | $2 \times 2$ subamostras por pixel | Um pixel por posição |
| 17 | Redução do supersampling | Blocos $s \times s$ | Imagem final $W \times H$ |
