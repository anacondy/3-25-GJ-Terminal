# GJ Terminal - AI-Powered Government Jobs Dashboard

*No Clutter, Just Data* - A modern, terminal-style web dashboard for Indian government job aspirants.

## Overview

GJ Terminal is a next-generation web application tailored for Indian students and competitive exam aspirants. It replaces traditional, ad-heavy portals with a focused, glassmorphism-styled interface. The built-in AI "Research Team" powered by Google Gemini autonomously scouts for the latest exam notifications, updates cutoff scores, and maintains a verified job database.

## Key Features

- **Automated Data Scout**: Python bot (`data_scout.py`) integrates Gemini 2.5 Pro to fetch, analyze, and batch-process government job data
- **Intelligent Updates**: Selectively checks old/missing data (>7 days), preserves verified info, discovers new job posts
- **Glassmorphism UI**: Responsive dark-themed interface with animated frosted glass effects
- **Dynamic Details View**: 3-column grid with real-time data cards (cutoffs, patterns, fees, vacancies)
- **Keyboard Controls**: `Ctrl+K` for search, arrow key navigation, `Esc` to close overlays
- **Live Status Indicator**: Flickering dot signals active updates + auto-refresh

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python (Flask) |
| Database | SQLite (relational tables) |
| AI Model | Google Gemini 1.5/2.5 Pro |
| Frontend | HTML5, CSS3 (Grid/Flexbox), JavaScript ES6+ |
| Techniques | Defensive SQL, API rate limiting, fuzzy matching with `difflib` |

## Project Structure

```
/GJ_Terminal_Project/
  ├── app.py              # Flask server with routes
  ├── database_setup.py   # Database schema initialization
  ├── data_scout.py       # Gemini AI research bot
  ├── jobs.db             # SQLite data store
  └── /templates/
        ├── index.html    # Main dashboard
        └── details.html  # Job detail view
```

## Getting Started

1. Clone this repository
2. Install dependencies: `pip install flask google-generativeai`
3. Set up your Gemini API key
4. Run database setup: `python database_setup.py`
5. Start the server: `python app.py`

## Future Roadmap

- Secure admin portal for PDF uploads
- Real-time notifications for exam status changes
- Historical cutoff analytics (5-year trends)
- One-click deep links for applications

---

*Built with Flask + Gemini AI for Indian competitive exam aspirants*
