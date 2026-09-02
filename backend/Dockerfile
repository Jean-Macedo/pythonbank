# Imagem do backend.
#
# Contexto de build é `./backend`, e é por isso que `core/` mora dentro dele
# desde a Fase 2: o domínio precisa entrar na imagem sem que o contexto tenha
# de subir um nível e arrastar `frontend/`, `tests/` e o repositório inteiro.
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências antes do código: a camada só é refeita quando elas mudam, e não
# a cada edição de arquivo Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY . /app/backend/
ENV PYTHONPATH=/app

# Usuário sem privilégio: um processo que só serve HTTP não precisa ser root,
# e se for comprometido não é dono do sistema de arquivos.
RUN useradd --create-home --uid 10001 banco && chown -R banco:banco /app
USER banco

EXPOSE 8000

# O healthcheck consulta o banco, não só o processo — ver backend/main.py
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
