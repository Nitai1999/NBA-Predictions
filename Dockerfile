# 1. Use the stable Python 3.12 slim image to keep it lightweight
FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Install system dependencies (needed for some pandas/numpy operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy only requirements first (leverages Docker caching)
COPY requirements.txt .

# 6. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy the rest of your project code
COPY . .

# 8. Create the data directory structure
RUN mkdir -p data/raw

# 9. Set the command to run your prediction engine
# (Or your web server once you build the site)
CMD ["python", "src/run_daily_predictions.py"]