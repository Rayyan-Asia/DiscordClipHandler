FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Install Python and FFmpeg
RUN apt-get update && apt-get install -y python3 python3-pip ffmpeg && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (if needed)
EXPOSE 8000

# Command to run the application
CMD ["python", "-u", "main.py"]