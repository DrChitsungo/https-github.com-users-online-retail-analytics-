FROM python:3.13-slim
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH=/home/user/app/src \
    CHURN_API_URL=http://127.0.0.1:8000 \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
EXPOSE 7860
CMD ["bash", "start.sh"]
