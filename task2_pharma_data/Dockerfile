
FROM python:3.10


WORKDIR /app


COPY . .


RUN pip install -r requirements.txt


CMD ["bash", "-c", "python collect_drug_data.py && python validate_data.py && python generate_report.py"]

