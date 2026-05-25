FROM docker.m.daocloud.io/library/alpine:3.20

RUN printf '%s\n' \
    'https://mirrors.aliyun.com/alpine/v3.20/main' \
    'https://mirrors.aliyun.com/alpine/v3.20/community' \
    > /etc/apk/repositories
RUN apk add --no-cache postgresql16 postgresql16-client su-exec

COPY docker/postgres-alpine/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5432

ENTRYPOINT ["docker-entrypoint.sh"]
