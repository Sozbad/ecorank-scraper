FROM python:3.11-slim

# Install basic system dependencies
RUN apt-get update && apt-get install -y libglib2.0-0 libgl1-mesa-glx

# Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Start app
CMD ["python", "main.py"]
