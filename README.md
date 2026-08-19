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
