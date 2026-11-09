# PI_ADSP_CallVerse_NeuroNova

CallVerse – AI-Powered Contact Center Digital Twin

## Overview

This project was developed as part of the PI – Applied Data Science Program at Esprit School of Engineering (Academic Year 2025–2026). CallVerse is an AI-powered Digital Twin of an online parapharmacy contact center (PharmaShop), designed to simulate sensitive customer interactions, evaluate customer service quality, detect potential risks, and generate corrective action plans through a unified multi-agent AI system.

Built around a Design Thinking methodology, CallVerse combines conversational AI, Retrieval-Augmented Generation (RAG), LLM-based evaluation, fine-tuned language models, and rule-based decision-making to reproduce and analyze realistic customer service scenarios in a controlled simulation environment.

## Features

***Client Simulator Agent*** — Simulates 8 distinct customer personas (calm, impatient, nervous, dissatisfied, etc.) using a fine-tuned Qwen2.5-3B model, Ollama, and persona-based prompting to generate realistic customer conversations.

***Customer Advisor Agent*** — Provides context-aware and document-grounded responses to customer inquiries using a Modular RAG pipeline, combining intelligent routing, ChromaDB vector search, MiniLM embeddings, and Groq or Ollama LLM inference.

***Quality Analyst Agent*** — Automatically evaluates advisor responses, assigns quality scores, identifies potential risks, and detects inappropriate or unsafe responses using Gemini as an LLM judge, deterministic safety rules, and a fine-tuned Qwen-LoRA risk classifier.

***Workforce Manager Agent*** — Transforms quality evaluation results into structured corrective action plans using deterministic business rules, without relying on an additional LLM.

***Global Conversation Simulation*** — Orchestrates the four agents in a unified workflow, from customer message generation to advisor response, quality evaluation, and workforce action planning.

***Quality Monitoring & KPI Dashboard*** — Tracks conversation quality, evaluation scores, detected risks, and performance indicators through interactive dashboards.

***Conversation History & Analytics*** — Stores simulation sessions, customer profiles, conversation turns, evaluation results, and related sources for historical analysis and reporting.

***Database Integration & Power BI Reporting*** — PostgreSQL integration for structured simulation data storage and analytical reporting, with a dedicated view for Power BI integration.

## Tech Stack

### Frontend

*Main web interface* : React.js

*Development server & proxy* : Vite

*API communication* : REST API / HTTP client

*Dashboards & KPI visualization* : React-based interactive dashboards

### Backend

*Primary language* : Python 3.10+

*REST API backend* : FastAPI

*API documentation* : Swagger / OpenAPI

*Multi-agent orchestration* : Custom simulation orchestrator

*RAG framework* : Modular RAG (intelligent router + retrieval pipeline)

*Vector database* : ChromaDB

*Embedding model* : Sentence Transformers / paraphrase-multilingual-MiniLM-L12-v2

*Cloud LLM inference* : Groq

*Local LLM inference* : Ollama

*Customer simulation model* : Fine-tuned Qwen2.5-3B

*Advisor LLM* : Qwen2.5-7B / Groq models

*Quality evaluation* : Gemini API (LLM-as-a-Judge)

*Risk classification* : Fine-tuned Qwen-LoRA

*Decision-making & action planning* : Rule-based deterministic engine

*Structured data storage* : PostgreSQL

*Local evaluation storage* : SQLite

*Simulation history* : JSON-based storage

*Testing* : Pytest

## Architecture

```text
CallVerse – Contact Center Digital Twin

├── Agent 1: Client Simulator
│   └── Qwen2.5-3B Fine-tuned · Ollama · Persona Prompting
│
├── Agent 2: Customer Advisor
│   └── Modular RAG · Router · ChromaDB · MiniLM · Groq / Ollama
│
├── Agent 3: Quality Analyst
│   └── Gemini LLM-as-a-Judge · Safety Rules · Qwen-LoRA
│
├── Agent 4: Workforce Manager
│   └── Deterministic Rules · Corrective Action Plans
│
├── Global Simulation Orchestrator
│   └── Client → Advisor → Quality Analyst → Workforce Manager
│
├── Data & Analytics
│   └── PostgreSQL · SQLite · JSON · Power BI
│
├── Presentation
│   └── React.js · Vite · Interactive Dashboards
│
└── Infrastructure
    └── FastAPI · REST API · Ollama · ChromaDB
```

## Contributors

**Ines Moalla** · **Nour Rajhi** · **Baha Saadaoui** · **Yosri Awedi** · **Safa Mahjoub** · **Samar Touil**

**Team Neuro Nova**

## Academic Context

Developed at Esprit School of Engineering – Tunisia  
PI – Applied Data Science Program (ADSP)  
5DS8 | Academic Year 2025–2026

## Getting Started

**Prerequisites:**

```bash
python --version
node --version
ollama --version
```

**1. Clone the repository:**

```bash
git clone https://github.com/nourrajhii/Esprit_PIADSP_5DS8_2026_CallVerse_NeuroNova.git
cd Esprit_PIADSP_5DS8_2026_CallVerse_NeuroNova
```

**2. Set up the Backend:**

```powershell
cd RAG
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**3. Configure Environment Variables:**

```powershell
copy .env.example .env
```

Add your `GEMINI_API_KEY` to `RAG/.env`. Configure the optional Groq and PostgreSQL credentials if needed.

**4. Download the Ollama Model:**

```bash
ollama pull qwen2.5:7b
```

For the fine-tuned client simulator, obtain the `.gguf` model file from the team, configure the `client/modele/Modelfile`, and run:

```bash
ollama create qwen-client-v2 -f client/modele/Modelfile
```

**5. Start the Ollama Service:**

```bash
ollama serve
```

**6. Run the Backend:**

From the `RAG` directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --port 8000
```

**7. Run the Frontend:**

Open another terminal:

```bash
cd dt-front
npm install
```

Configure `VITE_USE_MOCK=false` in `dt-front/.env`, then run:

```bash
npm run dev
```

**8. Access the Application:**

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger Documentation: http://localhost:8000/docs
- Backend Health: http://localhost:8000/api/health
- Quality Analyst Health: http://localhost:8000/api/quality/health

**9. Run Tests:**

From the `RAG` directory:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite includes 41 tests covering the Quality Analyst, Workforce Manager, and global simulation workflow. Tests use mocked providers and do not require API keys.

## Acknowledgments

- **Esprit School of Engineering – Tunisia** — Academic supervision and institutional support.
- **PharmaShop** — Business context and customer service scenarios used for the simulation.
- **Alibaba Cloud / Qwen Team** — Qwen2.5 language models and fine-tuning ecosystem.
- **Google Gemini** — LLM-as-a-Judge for automated quality evaluation.
- **Groq** — Fast cloud-based LLM inference.
- **Ollama** — Local LLM execution and model management.
- **Sentence Transformers** — Multilingual embedding model for semantic retrieval.
- **ChromaDB** — Vector database for the RAG retrieval pipeline.
- **Hugging Face** — Model ecosystem and fine-tuning tools.
- **FastAPI** — Backend API framework.
- **React.js & Vite** — Frontend development and interface.
- **PostgreSQL** — Structured simulation data storage.
- **SQLite** — Local quality evaluation storage.
- **Power BI** — Business intelligence and analytical reporting.
- **Pytest** — Automated testing framework.
