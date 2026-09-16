# Z-Buffer

## 1. O problema da oclusão

Quando dois triângulos de objetos diferentes ocupam a mesma região da tela mas estão a profundidades diferentes na câmera, o triângulo mais distante não deveria aparecer nos pixels onde o mais próximo o cobre. Sem nenhum mecanismo de profundidade, a única forma de resolver isso é confiar na ordem em que os triângulos são desenhados (o último desenhado vence, um painter's algorithm implícito), o que só produz o resultado correto se a cena inteira for desenhada estritamente do mais distante para o mais próximo. Geometria que se cruza no espaço 3D, onde nenhuma ordem de desenho por objeto inteiro é sempre correta em toda a tela, quebra essa suposição.

## 2. Buffer de profundidade por subamostra

O z-buffer mantém, para cada subamostra de cada pixel (mesma grade usada pelo MSAA, ver documento correspondente), a profundidade do fragmento mais próximo da câmera já desenhado ali no frame atual. O buffer é inicializado (e reiniciado a cada frame) com o valor do plano de corte distante, o mais afastado possível, para que qualquer geometria desenhada vença o teste por padrão na primeira vez que toca aquela subamostra.

## 3. Valor de profundidade usado

O valor de profundidade armazenado é o componente $z$ de NDC (ver documento de projeção perspectiva), que varia monotonicamente de $-1$ no plano de corte próximo a $1$ no plano de corte distante, com a propriedade de ser afim nas coordenadas de tela do triângulo (ver documento de interpolação perspectiva-correta). Isso permite interpolar a profundidade de cada subamostra com os pesos baricêntricos brutos $\lambda_0, \lambda_1, \lambda_2$ (sem a correção de perspectiva usada para outros atributos):

$$
z(p) = \lambda_0 z_0 + \lambda_1 z_1 + \lambda_2 z_2
$$

onde $z_0, z_1, z_2$ são os valores de $z$ de NDC dos 3 vértices do triângulo.

## 4. Teste e atualização

Para cada subamostra coberta pelo triângulo, a profundidade interpolada $z(p)$ é comparada com o valor já registrado no buffer, $z_{\text{atual}}$:

$$
\text{aprovado}(p) \iff z(p) \le z_{\text{atual}}(p)
$$

Subamostras aprovadas (mais perto da câmera, ou empatadas, com o que já estava lá) têm o buffer atualizado com a nova profundidade e são as únicas que seguem adiante para a etapa de escrita de cor; as reprovadas são descartadas sem nenhum efeito no framebuffer, preservando o que já tinha sido desenhado ali por geometria mais próxima. Como o teste e a atualização acontecem por subamostra, dois triângulos que se cruzam dentro de um mesmo pixel produzem uma borda de oclusão sub-pixel, não uma decisão única por pixel inteiro.

## 5. Geometria transparente: teste sem escrita

Para geometria com transparência (ver documento de transparência), a comparação contra o buffer ainda acontece (a geometria transparente continua sendo ocluída por, e não aparece através de, geometria opaca mais próxima da câmera), mas a atualização do buffer é pulada. Se a escrita não fosse pulada, duas peças transparentes sobrepostas, desenhadas em sequência, se ocluiriam mutuamente pelo teste de profundidade em vez de se misturarem opticamente, quebrando o efeito de transparência entre elas mesmas.
