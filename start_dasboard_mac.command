#!/bin/bash
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install Python 3.12 from python.org, then run this again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "First-time setup: installing the required packages. This can take a few minutes..."
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
else
  . .venv/bin/activate
fi

( sleep 4 && open "http://localhost:8501" ) &
streamlit run app.py --server.headless true --browser.gatherUsageStats false
read -n 1 -s -r -p "Press any key to close..."