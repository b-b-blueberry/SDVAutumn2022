FROM python:alpine

RUN apk update && apk add \
    build-base \
    sqlite

ADD requirements.txt /autumn/requirements.txt
RUN pip3 install -r /autumn/requirements.txt

WORKDIR /autumn
CMD ["python3", "-u", "main.py"]
