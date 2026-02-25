FROM python:3.13-slim

WORKDIR /app

COPY main.py ./

CMD ["python", "autonomy-packages-bumper.py"]
