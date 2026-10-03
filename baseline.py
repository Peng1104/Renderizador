#!/usr/bin/env python3
"""
Baseline de regressão do renderizador.

Renderiza um conjunto fixo de cenas (exemplos 0 a 45) e compara cada resultado, pixel a pixel,
com o que foi gravado por `gerar`. Serve para provar que uma refatoração não
mudou nenhum pixel.

Uso
---
uv run baseline.py gerar       grava as imagens e o manifesto de hashes
uv run baseline.py verificar   renderiza de novo e compara com o manifesto

O manifesto (`baseline/manifesto.json`) vai para o git; as imagens ficam em
`baseline/imagens/` e `baseline/atual/`, fora dele.
"""

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

RAIZ = Path(__file__).resolve().parent
BASE = RAIZ / "baseline"
IMAGENS = BASE / "imagens"
ATUAL = BASE / "atual"
MANIFESTO = BASE / "manifesto.json"
TEMPOS = BASE / "tempos.json"

# Ids da lista achatada de docs/exemplos.json (posição na lista, a partir de 0).
EXEMPLOS = range(0, 46)
ANIMADOS = range(36, 41)
INSTANTES = (0.0, 2.5, 5.0)  # segundos, para os exemplos animados


@dataclass(frozen=True)
class Caso:
    """
    Uma renderização do baseline.

    Attributes
    ----------
    nome : str
        Identificador estável do caso, usado como chave no manifesto.
    x3d : Path
        Arquivo da cena.
    largura : int
        Largura da imagem, em pixels.
    altura : int
        Altura da imagem, em pixels.
    instante : float or None
        Instante fixo da animação, ou None para não mexer no relógio.
    """

    nome: str
    x3d: Path
    largura: int
    altura: int
    instante: float | None = None


def _casos() -> list[Caso]:
    """
    Monta a lista de casos: exemplos 9 a 45, animações em instantes fixos e cenas extras.

    Returns
    -------
    list[Caso]
        Casos na ordem em que são renderizados.
    """
    dados = json.loads((RAIZ / "docs" / "exemplos.json").read_text())
    lista = [e for grupo in dados["examples"] for e in grupo["examples"]]

    casos: list[Caso] = []
    for i in EXEMPLOS:
        e = lista[i]
        arquivo = RAIZ / "docs" / "exemplos" / (e["path"] + e["x3d"]) / (e["x3d"] + ".x3d")
        if i in ANIMADOS:
            for t in INSTANTES:
                casos.append(Caso(f"{i:02d}_{e['x3d']}_t{t:g}", arquivo,
                                  e["width"], e["height"], t))
        else:
            casos.append(Caso(f"{i:02d}_{e['x3d']}", arquivo, e["width"], e["height"]))

    for cena in sorted((BASE / "cenas").glob("*.x3d")):
        casos.append(Caso(f"cena_{cena.stem}", cena, 450, 200))
    return casos


def _renderizar(caso: Caso, destino: Path) -> tuple[Path, float]:
    """
    Renderiza um caso num processo novo, para que nenhum estado vaze entre casos.

    Parameters
    ----------
    caso : Caso
        Caso a renderizar.
    destino : Path
        Pasta onde a imagem é gravada.

    Returns
    -------
    Path
        Imagem gerada.
    float
        Tempo da renderização, em segundos.
    """
    prefixo = destino / caso.nome.replace(".", "p")
    comando = [sys.executable, str(Path(__file__).resolve()), "_filho", str(caso.x3d),
               str(caso.largura), str(caso.altura), str(prefixo),
               "-" if caso.instante is None else str(caso.instante)]
    inicio = time.perf_counter()
    resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, check=False)
    duracao = time.perf_counter() - inicio
    gerados = sorted(destino.glob(prefixo.name + "*.png"))
    if resultado.returncode != 0 or not gerados:
        raise RuntimeError(f"{caso.nome}: falha ao renderizar\n{resultado.stderr[-600:]}")
    return gerados[0], duracao


def _filho(argumentos: list[str]) -> None:
    """
    Renderiza uma cena nesta execução (chamado por `_renderizar`, em processo próprio).

    Parameters
    ----------
    argumentos : list[str]
        x3d, largura, altura, prefixo de saída e instante (ou "-" para o relógio real).
    """
    x3d, largura, altura, prefixo, instante = argumentos
    sys.path.insert(0, str(RAIZ / "renderizador"))
    if instante != "-":
        gl = importlib.import_module("gl")
        gl.definir_relogio(lambda: float(instante), origem=0.0)

    sys.argv = ["renderizador", "-i", x3d, "-q", "-s", "2", "-w", largura, "-h", altura,
                "-o", prefixo + ".png"]
    renderizador = importlib.import_module("renderizador")
    renderizador.Renderizador().main()


def _hash(imagem: Path) -> tuple[str, tuple[int, ...]]:
    """
    Calcula o hash dos pixels de uma imagem.

    Parameters
    ----------
    imagem : Path
        Arquivo PNG.

    Returns
    -------
    str
        SHA-256 dos bytes dos pixels RGB.
    tuple[int, ...]
        Forma da matriz de pixels (altura, largura, canais).
    """
    pixels = np.asarray(Image.open(imagem).convert("RGB"))
    return hashlib.sha256(np.ascontiguousarray(pixels).tobytes()).hexdigest(), pixels.shape


def _pixels(imagem: Path) -> npt.NDArray[np.uint8]:
    """
    Lê os pixels RGB de uma imagem.

    Parameters
    ----------
    imagem : Path
        Arquivo PNG.

    Returns
    -------
    NDArray[uint8]
        Pixels (altura, largura, 3).
    """
    return np.asarray(Image.open(imagem).convert("RGB"))


def gerar() -> int:
    """
    Renderiza todos os casos e grava as imagens, o manifesto e os tempos.

    Returns
    -------
    int
        Código de saída (0 se tudo foi gravado).
    """
    shutil.rmtree(IMAGENS, ignore_errors=True)
    IMAGENS.mkdir(parents=True)
    manifesto: dict[str, dict[str, object]] = {}
    tempos: dict[str, float] = {}
    for caso in _casos():
        imagem, duracao = _renderizar(caso, IMAGENS)
        digest, forma = _hash(imagem)
        manifesto[caso.nome] = {"sha256": digest, "forma": list(forma), "arquivo": imagem.name}
        tempos[caso.nome] = round(duracao, 3)
        print(f"{caso.nome:40s} {duracao:6.2f}s  {digest[:12]}")
    MANIFESTO.write_text(json.dumps(manifesto, indent=2, sort_keys=True) + "\n")
    TEMPOS.write_text(json.dumps(tempos, indent=2, sort_keys=True) + "\n")
    print(f"\n{len(manifesto)} casos gravados em {MANIFESTO.relative_to(RAIZ)}")
    return 0


def verificar() -> int:
    """
    Renderiza todos os casos de novo e compara com o manifesto.

    Returns
    -------
    int
        0 se todos os casos saíram idênticos, 1 se algum diferiu ou falhou.
    """
    esperado: dict[str, dict[str, object]] = json.loads(MANIFESTO.read_text())
    antes: dict[str, float] = json.loads(TEMPOS.read_text()) if TEMPOS.exists() else {}
    shutil.rmtree(ATUAL, ignore_errors=True)
    ATUAL.mkdir(parents=True)

    diferentes: list[str] = []
    total_antes = total_depois = 0.0
    casos = _casos()
    for caso in casos:
        if caso.nome not in esperado:
            diferentes.append(f"{caso.nome}: não está no manifesto")
            continue
        try:
            imagem, duracao = _renderizar(caso, ATUAL)
        except RuntimeError as erro:
            diferentes.append(str(erro))
            continue
        total_depois += duracao
        total_antes += antes.get(caso.nome, 0.0)
        digest, _ = _hash(imagem)
        if digest != esperado[caso.nome]["sha256"]:
            original = IMAGENS / str(esperado[caso.nome]["arquivo"])
            n = (int((_pixels(original) != _pixels(imagem)).any(axis=-1).sum())
                 if original.exists() else -1)
            diferentes.append(f"{caso.nome}: {n} pixels diferentes")
    faltando = sorted(set(esperado) - {c.nome for c in casos})
    diferentes += [f"{nome}: está no manifesto mas não é mais renderizado" for nome in faltando]

    print(f"{len(casos)} casos, {len(diferentes)} problemas "
          f"(tempo total {total_depois:.1f}s; baseline {total_antes:.1f}s)")
    for linha in diferentes:
        print("  DIFERE:", linha)
    return 1 if diferentes else 0


def main() -> int:
    """
    Despacha o comando da linha de comando.

    Returns
    -------
    int
        Código de saída do comando.
    """
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "gerar":
        return gerar()
    if comando == "verificar":
        return verificar()
    if comando == "_filho":
        _filho(sys.argv[2:])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
