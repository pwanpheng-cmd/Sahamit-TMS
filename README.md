# Sahamit TMS (Streamlit) - Starter

This is a lightweight Streamlit starter inspired by the Canvas TMS concept.
It uses local SQLite for storage (no cloud dependency).

## 1) Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Run
```bash
streamlit run app.py
```

## Notes
- Toggle "Use demo data" in the sidebar to seed sample data.
- Replace SQLite with your real backend later (Dataverse, SQL, etc.).
