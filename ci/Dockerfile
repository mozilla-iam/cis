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
RUN pacman -S --noconfirm postgresql 
RUN pacman -S --noconfirm postgresql-libs
RUN pacman -S --noconfirm gcc
RUN pacman -S --noconfirm python2
RUN pip install boto3 awscli
RUN pip install flake8
RUN pip install tox
RUN npm install serverless
RUN npm install kinesalite
RUN npm install dynalite
RUN mkdir /root/utils
COPY fake-creds.sh /root/utils/
RUN chmod 700 /root/utils/fake-creds.sh
WORKDIR /var/task
RUN echo "export PATH=$PATH:/node_modules/.bin" > ~/.bashrc
