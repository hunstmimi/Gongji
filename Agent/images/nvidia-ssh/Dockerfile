ARG BASE_IMAGE=nvidia/cuda:12.0.0-base-ubuntu22.04
FROM ${BASE_IMAGE}

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssh-server ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/sshd \
    && sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PermitUserEnvironment .*/PermitUserEnvironment yes/' /etc/ssh/sshd_config

COPY entrypoint.sh /usr/local/bin/gongji-ssh-entrypoint
RUN chmod +x /usr/local/bin/gongji-ssh-entrypoint

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/gongji-ssh-entrypoint"]
