from docker.io/library/pypy:3.11-bookworm

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt
COPY . /usr/src/app

CMD ["twistd", "-ny", "buildbot.tac"]
