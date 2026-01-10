# AI Council Deployment Guide

This guide covers deploying AI Council to Vercel with Supabase as the database and authentication provider.

## Prerequisites

1. A [Vercel](https://vercel.com) account
2. A [Supabase](https://supabase.com) account
3. An [OpenRouter](https://openrouter.ai) API key

## Step 1: Set Up Supabase

### Create Project

1. Create a new Supabase project
2. Note your project credentials:
   - **Project URL**: Found in Settings > API > Project URL
   - **Anon Key**: Found in Settings > API > Project API keys (`anon` public key)
   - **Service Role Key**: Found in Settings > API > Project API keys (`service_role` key)
   - **JWT Secret**: Found in Settings > API > JWT Settings

### Run Database Migrations

Go to the SQL Editor and run the schema files in order:

1. `supabase/schema.sql` - Creates the base tables
2. `supabase/migration_add_user_auth.sql` - Adds user authentication columns and RLS policies

### Configure Authentication (Invite-Only)

AI Council uses an invite-only authentication model. Users must be created by an administrator.

1. Go to **Authentication > Providers**
2. Ensure **Email** provider is enabled
3. Under **Email Auth**, disable "Enable email confirmations" (optional, for simpler user setup)

To create users:
1. Go to **Authentication > Users**
2. Click "Add user" (or "Invite user")
3. Enter the user's email and a temporary password
4. Share credentials securely with the user

Users can change their password using the "Forgot password" link on the login screen.

## Step 2: Configure Environment Variables

Create a `.env` file for local development (do not commit this file):

```bash
# OpenRouter API Key (required)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Supabase Backend Configuration (required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret-here

# CORS Origins (comma-separated, required for production)
CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app

# Frontend Supabase Configuration (required)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...your-anon-key

# Frontend API URL (optional, for cross-origin deployments)
VITE_API_URL=
```

### Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key for LLM access | Yes |
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (backend only) | Yes |
| `SUPABASE_JWT_SECRET` | JWT secret for token verification | Yes |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | Yes (production) |
| `VITE_SUPABASE_URL` | Supabase URL for frontend auth | Yes |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key for frontend auth | Yes |
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

**Backend:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Your Supabase service role key
- `SUPABASE_JWT_SECRET` - Your Supabase JWT secret
- `CORS_ORIGINS` - Your Vercel domain (e.g., `https://your-app.vercel.app`)

**Frontend:**
- `VITE_SUPABASE_URL` - Your Supabase project URL
- `VITE_SUPABASE_ANON_KEY` - Your Supabase anon/public key

## Step 4: Verify Deployment

1. Visit your Vercel URL
2. You should see the login screen
3. Log in with a user account created in Supabase
4. Create a new conversation and test the council

## Managing Users

### Creating New Users

1. Go to your Supabase dashboard
2. Navigate to Authentication > Users
3. Click "Add user" or "Invite user"
4. Enter email and password
5. Share credentials securely

### Resetting Passwords

Users can reset their own passwords:
1. Click "Forgot password?" on the login screen
2. Enter their email address
3. Check email for reset link

Admins can also reset passwords from the Supabase dashboard.

### Removing Users

1. Go to Authentication > Users in Supabase
2. Find the user and click the options menu
3. Select "Delete user"

Note: Deleting a user will cascade delete their conversations, presets, and predictions (if RLS policies are configured correctly).

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

### "Session expired" error
- The JWT token has expired - refresh the page to get a new token
- Check that `SUPABASE_JWT_SECRET` matches your Supabase project

### "Invalid login credentials" error
- Verify the user exists in Supabase Authentication > Users
- Check that the password is correct
- Ensure the user's email is confirmed (if email confirmation is enabled)

### CORS errors
- Ensure `CORS_ORIGINS` includes your Vercel domain
- Make sure there are no trailing slashes in the origins

### Database connection errors
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are correct
- Ensure you ran all schema migrations in Supabase

### OpenRouter errors
- Verify your `OPENROUTER_API_KEY` is valid
- Check your OpenRouter account has credits

## Security Notes

1. **Never commit** your `.env` file or any credentials
2. The `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS - keep it secret
3. The `SUPABASE_JWT_SECRET` is used to verify tokens - keep it secret
4. The `VITE_SUPABASE_ANON_KEY` is safe to expose (it's public)
5. All user data is isolated via Row Level Security policies
6. Invite-only model prevents unauthorized signups

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Frontend    │────▶│  Vercel Edge    │────▶│   OpenRouter    │
│   (React/Vite)  │     │    (FastAPI)    │     │   (LLM APIs)    │
└────────┬────────┘     └────────┬────────┘     └─────────────────┘
         │                       │
         │ Auth                  │ Service Role
         ▼                       ▼
┌─────────────────────────────────────────────┐
│              Supabase                        │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │    Auth     │  │   PostgreSQL + RLS   │   │
│  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Data Flow

1. User logs in via Supabase Auth (frontend)
2. Frontend receives JWT token
3. JWT is sent with each API request (Authorization header)
4. Backend verifies JWT using `SUPABASE_JWT_SECRET`
5. User ID extracted from JWT for RLS queries
6. Backend uses service role key for database operations
7. RLS policies ensure users only see their own data
