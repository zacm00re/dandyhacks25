# Electron + React + Python Boilerplate

A modern desktop application boilerplate combining Electron, React (with TypeScript), shadcn/ui, and a Python FastAPI backend.

## Features

- ⚛️ **React 18** with TypeScript
- 🎨 **shadcn/ui** components with Tailwind CSS
- ⚡ **Vite** for fast development
- 🖥️ **Electron** for desktop app
- 🐍 **Python FastAPI** backend
- 🔄 Hot reload for both frontend and backend

## Project Structure

```
electron-react-python-app/
├── src/
│   ├── frontend/              # React frontend
│   │   ├── components/
│   │   │   └── ui/           # shadcn/ui components
│   │   ├── lib/
│   │   ├── types/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── backend/              # Python backend
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── main.js               # Electron main process
│   └── preload.js            # Electron preload script
├── public/                   # Static assets
├── dist/                     # Build output
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.js
```

## Prerequisites

- Node.js (v18 or higher)
- Python (v3.8 or higher)
- npm or yarn

## Setup

### 1. Install Node.js Dependencies

```bash
npm install
```

### 2. Install Python Dependencies

```bash
pip install -r src/backend/requirements.txt
```

Or using a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r src/backend/requirements.txt
```

## Development

Run all services concurrently:

```bash
npm run dev
```

This will start:
- Python backend on `http://localhost:8000`
- Vite dev server on `http://localhost:5173`
- Electron app

### Run Services Individually

**Python Backend:**
```bash
npm run dev:python
# or
python src/backend/main.py
```

**Vite Dev Server:**
```bash
npm run dev:vite
```

**Electron:**
```bash
npm run dev:electron
```

## Building

### Build Frontend

```bash
npm run build
```

### Package Electron App

```bash
npm run build:electron
```

This will create distributable packages in the `dist` folder.

## Adding shadcn/ui Components

This boilerplate includes Button and Card components. To add more shadcn/ui components:

1. Visit [ui.shadcn.com](https://ui.shadcn.com)
2. Copy the component code
3. Add to `src/frontend/components/ui/`
4. Import and use in your app

Example components already included:
- Button
- Card

## API Endpoints

The Python backend provides these example endpoints:

- `GET /ping` - Health check
- `GET /api/data` - Sample data endpoint

Add more endpoints in `src/backend/main.py`.

## Communication Between Frontend and Backend

### Direct HTTP Fetch (Development)
```typescript
const response = await fetch('http://localhost:8000/api/data');
const data = await response.json();
```

### Via Electron IPC (Production)
```typescript
const result = await window.electron.pingPython();
```

## Customization

### Tailwind Theme

Edit `tailwind.config.js` and `src/frontend/index.css` to customize colors and styling.

### Electron Window

Modify `src/main.js` to change window size, behavior, and settings.

### Python API

Edit `src/backend/main.py` to add routes, database connections, or business logic.

## License

MIT
