FROM python:3.11-slim

# Install OS dependencies
RUN apt-get update && apt-get install -y libglib2.0-0 libgl1-mesa-glx

# Copy and install Python requirements
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browser binaries
RUN playwright install --with-deps

# Copy app code
COPY . /app
WORKDIR /app

# Run the app
CMD ["python", "main.py"]
