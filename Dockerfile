FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt /app
RUN pip install -r requirements.txt

COPY code /app

ENV KAFKA_URL=kafka-cluster.default:9092
ENV TOPIC_NAME=undefined
ENV TRELLO_KEY=undefined
ENV TRELLO_TOKEN=undefined
ENV TRELLO_LIST=undefined
ENV TRELLO_APP_MEMBER_ID=undefined

CMD python3 -u service.py