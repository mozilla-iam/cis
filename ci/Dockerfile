FROM archlinux:latest
LABEL maintainer="akrug@mozilla.com"

# skip global package update - whatever archlinux/latest has is enough
#RUN pacman -Syyu --noconfirm
# install arch base-devel, dependencies, and refresh the package list from upstream
RUN pacman --noconfirm -S -y --needed base-devel iputils net-tools grep nodejs npm docker make pacman-contrib jq python-pip zip gcc python2 wget unzip tar gawk jdk-openjdk postgresql-libs python-psycopg2
## Use this if you need to force-downgrade system's python
## You'll want to compile the version you want first and upload it to S3
# RUN wget https://s3-us-west-2.amazonaws.com/public.iam.mozilla.com/python37-3.7.5-2-x86_64.pkg.tar.xz
#RUN pacman -U --noconfirm python37-3.7.5-2-x86_64.pkg.tar.xz
#RUN ln -fs /usr/bin/python3.7 /usr/bin/python && \
#  rm -rf /usr/lib/python3.7/site-packages && \
#  ln -fs /usr/lib/python3.8/site-packages/ /usr/lib/python3.7/site-packages
RUN pip install boto3 awscli flake8 black tox docker-compose
RUN npm --unsafe-perm -g install serverless kinesalite
RUN mkdir -p /opt/dynamodb_local
WORKDIR /opt/dynamodb_local
RUN wget --no-verbose https://s3-us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz
RUN tar xzf dynamodb_local_latest.tar.gz
WORKDIR /
RUN mkdir /root/utils
COPY fake-creds.sh /root/utils/
RUN chmod 700 /root/utils/fake-creds.sh
# We get this artifact from S3 now.
# RUN wget https://ftp.postgresql.org/pub/source/v11.1/postgresql-11.1.tar.gz
# XXX TBD run signature check here.  Currently unsupport by postgres project.
# RUN tar xzvf postgresql-11.1.tar.gz
# RUN cd postgresql-11.1 && \
# ./configure --prefix `pwd` --without-readline --without-zlib && \
# make && \
# make install
RUN wget --no-verbose https://s3-us-west-2.amazonaws.com/public.iam.mozilla.com/postgresql-11.1-compiled.tar.gz
RUN tar xzf postgresql-11.1-compiled.tar.gz
# We get this artifact from S3 now.
# RUN wget https://files.pythonhosted.org/packages/5c/1c/6997288da181277a0c29bc39a5f9143ff20b8c99f2a7d059cfb55163e165/psycopg2-2.8.3.tar.gz
# RUN tar xzvf psycopg2-2.8.3.tar.gz
# RUN cd psycopg2-2.8.3 && \
# sed -i s/pg_config\ =/pg_config\ =\\/postgresql-11.1\\/bin\\/pg_config/ setup.cfg && \
# python3 setup.py build
RUN wget --no-verbose https://s3-us-west-2.amazonaws.com/public.iam.mozilla.com/psycopg2-2.8.3.tar.gz
RUN tar xzf psycopg2-2.8.3.tar.gz
RUN cp -ar /postgresql-11.1/lib/* /usr/lib64/
WORKDIR /var/task
RUN echo "export PATH=$PATH:/node_modules/.bin:/postgresql-11.1/bin" >> ~/.bashrc
