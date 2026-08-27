# ZenAI

ZenAI is an intelligent, secure database query assistant and analytics engine with natural language querying, schema introspection, and automated visualization.

## Architecture

- **Backend:** FastAPI (Python 3.12), SQLAlchemy, AsyncPG, ChromaDB, Google Gemini AI
- **Frontend:** Next.js (App Router), React, Tailwind CSS, TypeScript, Chart.js / Recharts

## Getting Started

### Backend Setup
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your variables:
   ```bash
   cp .env.example .env
   ```
5. Start the backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup
1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```
4. Run the development server:
   ```bash
   npm run dev
   ```

## License
MIT
