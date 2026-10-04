# Tesselação das Primitivas 3D

## 1. Da primitiva paramétrica à malha

Box, Sphere, Cone e Cylinder são descritos por poucos parâmetros (tamanho, raio, altura), mas o rasterizador só desenha triângulos. A tesselação converte cada primitiva em uma malha indexada com quatro arrays:

| Array | Conteúdo |
| :--- | :--- |
| Posições | Vértices em coordenadas de objeto, com o sólido centrado na origem |
| Normais | Uma normal unitária por vértice, para a iluminação |
| Triângulos | Triplas de índices de vértice em ordem anti-horária vista de fora |
| UV | Uma coordenada de textura por vértice |

A partir daí a malha segue o mesmo caminho de qualquer outra geometria triangular: projeção, descarte de faces de costas, rasterização e iluminação. As superfícies curvas usam 48 fatias ao redor do eixo vertical, e a esfera usa 24 faixas de latitude. Como a malha só depende dos parâmetros da primitiva, ela é construída uma vez por combinação de parâmetros e reaproveitada nos frames seguintes.

## 2. Normais: planas ou suaves

A escolha da normal define o aspecto da superfície sob a iluminação:

| Normal | Como é obtida | Aspecto |
| :--- | :--- | :--- |
| Plana | Mesma normal para todos os vértices de uma face | Face uniforme, arestas vivas |
| Suave | Normal da superfície curva ideal em cada vértice, interpolada pelo triângulo | Superfície curva contínua, sem facetas visíveis |

Quando a normal muda de uma face para a vizinha (uma aresta viva), os vértices da aresta precisam ser duplicados, um conjunto por face, cada um com a sua normal. Compartilhar o vértice forçaria uma única normal para as duas faces e suavizaria uma aresta que deveria ser viva.

## 3. Box

Seis faces, quatro vértices por face, em um total de 24 vértices e 12 triângulos. Cada face tem normal plana, apontando para fora ao longo de $\pm X$, $\pm Y$ ou $\pm Z$, e é um retângulo dividido em dois triângulos pela diagonal:

$$
(c_0, c_1, c_2) \quad (c_0, c_2, c_3)
$$

onde $c_0 \dots c_3$ são os cantos em ordem anti-horária vista de fora. Os 24 vértices (e não 8) existem justamente porque cada canto do cubo pertence a três faces com normais diferentes (seção 2).

Cada face recebe a textura inteira: os cantos têm UV $(0,0)$, $(1,0)$, $(1,1)$ e $(0,1)$, com $u$ crescendo para a direita e $v$ para cima vistos de fora.

## 4. Sphere

A esfera de raio $r$ é uma grade de latitude $\theta \in [0, \pi]$ (do polo norte ao sul) por longitude $\varphi \in [0, 2\pi]$, com $(24 + 1) \times (48 + 1)$ vértices. A normal em cada vértice é o próprio vetor radial, e a posição é essa normal escalada por $r$:

$$
\mathbf{n} = \begin{pmatrix} \sin\theta \cos\varphi \\ \cos\theta \\ \sin\theta \sin\varphi \end{pmatrix}, \qquad \mathbf{p} = r\,\mathbf{n}
$$

Cada célula da grade, entre duas faixas e duas fatias vizinhas, vira dois triângulos, em um total de $2 \times 24 \times 48 = 2304$ triângulos. Nos polos, onde $\sin\theta = 0$, todos os vértices de uma linha da grade coincidem; nas duas faixas polares, um dos dois triângulos de cada célula tem então dois vértices iguais e área zero, e é eliminado pelo descarte de faces de costas (a área assinada nula não passa no teste).

A coordenada de textura mapeia a esfera como um globo:

$$
u = 0{,}75 - \frac{\varphi}{2\pi}, \qquad v = 1 - \frac{\theta}{\pi}
$$

de modo que $v = 1$ está no polo norte e $u$ percorre a volta no sentido anti-horário visto de cima, começando pelo fundo (direção $-Z$). A última coluna de vértices repete a primeira em posição, mas com $u$ diferente, para que a textura não salte na costura.

## 5. Cilindro e cone

Ambos têm a superfície lateral definida por dois anéis de 49 vértices cada, um no topo (altura $+h/2$) e outro na base ($-h/2$), com o sólido centrado em $Y = 0$. O último vértice de cada anel repete o primeiro, para fechar a costura sem reindexar. Cada fatia lateral é um quadrilátero de dois triângulos:

| Sólido | Raio do topo | Raio da base | Normal lateral (antes de normalizar) | Tampas |
| :--- | :--- | :--- | :--- | :--- |
| Cilindro | $r$ | $r$ | $(\cos\varphi,\ 0,\ \sin\varphi)$ | Topo e base |
| Cone | $0$ | $r$ | $(h\cos\varphi,\ r,\ h\sin\varphi)$ | Só a base |

No cone, o raio do topo é zero e o anel de cima colapsa no ápice; o segundo triângulo de cada quadrilátero degenera, e a lateral fica com um triângulo por fatia (48). A normal do cone tem a componente vertical $r$ e a horizontal $h$ porque a superfície é inclinada: no plano (raio, altura), a geratriz do cone vai de $(r, -h/2)$ a $(0, h/2)$, com direção $(-r, h)$, e uma normal a essa direção é $(h, r)$ em (horizontal, vertical).

A normal lateral é calculada por fatia, de modo que a lateral é suave em torno do eixo. As tampas ficam em malhas separadas, com vértices próprios e normal plana ao longo de $\pm Y$, porque a aresta entre a lateral e a tampa deve continuar viva (seção 2).

### 5.1 Tampa circular

Uma tampa é um disco de raio $r$ no plano de altura $y$: um vértice central mais o anel de 49 vértices. Os 48 triângulos formam um leque a partir do centro. A ordem dos vértices em cada triângulo depende do sentido da normal:

| Tampa | Normal | Sentido do anel |
| :--- | :--- | :--- |
| Topo | $+Y$ | Invertido, porque $\varphi$ crescente é horário visto de cima |
| Base | $-Y$ | Direto, porque visto de baixo o sentido se inverte |

Assim, em ambos os casos, o triângulo é anti-horário visto de fora. A textura da tampa é um recorte circular da imagem, centrado em $(0{,}5;\ 0{,}5)$ e de raio $0{,}5$, com a imagem em pé vista de fora.

### 5.2 UV da lateral

A textura da lateral dá a volta no mesmo sentido da esfera, com $u = 0{,}75 - j/48$ para a fatia $j$ e $v$ indo de 0 na base a 1 no topo. O valor de $u$ é "desenrolado" (decresce de forma contínua em vez de voltar a 1 depois de 0), o que evita um salto de interpolação na costura.

## 6. União de malhas

Um sólido formado por várias partes (lateral e tampas) é a concatenação das malhas das partes. Os índices dos triângulos de cada parte são deslocados pela quantidade de vértices das partes anteriores, para continuarem apontando para os vértices certos na lista final.
