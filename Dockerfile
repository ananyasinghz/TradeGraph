# TradeGraph API (SQLite by default; override TRADE_DATABASE_URL for Postgres)
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY alembic ./alembic
COPY alembic.ini ./
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[postgres]"

ENV TRADE_DATABASE_URL=sqlite:///./data/processed/trade.db
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
