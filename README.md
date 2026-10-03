# Renderizador
Renderizador base para o curso de Computação Gráfica

Pré-requisitos:

```sh
uv sync
```

Uso:
```sh
  uv run renderizador/renderizador.py
````

Opções
- "-i", "--input": arquivo X3D de entrada
- "-o", "--output": arquivo 2D de saída (imagem)
- "-w", "--width": resolução horizontal
- "-h", "--height": resolução vertical
- "-q", "--quiet": não exibe janela

## Estrutura do código

A pasta `renderizador/` tem um pacote por responsabilidade. Cada pacote expõe só a sua API pública em `__init__.py`; os módulos internos começam com sublinhado.

| Pacote | O que faz | Organização interna |
| :--- | :--- | :--- |
| `gl/` | Biblioteca gráfica: projeção, rasterização, iluminação, texturas e animação | Um módulo por domínio. A classe `GL` só expõe, por delegação, as funções que o renderizador chama |
| `x3d/` | Leitura do arquivo X3D e grafo de cena | Um módulo por componente do padrão X3D (agrupamento, aparência, geometrias, luzes, interpoladores) |

As classes de nó do `x3d/` se registram por tag, e os campos `SFNode` e `MFNode` instanciam o nó certo consultando esse registro. Para suportar um nó novo, basta declarar a classe com o decorador de registro e listá-la nos nós suportados.

## Verificação de regressão

O comando `baseline.py` renderiza 61 cenas (os exemplos 0 a 45, as animações em três instantes e cenas extras de textura nas primitivas) e compara cada imagem, pixel a pixel, com um manifesto de hashes.

```sh
  uv run baseline.py verificar
```

Qualquer mudança que altere um único pixel é reportada. Para adotar de propósito um novo resultado como referência:

```sh
  uv run baseline.py gerar
```

As imagens de referência ficam em `baseline/imagens/`, fora do git; o manifesto em `baseline/manifesto.json` é versionado.

## Exemplos

Para rodar os exemplos:

```sh
  uv run exemplos.py
````

Opções:
- número ou índice do exemplo

Visualizar exemplos na web:

[Exemplos](https://lpsoares.github.io/Renderizador/)

Lista de exemplos:

0. pontos
1. linhas
2. octogono
3. tri_2D
4. helice
...

Se quiser ver os arquivos localmente, rode: python3 -m http.server
