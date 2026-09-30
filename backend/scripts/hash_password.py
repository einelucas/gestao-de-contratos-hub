"""Gera o hash Argon2 de uma senha do login de homologação.

Uso (a partir de backend/):
    python scripts/hash_password.py

A senha é digitada sem eco (duas vezes) e nunca é gravada; o script imprime só
o hash, para colar em HOMOLOGATION_VIEWER_PASSWORD_HASH ou
HOMOLOGATION_ADMIN_PASSWORD_HASH no ambiente do backend.
"""

from __future__ import annotations

import getpass
import sys

from argon2 import PasswordHasher

MIN_LENGTH = 12


def main() -> int:
    password = getpass.getpass("Senha: ")
    if len(password) < MIN_LENGTH:
        print(f"ERRO: use pelo menos {MIN_LENGTH} caracteres.", file=sys.stderr)
        return 2
    if getpass.getpass("Repita a senha: ") != password:
        print("ERRO: as senhas não conferem.", file=sys.stderr)
        return 2
    print(PasswordHasher().hash(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
