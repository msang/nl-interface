FROM rasa/rasa:3.6.15

COPY requirements.txt /app/requirements.txt

USER root
RUN pip install --no-cache-dir -r /app/requirements.txt && python -m spacy download it_core_news_sm

EXPOSE 5005

USER 1001

CMD ["run","-m", "/app/models", "--cors", "*", "--enable-api", "--log-file", "out.log"]


