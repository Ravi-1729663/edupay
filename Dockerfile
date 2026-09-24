FROM oven/bun:latest AS frontend

WORKDIR /app

# Install deps (cache layer).
COPY package.json bun.lock* ./
RUN bun install

COPY . .

EXPOSE 3000

CMD ["bun", "run", "dev"]
