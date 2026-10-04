# Luzes: DirectionalLight e Headlight

## 1. Papel das luzes no frame

O modelo de iluminação (ver [Modelo de Iluminação de Phong](MODELO_PHONG.md)) precisa, para cada ponto da superfície, de uma lista de luzes com direção, cor, intensidade e contribuição ambiente. Essa lista é construída a cada frame, enquanto a cena é percorrida, e descartada no início do frame seguinte. Cada luz entra na lista já em coordenadas de mundo, o mesmo espaço em que a posição, a normal e a câmera são comparadas na hora de iluminar.

Uma cena sem nenhuma luz na lista é desenhada sem iluminação: cada superfície recebe apenas a cor emissiva do material.

## 2. Ordem de visita

A lista só pode ser usada por geometria desenhada depois que a luz foi visitada. A travessia do grafo de cena impõe a ordem:

1. O Viewpoint, para que as matrizes da câmera já existam.
2. O NavigationInfo, que pode acrescentar a luz da câmera (seção 4) e depende da orientação da câmera.
3. As luzes declaradas na cena.
4. O restante da geometria, na ordem do arquivo.

## 3. Luz direcional

Uma luz direcional simula uma fonte muito distante (como o sol): todos os raios são paralelos e a direção é a mesma em qualquer ponto da cena. Seus campos são a direção $\mathbf{d}$ em que a luz se propaga, a cor, a intensidade e a contribuição ambiente.

A direção é declarada no sistema de coordenadas local do ponto da árvore onde a luz aparece. Para que uma luz dentro de um Transform gire junto com ele, $\mathbf{d}$ é levada ao mundo pela transformação corrente. Como $\mathbf{d}$ é um vetor de direção e não uma posição, o tratamento é o mesmo das normais (seção 5): a transformação usada é a inversa transposta da parte linear da matriz de modelo $M$, e o resultado é renormalizado.

O vetor usado na equação de Phong aponta do ponto para a luz, isto é, o oposto da direção de propagação:

$$
L = -\hat{\mathbf{d}}
$$

## 4. Luz da câmera (headlight)

Quando o NavigationInfo mantém `headlight` ligado, a cena recebe uma luz direcional branca, de intensidade 1 e sem componente ambiente, presa à câmera. Ela aponta sempre para onde a câmera olha. Em coordenadas de câmera o olhar é $(0, 0, -1)$, então no mundo a direção é essa mesma direção levada pela rotação inversa da matriz de view $R_v$:

$$
\mathbf{d}_{\text{headlight}} = R_v^{\top} \begin{pmatrix} 0 \\ 0 \\ -1 \end{pmatrix}
$$

Como a rotação é ortogonal, sua inversa é a transposta. Por depender da orientação corrente da câmera, a luz da câmera precisa ser criada depois do Viewpoint.

## 5. Normais em coordenadas de mundo

A normal de uma superfície transformada por uma matriz $M$ não é transformada por $M$. Considere um plano de normal $\mathbf{n}$ e um vetor $\mathbf{t}$ tangente a ele, de modo que $\mathbf{n} \cdot \mathbf{t} = 0$. Após a transformação a tangente vira $M\mathbf{t}$, e a nova normal $\mathbf{n}'$ precisa continuar perpendicular a ela:

$$
\mathbf{n}'^{\top} (M \mathbf{t}) = 0 \quad \Longrightarrow \quad \mathbf{n}' = (M^{-1})^{\top} \mathbf{n}
$$

Com uma escala não uniforme, aplicar $M$ diretamente à normal a deixaria inclinada em relação à superfície. A inversa transposta preserva a perpendicularidade, e a renormalização final restaura o comprimento unitário, que o produto escalar $N \cdot L$ da equação de Phong exige.

As posições, ao contrário, usam $M$ diretamente.
