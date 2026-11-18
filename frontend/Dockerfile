# syntax=docker/dockerfile:1
# Contract Guard frontend — Vite build served by nginx on Alpine.
#
# Layer order = cache order: `npm ci` only reruns when package.json /
# package-lock.json change; source edits reuse the node_modules layer.

########################
# deps — node_modules
########################
FROM node:24-alpine AS deps
WORKDIR /app

# manifests only — the cache boundary for the npm layer
COPY package.json package-lock.json ./
RUN npm ci

########################
# build — static bundle
########################
FROM deps AS build
WORKDIR /app

COPY . .
RUN npm run build

########################
# runtime — nginx serves the SPA and proxies /api to Django
########################
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx's own healthcheck ships in the base image; nothing to add
