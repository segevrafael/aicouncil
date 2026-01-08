# AI Council Deployment Guide

This guide covers deploying AI Council to Vercel with Supabase as the database.

## Prerequisites

1. A [Vercel](https://vercel.com) account
2. A [Supabase](https://supabase.com) account
3. An [OpenRouter](https://openrouter.ai) API key

## Step 1: Set Up Supabase

1. Create a new Supabase project
2. Go to the SQL Editor and run the schema from `supabase/schema.sql`
3. Note your project credentials:
   - **Project URL**: Found in Settings > API > Project URL
   - **Service Role Key**: Found in Settings > API > Project API keys (use `service_role` key, not `anon`)

## Step 2: Configure Environment Variables

Create a `.env` file for local development (do not commit this file):

```bash
# OpenRouter API Key (required)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Supabase Configuration (required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key

# Authentication Password (required for production)
COUNCIL_API_PASSWORD=your-secure-password

# CORS Origins (comma-separated, required for production)
CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app
```

### Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key for LLM access | Yes |
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (backend only) | Yes |
| `COUNCIL_API_PASSWORD` | Password for API authentication | Yes (production) |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | Yes (production) |
| `VITE_API_URL` | API URL for frontend (empty for same-origin) | No |

## Step 3: Deploy to Vercel

### Option A: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel
```

### Option B: Deploy via GitHub

1. Push your code to GitHub
2. Go to [Vercel Dashboard](https://vercel.com/dashboard)
3. Click "New Project"
4. Import your GitHub repository
5. Configure environment variables in Vercel dashboard

### Configure Vercel Environment Variables

In your Vercel project settings, add these environment variables:

- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Your Supabase service role key
- `COUNCIL_API_PASSWORD` - Your chosen password
- `CORS_ORIGINS` - Your Vercel domain (e.g., `https://your-app.vercel.app`)

## Step 4: Verify Deployment

1. Visit your Vercel URL
2. You should see the login screen
3. Enter your password to access the app
4. Create a new conversation and test the council

## Local Development

### Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the backend
cd backend
python -m backend.main
```

### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev
```

## Troubleshooting

### "Authentication required" error
- Ensure `COUNCIL_API_PASSWORD` is set in Vercel environment variables
- Clear your browser's localStorage and try logging in again

### CORS errors
- Ensure `CORS_ORIGINS` includes your Vercel domain
- Make sure there are no trailing slashes in the origins

### Database connection errors
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are correct
- Ensure you ran the schema SQL in Supabase

### OpenRouter errors
- Verify your `OPENROUTER_API_KEY` is valid
- Check your OpenRouter account has credits

## Security Notes

1. **Never commit** your `.env` file or any credentials
2. Use a **strong, unique password** for `COUNCIL_API_PASSWORD`
3. The `SUPABASE_SERVICE_ROLE_KEY` has full database access - keep it secret
4. Consider enabling Supabase Row Level Security for additional protection

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Frontend    │────▶│  Vercel Edge    │────▶│   OpenRouter    │
│   (React/Vite)  │     │    (FastAPI)    │     │   (LLM APIs)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Supabase     │
                        │   (PostgreSQL)  │
                        └─────────────────┘
```
