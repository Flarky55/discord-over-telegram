export $(grep -v '^#' .env | xargs)

source .venv/bin/activate

python app.py