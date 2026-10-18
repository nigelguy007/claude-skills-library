# Build from the REPOSITORY ROOT so the skills library is included:
#   docker build -f tools/meeting-consultant/Dockerfile -t meeting-consultant .
FROM python:3.12-slim
WORKDIR /app
COPY tools/meeting-consultant/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY skills /app/skills
COPY tools/meeting-consultant /app/tools/meeting-consultant
ENV SKILLS_DIRS=/app/skills DATA_DIR=/data LEARNED_SKILLS_DIR=/data/learned_skills PYTHONUNBUFFERED=1
WORKDIR /app/tools/meeting-consultant
EXPOSE 8000
CMD ["python", "-m", "consultant", "serve"]
