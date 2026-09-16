# Anti-Aliasing por Supersampling (SSAA)

## 1. Relação com o MSAA

O MSAA (ver documento correspondente) resolve o aliasing de borda avaliando várias subamostras por pixel dentro do próprio rasterizador. O supersampling (SSAA, supersample anti-aliasing) ataca o mesmo problema de outra camada, acima do rasterizador: a cena inteira é desenhada numa resolução maior que a resolução final de saída, e o resultado é reduzido por um filtro de média. As duas técnicas são independentes e compostas neste renderizador: o SSAA é opcional (fator 1 por padrão, equivalente a desligado) e atua depois que o MSAA já resolveu sua própria super-amostragem por subamostra.

## 2. Resolução de desenho ampliada

Com um fator de supersampling $s$ e uma resolução de saída desejada $\text{largura} \times \text{altura}$, toda a cena é desenhada internamente numa resolução $s$ vezes maior em cada eixo:

$$
\text{largura}_{\text{render}} = s \cdot \text{largura}, \qquad \text{altura}_{\text{render}} = s \cdot \text{altura}
$$

O pipeline de projeção (matrizes de view e projeção, viewport) e a rasterização MSAA operam inteiramente nessa resolução ampliada, sem nenhuma mudança de algoritmo; da perspectiva do rasterizador, é como se a tela fosse simplesmente maior.

## 3. Redução por filtro de caixa

Depois que o frame foi desenhado e o MSAA já foi resolvido (médias de subamostra já viraram uma cor por pixel na resolução ampliada), a imagem de $\text{largura}_{\text{render}} \times \text{altura}_{\text{render}}$ é reduzida para a resolução final $\text{largura} \times \text{altura}$ pela média de cada bloco de $s \times s$ pixels:

$$
\text{cor}_{\text{final}}(x, y) = \frac{1}{s^2} \sum_{i=0}^{s-1} \sum_{j=0}^{s-1} \text{cor}_{\text{render}}(s \cdot x + i,\; s \cdot y + j)
$$

Esse é um filtro de caixa (box filter): cada pixel de saída é a média não ponderada dos $s^2$ pixels de entrada que caem no seu bloco correspondente, sem sobreposição entre blocos vizinhos.

## 4. Por que compor as duas técnicas

MSAA por si só suaviza bordas de geometria (silhuetas de triângulos), porque testa vários pontos dentro de cada pixel contra as arestas do triângulo, mas dentro de cada subamostra o resultado ainda é um teste binário, dentro ou fora, sem suavização adicional. Aumentar a resolução de desenho via SSAA reduz ainda mais o tamanho de qualquer detalhe de borda que sobreviveria intacto a uma única passada de MSAA, útil sobretudo quando o fator de MSAA já fixo ($m = 2$, 4 subamostras) não é suficiente para uma cena com muitas arestas próximas ou padrões de alta frequência. O custo é multiplicativo: dobrar $s$ multiplica por 4 o número de pixels rasterizados, e cada um deles já carrega o custo do MSAA por baixo.
