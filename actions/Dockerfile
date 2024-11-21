FROM rasa/rasa-sdk:3.6.2

COPY requirements_actions.txt /app/requirements_actions.txt

USER root

RUN pip install --no-cache-dir -r /app/requirements_actions.txt 

EXPOSE 5055

USER 1001

CMD ["run", "actions"]
