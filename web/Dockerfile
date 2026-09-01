FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./

# A cold install pulls ~200 MB of platform binaries (@next/swc-linux-x64-musl,
# sharp + libvips, the oxc/unrs resolver bindings) and npm prints nothing until
# it finishes, so a six-minute step looks like a frozen build. --loglevel=http
# streams one line per request so the step is visibly alive, and the npm cache
# mount keeps the tarballs across builds so a changed lockfile no longer means
# re-downloading everything.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --no-audit --no-fund --fetch-retries=5 --fetch-timeout=600000 --loglevel=http

FROM node:22-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ARG NEXT_PUBLIC_UI_REFERENCE_MODE=false
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_UI_REFERENCE_MODE=${NEXT_PUBLIC_UI_REFERENCE_MODE}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
# Docker populates HOSTNAME with the container id, and the standalone server
# reads it as its bind address, so without this it listens on one interface
# instead of all of them.
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
