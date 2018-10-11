FROM amazonlinux:2
LABEL maintainer="akrug@mozilla.com"

RUN echo '### Beginning build of container.'
RUN \
  yum makecache fast && \
  yum install -y \
                  glibc-devel \
                  gcc \
                  libstdc++ \
                  libffi-devel \
                  zlib-devel \
                  make \
                  openssl \
                  openssl-dev \
                  which \
                  net-tools \
                  wget

RUN echo '### Adding bash prompt'
RUN echo -n "PS1=\"(cis-dev-preview)$\"" >> /root/.bashrc

RUN echo '### Adding python3.'
RUN yum install python3 python3-devel python3-pip python-pip -y

RUN echo '### Adding NodeJS 8.x LTS'
RUN wget https://rpm.nodesource.com/setup_8.x
RUN bash setup_8.x
RUN yum -y install nodejs

RUN echo '### Adding kinesalite and dynalite packages'
WORKDIR /opt/cis/envs/venv/
RUN npm install kinesalite
RUN npm install dynalite
RUN npm install leveldown

RUN mkdir /opt/dynamodb_data
RUN mkdir /opt/kinesis_data

RUN echo '### Setting up supervisord'
RUN pip install supervisor
RUN mkdir -p /opt/cis/conf
COPY docker/config/supervisor.conf /opt/cis/conf/
COPY docker/config/mozilla-cis.ini.dist /etc/mozila-cis.ini
RUN echo '### Setting up a home for cis.'
RUN mkdir -p /opt/cis
ADD . /opt/cis
RUN mkdir -p /opt/cis/envs

RUN echo '### Add CIS modules to the System'
RUN python3 -m venv /opt/cis/venv
RUN bash -c '\
  source /opt/cis/venv/bin/activate && \
  for D in $(find /opt/cis/python-modules -mindepth 1 -maxdepth 1 -type d) ; \
  do pip3 install $D ; done'
