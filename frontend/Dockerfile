# syntax=docker/dockerfile:1

FROM node:24-alpine AS base

WORKDIR /app
RUN chown node:node /app
USER node

FROM base AS dependencies

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

FROM dependencies

COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
