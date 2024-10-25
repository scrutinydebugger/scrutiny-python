FROM ubuntu:20.04 as build-tests

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git \
    wget \
    libssl-dev \
    build-essential \
    libffi-dev \
    libreadline-dev \
    zlib1g-dev \
    libsqlite3-dev \
    libssl-dev \
    gcc-avr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/

# ============================================
ARG PYTHON_VERSION="3.12.0"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"

# ============================================
ARG PYTHON_VERSION="3.11.10"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"


# ============================================
ARG PYTHON_VERSION="3.10.15"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"

# ============================================
ARG PYTHON_VERSION="3.9.20"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"
