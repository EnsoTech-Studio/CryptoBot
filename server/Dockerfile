FROM golang:1.23-alpine AS builder

WORKDIR /src
COPY go.mod ./
COPY go.sum ./
COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/worker ./cmd/worker

FROM alpine:3.20

RUN apk add --no-cache ca-certificates wget \
    && addgroup -S app \
    && adduser -S -G app app

COPY --from=builder /out/api /api
COPY --from=builder /out/worker /worker

USER app
EXPOSE 8080
ENTRYPOINT ["/api"]
