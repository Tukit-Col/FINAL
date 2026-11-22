# Contribuir

Tukit es un proyecto privado del Equipo Tukit publicado solo para consulta (ver [LICENSE](LICENSE)).
**No aceptamos pull requests de fuera del equipo.** Si encontraste un error, abre un issue; si es
de seguridad, sigue [SECURITY.md](SECURITY.md).

## Para el equipo

1. Rama desde `main` con prefijo: `feat/`, `fix/`, `chore/`, `docs/` o `test/`.
2. Antes del PR, lo mismo que corre CI:
   ```bash
   make verificar            # o, en Windows: ruff check . ; ruff format --check . ; pytest
   npm run typecheck ; npm run lint ; npm test
   ```
3. PR contra `main`. Se mergea solo con los 13 trabajos de CI en verde; `main` no acepta push
   directo ni push forzado.
4. Commits en español, en imperativo y con el porqué en el cuerpo.
5. Nunca subas `.env`, llaves ni datos personales reales: el push los bloquea, pero revísalo antes.
