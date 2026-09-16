# Técnicas do Renderizador

Documentação das técnicas de computação gráfica implementadas no renderizador, com as equações por trás de cada uma e o funcionamento do algoritmo. Cada documento é autocontido; onde um documento depende de um conceito definido em outro, o texto define esse conceito inline e aponta para o documento relacionado como leitura complementar.

## Pipeline geométrico

- [Transformações Geométricas](TRANSFORMACOES.md): coordenadas homogêneas, translação, escala, rotação via quatérnio, pilha de transformações do grafo de cena.
- [Projeção Perspectiva](PROJECAO_PERSPECTIVA.md): matriz de view, matriz de projeção perspectiva, divisão de perspectiva, viewport.

## Rasterização

- [Rasterização de Triângulos por Função de Aresta](RASTERIZACAO_TRIANGULOS.md): teste de dentro/fora por função de aresta, coordenadas baricêntricas.
- [Back-Face Culling](BACKFACE_CULLING.md): descarte de triângulos de costas para a câmera via área assinada.
- [Interpolação Perspectiva-Correta](INTERPOLACAO_PERSPECTIVA.md): correção pelo componente w para cor e textura interpoladas por vértice.
- [Desenho de Círculo por Simetria de Octantes](CIRCULO_OCTANTES.md): geração do contorno de um círculo por reflexão de um único octante.

## Anti-aliasing

- [Anti-Aliasing por Multisampling (MSAA)](ANTIALIASING_MSAA.md): grade de subamostras por pixel e resolve por média.
- [Anti-Aliasing por Supersampling (SSAA)](ANTIALIASING_SUPERSAMPLING.md): desenho em resolução ampliada e redução por filtro de caixa.
- [Anti-Aliasing de Linhas (Algoritmo de Xiaolin Wu)](ANTIALIASING_LINHAS.md): cobertura analítica distribuída entre dois pixels vizinhos.

## Textura e profundidade

- [Mapeamento de Textura](MAPEAMENTO_TEXTURA.md): coordenadas UV, wrap, amostragem nearest-neighbor.
- [Mipmap](MIPMAP.md): cadeia de níveis por filtro de caixa e seleção de nível por triângulo.
- [Z-Buffer](ZBUFFER.md): teste de profundidade por subamostra para oclusão entre geometria que se cruza.
- [Transparência (Alpha Blending)](TRANSPARENCIA.md): mistura de cor por opacidade e sua interação com o z-buffer.
