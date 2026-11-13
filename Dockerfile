FROM python:3.12-slim
WORKDIR /srv/agentdesk
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY evals ./evals
COPY frontend ./frontend
COPY data ./data
ENV AGENTDESK_STATE_FILE=/srv/agentdesk/data/state.json
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
