FROM ubuntu:20.04

RUN set -eux;
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN	apt-get update;
RUN	apt-get install -y \
    git \
    wget \
    libssl-dev \
    build-essential \
    libffi-dev \
    libreadline-dev \
    zlib1g-dev \
    libsqlite3-dev \
    libssl-dev

# ============================================
WORKDIR /tmp/
ARG PYTHON_VERSION="3.10.5"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC &&\
    tar -xvzf "Python-${PYTHON_VERSION}.tgz"
WORKDIR "Python-${PYTHON_VERSION}"
RUN ./configure     &&\
    make -j 4       &&\
    make install
WORKDIR /tmp/
RUN rm "Python-${PYTHON_VERSION}.tgz" &&\
    rm -rf "Python-${PYTHON_VERSION}"

# ============================================
WORKDIR /tmp/
ARG PYTHON_VERSION="3.9.13"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC &&\
    tar -xvzf "Python-${PYTHON_VERSION}.tgz"
WORKDIR "Python-${PYTHON_VERSION}"
RUN ./configure     &&\
    make -j 4       &&\
    make install
WORKDIR /tmp/
RUN rm "Python-${PYTHON_VERSION}.tgz" &&\
    rm -rf "Python-${PYTHON_VERSION}"

# ============================================
WORKDIR /tmp/
ARG PYTHON_VERSION="3.8.13"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC &&\
    tar -xvzf "Python-${PYTHON_VERSION}.tgz"
WORKDIR "Python-${PYTHON_VERSION}"
RUN ./configure     &&\
    make -j 4       &&\
    make install
WORKDIR /tmp/
RUN rm "Python-${PYTHON_VERSION}.tgz" &&\
    rm -rf "Python-${PYTHON_VERSION}"

# ============================================
WORKDIR /tmp/