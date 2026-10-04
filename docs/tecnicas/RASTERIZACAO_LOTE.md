# Rasterização em Lote

## 1. O problema da varredura triângulo a triângulo

A varredura clássica processa um triângulo por vez: gera as subamostras da sua bounding box, testa cobertura, testa profundidade e, para cada subamostra aprovada, calcula a cor e a escreve. Em malhas com milhares de triângulos pequenos, dois custos dominam:

1. **Custo fixo por triângulo:** cada triângulo repete a mesma preparação (alocar arrays, montar subamostras) para pouquíssimas subamostras úteis.
2. **Cor calculada e descartada:** a cor (inclusive a iluminação de Phong, a parte mais cara) é calculada para toda subamostra que passa no teste de profundidade naquele instante, mesmo que um triângulo desenhado depois a cubra. Quanto maior a sobreposição entre triângulos, maior o desperdício.

A rasterização em lote resolve a cobertura e o z-buffer de todos os triângulos de um draw call antes de calcular qualquer cor, e só calcula a cor das subamostras que ficaram visíveis.

## 2. Resultado idêntico à varredura

O lote produz exatamente a mesma imagem que a varredura triângulo a triângulo: as mesmas subamostras cobertas, a mesma regra de profundidade e o mesmo desempate. É uma mudança na ordem de trabalho, não no resultado. Por isso a escolha entre os dois caminhos é só uma questão de desempenho (seção 7).

## 3. Etapas

### 3.1 Preparação

As funções de aresta e a bounding box de todos os triângulos são calculadas de uma só vez, em arrays (ver [Rasterização de Triângulos por Função de Aresta](RASTERIZACAO_TRIANGULOS.md)). Com a grade de subamostras $m \times m$ por pixel (aqui $m = 2$), o número de subamostras candidatas de um triângulo com bounding box de $W \times H$ pixels é:

$$
N_{\text{cand}} = (m W)(m H)
$$

Triângulos cuja bounding box está fora da tela têm zero candidatas.

### 3.2 Subamostras candidatas

Todas as candidatas de todos os triângulos do grupo são geradas num único array, na mesma ordem de uma varredura sequencial (triângulo por triângulo, linha por linha). A subamostra $(s_x, s_y)$ do pixel $(x, y)$ é testada no seu centro:

$$
p = \left(x + \frac{s_x + 0{,}5}{m},\ y + \frac{s_y + 0{,}5}{m}\right)
$$

### 3.3 Cobertura

Para cada candidata, as três funções de aresta do triângulo dão as coordenadas baricêntricas não normalizadas. A subamostra está dentro se as três têm o mesmo sinal (todas $\ge 0$ ou todas $\le 0$, o que cobre os dois sentidos de giro). As que ficam fora são descartadas. As coordenadas restantes são normalizadas para somarem 1, resultando nos pesos $\lambda_0, \lambda_1, \lambda_2$.

### 3.4 Teste de profundidade

A profundidade de cada candidata é a interpolação afim do $z$ de NDC dos vértices com os pesos brutos (ver [Z-Buffer](ZBUFFER.md)):

$$
z = \lambda_0 z_0 + \lambda_1 z_1 + \lambda_2 z_2
$$

Passam as candidatas com $z \le z_{\text{buffer}}$, isto é, que não estão atrás do que já foi registrado nessa subamostra.

### 3.5 Desempate entre triângulos

Num lote, várias candidatas aprovadas de triângulos diferentes podem disputar a mesma subamostra. Cada subamostra recebe um identificador único e as candidatas são ordenadas por três chaves, nesta prioridade:

1. Identificador da subamostra, para agrupar as que disputam o mesmo lugar.
2. Profundidade crescente, para que a mais próxima da câmera fique primeiro.
3. Ordem de desenho decrescente, para que em empate de profundidade vença o triângulo desenhado por último.

A primeira candidata de cada grupo é a vencedora. A regra de empate reproduz a de uma varredura sequencial com o teste $z \le z_{\text{buffer}}$, onde um fragmento de mesma profundidade sobrescreve o anterior. A profundidade das vencedoras é então gravada no z-buffer.

### 3.6 Pesos perspectiva-corretos

Atributos interpolados pelo triângulo (cor, UV, posição, normal) precisam da correção de perspectiva (ver [Interpolação Perspectiva-Correta](INTERPOLACAO_PERSPECTIVA.md)). Só para as vencedoras, os pesos são divididos pelo $w$ de clip de cada vértice e renormalizados:

$$
\lambda_i' = \frac{\lambda_i / w_i}{\sum_j \lambda_j / w_j}
$$

### 3.7 Fonte de cor

Uma fonte de cor é a regra que transforma as vencedoras em cores RGB. O lote é independente de como a cor é obtida; quatro fontes existem:

| Fonte | Cor da subamostra |
| :--- | :--- |
| Flat | A cor do triângulo (ou da face de origem) |
| Cor por vértice | Cores dos três vértices combinadas pelos pesos $\lambda'$ |
| Textura | UV interpolado com $\lambda'$, nível de mipmap escolhido por triângulo, amostra da textura (ver [Mapeamento de Textura](MAPEAMENTO_TEXTURA.md) e [Mipmap](MIPMAP.md)) |
| Phong | Posição e normal de mundo interpoladas com $\lambda'$, normal renormalizada, e a equação de iluminação (ver [Modelo de Iluminação de Phong](MODELO_PHONG.md)); a difusa pode vir da textura |

A cor calculada é escrita diretamente nas subamostras vencedoras do buffer de multisample.

## 4. Grupos e limite de memória

Manter todas as candidatas de uma malha grande em memória ao mesmo tempo pode esgotá-la. As candidatas são então divididas em grupos de, no máximo, 1,5 milhão de subamostras, formados por triângulos consecutivos (um grupo tem sempre ao menos um triângulo). Os grupos são resolvidos em sequência, e o z-buffer é atualizado ao final de cada um, de modo que o grupo seguinte já testa contra o resultado do anterior. A imagem final não muda com o tamanho do grupo.

## 5. Restrição: apenas geometria opaca

Com transparência (ver [Transparência](TRANSPARENCIA.md)), o resultado depende da ordem em que as camadas são misturadas, e a geometria transparente não escreve profundidade. Ordenar as candidatas por profundidade e manter só a mais próxima descartaria as camadas intermediárias que deveriam contribuir para a mistura. Por isso o lote só trata triângulos com $\alpha = 1$; geometria translúcida sempre usa a varredura sequencial.

## 6. Ganho de desempenho

O custo da fonte de cor passa de "uma avaliação por fragmento aprovado em algum momento" para "uma avaliação por subamostra visível no final". Em uma malha opaca fechada com sobreposição visual, como um modelo 3D com lados que se ocultam mutuamente, isso evita avaliar a iluminação de fragmentos que seriam sobrescritos.

## 7. Quando o lote é usado

O lote tem custo próprio, pois ordena todas as candidatas do draw call. Ele só compensa quando há muitos triângulos e cada um cobre poucas subamostras. As duas condições são:

| Condição | Valor | Razão |
| :--- | :--- | :--- |
| Número de triângulos | pelo menos 8 | Abaixo disso o custo fixo da preparação em lote supera a economia |
| Candidatas por triângulo (média) | no máximo 200 | Triângulos grandes geram arrays enormes, e a ordenação fica mais cara que varrer um a um |

Se alguma condição falha, ou se a geometria é translúcida, nada é desenhado pelo lote e o mesmo draw call é processado pela varredura sequencial, com o mesmo resultado.
