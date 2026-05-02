# 1. Use the stable Python 3.12 slim image to keep it lightweight
FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Prevent Python from writing .pyc files and enable unbuffered logging
# This ensures you see your AI's print statements in the cloud logs immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Install system dependencies 
# build-essential is often needed for pandas/numpy performance
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy only requirements first to leverage Docker layer caching
# Note: Ensure you ran `pip freeze > requirements.txt` before building!
COPY requirements.txt .

# 6. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy the rest of your project code
COPY . .

# 8. Create the data directory structure
# This ensures your fetch scripts have a place to save CSVs inside the container
RUN mkdir -p data/raw

# 9. Expose the port Streamlit uses by default
EXPOSE 8501

# 10. Command to run the Streamlit app
# --server.address=0.0.0.0 is critical for cloud deployment
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]