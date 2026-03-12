# ClerKase - AI-Powered Clinical Clerking Assistant

ClerKase is an intelligent web application that helps medical students complete clinical case documentation to professional standards. It guides students through the clerking process section-by-section, asks clarifying questions when information is missing, detects contradictions, and generates professional documents.

## Features

- **Structured Clerking**: Complete clinical documentation section-by-section with guided prompts
- **AI-Powered Clarifications**: Get intelligent questions to fill gaps and improve documentation
- **Multiple Rotations**: Support for Paediatrics, Surgery, Internal Medicine, Obstetrics & Gynaecology, Psychiatry, and Emergency Medicine
- **Professional Export**: Export cases as Markdown or Word documents
- **Quality Assurance**: Detect contradictions and missing critical information
- **Progress Tracking**: Visual progress tracking for each case

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Home Page  │  │  Dashboard  │  │  Case Editor            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (Flask API)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ State Mgr   │  │ Input Parser│  │ Clarification Engine    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Doc Compiler│  │  Database   │  │  Auth (JWT)             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- npm or yarn

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd clerkase
   ```

2. **Install Backend Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Install Frontend Dependencies**
   ```bash
   cd ..
   npm install
   ```

4. **Configure Environment Variables**
   
   Backend (`.env`):
   ```
   FLASK_DEBUG=true
   SECRET_KEY=your-secret-key
   JWT_SECRET_KEY=your-jwt-secret-key
   DATABASE_URL=sqlite:///clerkase.db
   ```
   
   Frontend (`.env`):
   ```
   VITE_API_URL=http://localhost:5000/api
   ```

### Running the Application

**Option 1: Using the startup script**
```bash
cd backend
./start.sh
```

**Option 2: Manual startup**

Terminal 1 - Backend:
```bash
cd backend
python app.py
```

Terminal 2 - Frontend:
```bash
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:5000

## API Endpoints

### Health & Status
- `GET /api/health` - Health check
- `GET /api/status` - System status

### Rotations
- `GET /api/rotations` - List all rotations
- `GET /api/rotations/:id` - Get rotation details
- `GET /api/rotations/:id/template` - Get rotation template
- `GET /api/rotations/:id/sections/:name` - Get section template

### Cases
- `POST /api/cases` - Create new case
- `GET /api/cases` - List all cases
- `GET /api/cases/:id` - Get case details
- `DELETE /api/cases/:id` - Delete case

### Sections
- `GET /api/cases/:id/sections/:name` - Get section data
- `PUT /api/cases/:id/sections/:name` - Update section
- `POST /api/cases/:id/sections/:name/submit` - Submit section
- `POST /api/cases/:id/sections/:name/clarifications` - Answer clarifications
- `POST /api/cases/:id/sections/:name/skip` - Skip section

### Workflow
- `POST /api/cases/:id/next` - Move to next section
- `GET /api/cases/:id/progress` - Get case progress

### Parsing
- `POST /api/parse` - Parse clinical input
- `POST /api/parse/socrates` - Parse SOCRATES pain assessment

### Clarifications
- `POST /api/clarify` - Generate clarifications
- `POST /api/clarify/contradictions` - Detect contradictions

### Export
- `POST /api/cases/:id/export` - Export case
- `GET /api/cases/:id/export/download` - Download export
- `GET /api/cases/:id/summary` - Get case summary

## Supported Rotations

| Rotation | Sections |
|----------|----------|
| Paediatrics | 18 |
| Surgery | 17 |
| Internal Medicine | 16 |
| Obstetrics & Gynaecology | 15 |
| Psychiatry | 20 |
| Emergency Medicine | 9 |

## Technology Stack

### Frontend
- React 18
- TypeScript
- Tailwind CSS
- shadcn/ui components
- React Router

### Backend
- Python 3.8+
- Flask
- SQLAlchemy
- python-docx
- Anthropic Claude API (optional)

### Database
- SQLite (default)
- PostgreSQL (production)

## Development

### Project Structure
```
clerkase/
├── backend/
│   ├── app.py                 # Flask application
│   ├── state_manager.py       # Case state management
│   ├── input_parser.py        # Clinical input parsing
│   ├── clarification_engine.py # AI-powered clarifications
│   ├── document_compiler.py   # Document generation
│   ├── auth/                  # Authentication
│   ├── database/              # Database models
│   ├── templates/             # Rotation templates (JSON)
│   └── requirements.txt
├── src/
│   ├── api/                   # API client
│   ├── components/            # React components
│   ├── pages/                 # Page components
│   ├── types/                 # TypeScript types
│   └── App.tsx
└── README.md
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For support, please open an issue on GitHub or contact the development team.

---

Made with ❤️ for medical students
