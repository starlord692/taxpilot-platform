# TaxPilot Frontend

Production frontend for TaxPilot, built with Next.js 15, TypeScript, Tailwind CSS v4, and shadcn/ui conventions. It communicates with the TaxPilot FastAPI service only through REST APIs.

## Local setup

1. Install dependencies with `npm install`.
2. Copy `.env.example` to `.env.local` and set the backend API URL.
3. Start development with `npm run dev`.
4. Open `http://localhost:3000`.

## Commands

- `npm run dev` — local development
- `npm run lint` — static analysis
- `npm run build` — production build
- `npm run start` — serve the production build

Protected product routes are reserved under `/workspace`, `/clients`, and `/settings`. Login and ERP screens intentionally are not part of FP-000.
