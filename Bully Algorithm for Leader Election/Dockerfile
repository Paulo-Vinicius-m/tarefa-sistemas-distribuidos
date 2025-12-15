# Usa uma imagem oficial do Python como imagem base
FROM python:3.10-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Copia o arquivo de dependências para o contêiner
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código da aplicação
COPY app.py .

# Expõe a porta 8000 para o mundo fora deste contêiner
EXPOSE 8000

# Comando para executar a aplicação quando o contêiner for iniciado
# ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "app.py"]