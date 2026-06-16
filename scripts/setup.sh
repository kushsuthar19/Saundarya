#!/bin/bash
# ============================================================
# Saundarya Beauty Care — Setup & Run Script
# ============================================================
set -e

echo "╔══════════════════════════════════════════════════╗"
echo "║   Saundarya Beauty Care — Backend Setup          ║"
echo "╚══════════════════════════════════════════════════╝"

# ── 1. Check Python ───────────────────────────────────────
echo ""
echo "▶ Checking Python version..."
python3 --version || { echo "ERROR: Python 3 not found"; exit 1; }
PYTHON_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_VER" -lt "10" ]; then
    echo "ERROR: Python 3.10+ required"
    exit 1
fi
echo "  ✅ Python OK"

# ── 2. Virtual environment ────────────────────────────────
if [ ! -d "venv" ]; then
    echo ""
    echo "▶ Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "  ✅ Virtual env activated"

# ── 3. Install dependencies ───────────────────────────────
echo ""
echo "▶ Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✅ Dependencies installed"

# ── 4. Check .env ─────────────────────────────────────────
echo ""
echo "▶ Checking environment..."
if [ ! -f ".env" ]; then
    echo "  ⚠️  .env not found — copying from .env.example"
    cp .env.example .env
    echo "  ❗ IMPORTANT: Edit .env with your Oracle DB credentials and SECRET_KEY!"
    echo "  Generate SECRET_KEY: python3 -c \"import secrets; print(secrets.token_hex(32))\""
fi

# ── 5. Check Oracle connectivity ─────────────────────────
echo ""
echo "▶ Testing Oracle DB connection..."
python3 -c "
import os, sys
from dotenv import load_dotenv
load_dotenv()
user = os.getenv('ORACLE_USER','')
pw = os.getenv('ORACLE_PASSWORD','')
dsn = os.getenv('ORACLE_DSN','localhost:1521/XEPDB1')
if not pw or pw == 'your_db_password_here':
    print('  ⚠️  ORACLE_PASSWORD not set in .env — skipping connection test')
    sys.exit(0)
try:
    import oracledb
    conn = oracledb.connect(user=user, password=pw, dsn=dsn)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM DUAL')
    print('  ✅ Oracle DB connected!')
    conn.close()
except Exception as e:
    print(f'  ❌ Oracle connection failed: {e}')
    print('  Check ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN in .env')
    sys.exit(1)
"

echo ""
echo "════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your Oracle credentials"
echo "  2. Run database schema: run_schema.sh"
echo "  3. Start server: ./run.sh"
echo "════════════════════════════════════════════"
