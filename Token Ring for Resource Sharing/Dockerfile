# Use uma imagem base oficial do Python
FROM python:3.10-slim

# Defina o diretório de trabalho no contêiner
WORKDIR /code

# Copie o arquivo de dependências e instale-as
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copie o código da aplicação para o diretório de trabalho
COPY ./app.py /code/app.py

# Comando para executar a aplicação quando o contêiner iniciar
# ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "app.py"]