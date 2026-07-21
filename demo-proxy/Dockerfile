FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund
COPY limits.ts server.ts tsconfig.json ./

EXPOSE 8080
CMD ["npx", "tsx", "server.ts"]
