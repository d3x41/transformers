
# Use the updated base image
FROM python:3.13.2-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN useradd -m appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     libsndfile1-dev=1.0.31-2     espeak-ng=1.50+dfsg-10     time=1.9-0.1     git=1:2.39.2-1.1     g++=4:12.2.0-3     cmake=3.25.1-1     pkg-config=1.8.1-1     openssh-client=1:9.2p1-2     && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Change ownership of the app directory to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Command to run the application
CMD ["python3.13", "your_main_script.py"]
