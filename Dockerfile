# Use the official lightweight Python image.
FROM python:3.11-slim

# Install necessary packages
RUN pip install flask requests beautifulsoup4 firebase-admin PyMuPDF

# Copy local code to the container image
COPY . /app
WORKDIR /app

# Run the web service
CMD ["python", "main.py"]
