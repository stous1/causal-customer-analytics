"""Los artefactos congelados no cambian después de su tag."""

import subprocess

import pytest

from causal.rutas import RAIZ

CONGELADOS = {
    "hito2-congelado": ["docs/resultados/hito2/parametros.json"],
    "preregistro": ["docs/resultados/preregistro.json"],
}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True)


@pytest.mark.parametrize("tag", sorted(CONGELADOS))
def test_congelado_igual_al_tag(tag: str) -> None:
    if _git("rev-parse", "--verify", f"refs/tags/{tag}").returncode != 0:
        pytest.skip(f"sin el tag {tag} (clon sin tags)")
    for ruta in CONGELADOS[tag]:
        en_tag = _git("show", f"{tag}:{ruta}")
        assert en_tag.returncode == 0, f"{ruta} no existe en {tag}"
        actual = (RAIZ / ruta).read_bytes().replace(b"\r\n", b"\n")
        assert actual == en_tag.stdout.replace(b"\r\n", b"\n"), f"{ruta} cambió desde {tag}"
