# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

# 1. Copy local package files (from the same directory as Dockerfile)
COPY package*.json ./
RUN npm ci

# 2. Copy everything else in the current directory
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

# 3. Copy the nginx.conf from the current directory
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 4. Copy build artifacts from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]