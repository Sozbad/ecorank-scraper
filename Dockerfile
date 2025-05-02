# Use the official lightweight Python image.
FROM python:3.11-slim

# Install necessary packages
RUN apt-get update && apt-get install -y libglib2.0-0 libgl1-mesa-glx
RUN pip install flask requests beautifulsoup4 firebase-admin PyMuPDF

# Copy local code to the container image
COPY . /app
WORKDIR /app

# Run the web service
CMD ["python", "main.py"]
