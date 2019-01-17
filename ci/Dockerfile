FROM archlinux/base:latest
LABEL maintainer="akrug@mozilla.com"

RUN pacman -Sy
RUN pacman -S --noconfirm nodejs
RUN pacman -S --noconfirm npm
RUN pacman -S --noconfirm docker
RUN pacman -S --noconfirm make
RUN pacman -S --noconfirm pacman-contrib
RUN pacman -S --noconfirm jq
RUN pacman -S --noconfirm python-pip
RUN pip install boto3 awscli
RUN npm -g install serverless
RUN pacman --noconfirm -Rsc \
    cryptsetup \
    device-mapper \
    iproute2 && \
    rm -rf \
    /var/cache/pacman/pkg/* \
    /var/lib/pacman/sync/* \
    /etc/pacman.d/mirrorlist.pacnew \
    /README
