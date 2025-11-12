# Lex Frontend

A modern Next.js web interface for searching UK legislation and caselaw built with shadcn/ui and Tailwind CSS.

## Features

- 🔍 **Legislation Search** - Search through 125K+ UK laws from 1963-present
- ⚖️ **Caselaw Search** - Semantic search across 1.9M+ court cases from 2001-present
- 🎨 **Modern UI** - Built with shadcn/ui components and Tailwind CSS
- 📱 **Responsive** - Mobile-first design with collapsible sidebar
- 🌙 **Dark Mode** - Automatic dark mode support

## Prerequisites

- [Bun](https://bun.sh/) v1.0+
- Lex backend API running on `localhost:8000`

## Quick Start

```bash
# Install dependencies
bun install

# Run development server
bun dev

# Build for production
bun run build

# Start production server
bun start
```

Open [http://localhost:3000](http://localhost:3000) to view the app.

## API Integration

The frontend connects to the Lex backend API. You can use either:

### Option 1: Public API (No Local Backend)

Set the public API endpoint in `.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io
```

**⚠️ Experimental**: Public API is for development/testing only. Not guaranteed to be available.

### Option 2: Local Backend

Default configuration connects to `http://localhost:8000`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Make sure the backend is running before starting the frontend.

### Available Endpoints

- **Legislation**: `POST /legislation/search`
- **Caselaw**: `POST /caselaw/search`

## Project Structure

```
app/
├── src/
│   ├── app/                 # Next.js app router pages
│   │   ├── page.tsx         # Home page
│   │   ├── legislation/     # Legislation search
│   │   └── caselaw/         # Caselaw search
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── app-sidebar.tsx  # Main sidebar navigation
│   │   └── ...
│   └── lib/
│       └── utils.ts         # Utility functions
└── public/                  # Static assets
```

## Development

This app uses:

- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **Components**: shadcn/ui
- **Icons**: Lucide React
- **Runtime**: Bun

### Adding Components

```bash
bunx shadcn@latest add [component-name]
```

### Customizing Navigation

Edit `src/components/app-sidebar.tsx` to modify sidebar navigation items.

### Search Pages

- Legislation: `src/app/legislation/page.tsx`
- Caselaw: `src/app/caselaw/page.tsx`

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui](https://ui.shadcn.com)
- [Tailwind CSS](https://tailwindcss.com)

## License

MIT - See root LICENSE file
