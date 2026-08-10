FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY packages/contracts/python /contracts/python
COPY apps/api/pyproject.toml apps/api/requirements.lock /app/
COPY apps/api/app /app/app

RUN pip install --no-cache-dir -U "pip>=24" "setuptools>=68" "wheel" \
 && pip install --no-cache-dir -e /contracts/python \
 && pip install --no-cache-dir -r /app/requirements.lock \
 && pip install --no-cache-dir --no-deps -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
