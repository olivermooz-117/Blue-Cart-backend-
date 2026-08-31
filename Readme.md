BlueCart Backend is a Flask-based REST API that powers the BlueCart Marketplace. It provides product search, MB/CB scoring, user authentication, and search history management.

## 🌐 Live API

- **Production URL:** https://blue-cart-backend-ynqy.onrender.com
- **Health Check:** https://blue-cart-backend-ynqy.onrender.com/api/health, 


- Local Development
Prerequisites
Python 3.10+

PostgreSQL (or SQLite for development)

 1 - Setup
Clone the repository

git clone https://github.com/olivermooz-117/Blue-Cart-backend
cd Blue-Cart-backend

2 - Create virtual environment

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3 - Install dependencies

pip install -r requirements.txt
Configure environment variables

4 - cp .env.example .env
# Edit .env with your database URL and API keys
5 - Initialize database

flask --app app init-db
Run the development server

python3 app.py