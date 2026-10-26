#!/usr/bin/env python3
"""El formato entra en la verificación cuando el proyecto ya lo eligió.

Sin eso, verify.sh podía dar ok con el código desordenado: el hook de guardado
solo formatea archivos nuevos, y la autodetección miraba lint, no formato.
Instalar un formateador que el repo no pidió tampoco: un paso vacío dejaría
todo verify en parcial hasta que alguien diga que sí.

    python3 .workflow/tests/test-verify-format.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
VERIFY = RAIZ / ".workflow" / "verify.sh"
CHECK_TOOLS = RAIZ / ".workflow" / "check-tools.sh"
ARCHITECT = RAIZ / ".claude" / "commands" / "architect.md"


def sh(repo, cmd):
    return subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, check=False)


def montar(repo):
    p = Path(repo)
    (p / ".workflow").mkdir(parents=True)
    (p / ".workflow" / "verify.sh").write_bytes(VERIFY.read_bytes())
    sh(repo, "git init -q . && git config user.email t@t.t && git config user.name t")
    sh(repo, "git add -A && git commit -q -m 'chore: base' --allow-empty")


def verify(repo):
    return subprocess.run(
        ["bash", ".workflow/verify.sh"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def stub(path, cuerpo):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cuerpo, encoding="utf-8")
    path.chmod(0o755)


def caso_sin_formateador_no_inventa_paso():
    """Un package.json pelado no gana un format-js vacío."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
        r = verify(d)
        assert "format-js" not in r.stdout, r.stdout


def caso_prettier_declarado_sin_binario_queda_sin_verificar():
    """Dijo Prettier y no está instalado: eso es parcial, no un ok silencioso."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "package.json").write_text('{"devDependencies":{"prettier":"3.9.10"}}\n', encoding="utf-8")
        r = verify(d)
        assert "format-js — sin herramienta" in r.stdout, r.stdout


def caso_prettier_instalado_se_chequea():
    """Con el binario, el paso corre prettier --check y no biome."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "package.json").write_text('{"devDependencies":{"prettier":"3.9.10"}}\n', encoding="utf-8")
        marca = Path(d, "prettier-corrio")
        stub(
            Path(d, "node_modules/.bin/prettier"),
            "#!/bin/sh\nprintf '%s\\n' \"$*\" > prettier-corrio\nexit 0\n",
        )
        r = verify(d)
        assert "format-js OK" in r.stdout, r.stdout
        assert "--check ." in marca.read_text(encoding="utf-8"), marca.read_text(encoding="utf-8")


def caso_biome_no_suma_prettier():
    """Biome ya cubre el formato. Prettier al lado no se ejecuta."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "package.json").write_text(
            '{"devDependencies":{"@biomejs/biome":"1.0.0","prettier":"3.9.10"}}\n',
            encoding="utf-8",
        )
        stub(Path(d, "node_modules/.bin/biome"), "#!/bin/sh\nexit 0\n")
        stub(
            Path(d, "node_modules/.bin/prettier"),
            "#!/bin/sh\necho no > prettier-corrio\nexit 0\n",
        )
        r = verify(d)
        assert "lint-js OK" in r.stdout, r.stdout
        assert "format-js" not in r.stdout, r.stdout
        assert not Path(d, "prettier-corrio").exists()


def caso_ruff_sin_format_no_agrega_paso():
    """Ruff como linter no arrastra ruff format. Eso se propone, no se impone."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "pyproject.toml").write_text("[project]\nname='t'\nversion='0'\n", encoding="utf-8")
        r = verify(d)
        assert "format-py" not in r.stdout, r.stdout


def caso_ruff_format_declarado_se_chequea():
    """[tool.ruff.format] es el sí: el paso entra solo."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        Path(d, "pyproject.toml").write_text(
            "[project]\nname='t'\nversion='0'\n\n[tool.ruff.format]\n",
            encoding="utf-8",
        )
        bindir = Path(d, "bin")
        stub(bindir / "ruff", "#!/bin/sh\nprintf '%s\\n' \"$*\" >> ruff-llamadas.txt\nexit 0\n")
        env = os.environ.copy()
        env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
        r = subprocess.run(
            ["bash", ".workflow/verify.sh"],
            cwd=d,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert "format-py OK" in r.stdout, r.stdout + r.stderr
        llamadas = Path(d, "ruff-llamadas.txt").read_text(encoding="utf-8")
        assert "format --check ." in llamadas, llamadas


def caso_check_tools_avisa_si_falta_y_calla_si_esta():
    """En un proyecto ya iniciado, el hueco se ve sin instalar nada."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
        r = subprocess.run(["bash", str(CHECK_TOOLS)], cwd=d, capture_output=True, text=True, check=False)
        assert "formato JS" in r.stdout, r.stdout
        assert "no se instala solo" in r.stdout, r.stdout

    with tempfile.TemporaryDirectory() as d:
        Path(d, "package.json").write_text('{"devDependencies":{"prettier":"3.9.10"}}\n', encoding="utf-8")
        r = subprocess.run(["bash", str(CHECK_TOOLS)], cwd=d, capture_output=True, text=True, check=False)
        assert "prettier ya está en el proyecto" in r.stdout, r.stdout
        assert "no se instala solo" not in r.stdout, r.stdout


def caso_architect_propone_y_no_reformatea_solo():
    """La instrucción tiene que sobrevivir: detectar, proponer, esperar el sí."""
    texto = ARCHITECT.read_text(encoding="utf-8")
    assert "Mirá el repo antes de proponer instalar nada." in texto
    assert "no se instala otro" in texto
    assert "pará hasta el sí" in texto
    assert "ruff format" in texto
    assert "solo con un sí aparte" in texto


CASOS = [
    caso_sin_formateador_no_inventa_paso,
    caso_prettier_declarado_sin_binario_queda_sin_verificar,
    caso_prettier_instalado_se_chequea,
    caso_biome_no_suma_prettier,
    caso_ruff_sin_format_no_agrega_paso,
    caso_ruff_format_declarado_se_chequea,
    caso_check_tools_avisa_si_falta_y_calla_si_esta,
    caso_architect_propone_y_no_reformatea_solo,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {str(exc)[:500]}")
        except Exception as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {type(exc).__name__}: {exc}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
