# Usa uma imagem base do Python 3.12
FROM python:3.12-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de dependências e as instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY app.py .

# Expõe a porta que a aplicação usa
EXPOSE 8000

# Comando para iniciar a aplicação.
# A variável de ambiente PROCESS_ID será fornecida em tempo de execução pelo Docker Compose.
# ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "app.py"]
