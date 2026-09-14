ARG POSTGRES_IMAGE=mcr.microsoft.com/azurelinux/base/postgres:16.15-1-azl3.0.20260909
FROM ${POSTGRES_IMAGE} AS builder

ARG PGVECTOR_VERSION=0.8.6

USER root
RUN tdnf install -y gcc binutils glibc-devel kernel-headers make postgresql-devel tar gzip ca-certificates azurelinux-rpm-macros

RUN curl --fail --location --retry 4 \
      "https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v${PGVECTOR_VERSION}" \
      --output /tmp/pgvector.tar.gz \
    && mkdir -p /tmp/pgvector-src \
    && tar -xzf /tmp/pgvector.tar.gz --strip-components=1 -C /tmp/pgvector-src \
    && make -C /tmp/pgvector-src OPTFLAGS="" LDFLAGS="" \
    && make -C /tmp/pgvector-src install DESTDIR=/tmp/pgvector-install

FROM ${POSTGRES_IMAGE}
COPY --from=builder /tmp/pgvector-install/ /
