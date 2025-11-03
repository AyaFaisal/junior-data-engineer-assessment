# Task 2: Pharmaceutical Data Collection

An automated pipeline for collecting, validating, and reporting on pharmaceutical data from public medical APIs.

---

## Quick Stats

| Metric                 | Value                 |
| ---------------------- | --------------------- |
| **Drugs Collected**    | 55 / 50+ required     |
| **Success Rate**       | 94.5% (52/55)         |
| **Data Quality Score** | 78/100 (B+)           |
| **Data Sources**       | OpenFDA + RxNorm      |
| **Database Size**      | ~2.5MB                |
| **Completeness**       | 71.8% overall         |

---

## Project Overview

This project implements a complete pharmaceutical data collection pipeline that:

-   Collects drug information from 2 authoritative APIs (OpenFDA, RxNorm).
-   Stores data in an SQLite database with a structured schema.
-   Implements comprehensive validation (6 validation types).
-   Generates detailed quality reports with recommendations.
-   Handles errors gracefully with retry logic and logging.

---

##  Quick Start & How to Run

This project is fully containerized with **Docker**, making setup and execution simple and reproducible. This is the recommended way to run the pipeline.

###  Running with Docker (Recommended)

**Prerequisites:**
*   Docker Desktop installed and running.

**Instructions:**

1.  **Build the Docker Image:**
    From the `task2_pharma_data` directory, run the following command. This will build the container image with all necessary dependencies.
    ```bash
    docker build -t pharma-pipeline .
    ```

2.  **Run the Entire Pipeline:**
    This single command will run the container, execute all three Python scripts in sequence, and save the outputs (database, logs, and reports) to your local machine.
    ```bash
    docker run --rm \
      -v "$(pwd)/data:/app/data" \
      -v "$(pwd)/logs:/app/logs" \
      -v "$(pwd)/Generated_Data_Quality_Report.md:/app/Generated_Data_Quality_Report.md" \
      pharma-pipeline
    ```
    After the command finishes, you can check the `data/`, `logs/`, and the `Generated_Data_Quality_Report.md` file in your project directory.

### Running Manually (Without Docker)

If you prefer not to use Docker, you can run the scripts directly.

**Prerequisites:**
*   Python 3.10 or higher.

**Installation:**
```bash
# Navigate to the project directory
cd task2_pharma_data

# Install dependencies
pip install requests

# (Optional) Set OpenFDA API key for higher rate limits
export OPENFDA_API_KEY=your-key-here  # On macOS/Linux
set OPENFDA_API_KEY=your-key-here     # On Windows
