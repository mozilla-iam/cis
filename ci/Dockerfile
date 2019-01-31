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
RUN pacman -S --noconfirm zip
RUN pip install boto3 awscli
RUN pip install flake8
RUN npm -g install serverless
WORKDIR /var/task
