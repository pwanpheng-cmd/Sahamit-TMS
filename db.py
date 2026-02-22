from __future__ import annotations
import os
import random
from datetime import date, timedelta, datetime
import pandas as pd
from sqlalchemy import create_engine, text

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "tms.db")

def get_engine():
    os.makedirs(DB_DIR, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", future=True)

def ensure_schema(engine):
    # Minimal schema inspired by the Canvas TMS package.
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS shm_POHeader (
            shm_ponumber TEXT PRIMARY KEY,
            shm_suppliername TEXT NOT NULL,
            shm_podivision TEXT NOT NULL,
            shm_deliverystatus TEXT NOT NULL,
            shm_podate TEXT NOT NULL,
            shm_requestdate TEXT NOT NULL,
            shm_deliverydate TEXT NOT NULL,
            shm_totalqty REAL DEFAULT 0,
            shm_transportname TEXT,
            shm_trucktype TEXT,
            shm_slotbooking INTEGER DEFAULT 0,
            shm_truckno TEXT,
            shm_truckqty REAL,
            shm_transportcost REAL,
            shm_scmnote TEXT,
            shm_recorddate TEXT,
            shm_recordby TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_PODetails (
            shm_podetailsindex TEXT PRIMARY KEY,
            shm_ponumber TEXT NOT NULL,
            shm_item TEXT,
            shm_qty REAL DEFAULT 0,
            shm_uom TEXT,
            shm_remark TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_Supplier (
            shm_suppliercode TEXT PRIMARY KEY,
            shm_name TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_DC (
            shm_dccode TEXT PRIMARY KEY,
            shm_name TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_Product (
            shm_shmitem TEXT PRIMARY KEY,
            shm_name TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_User (
            shm_username TEXT PRIMARY KEY,
            shm_fullname TEXT,
            shm_userclass INTEGER DEFAULT 2
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_LoginLog (
            shm_logid INTEGER PRIMARY KEY AUTOINCREMENT,
            shm_user TEXT,
            shm_logdate TEXT,
            shm_logtime TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_KPITransport (
            shm_kpitranref TEXT PRIMARY KEY,
            shm_name TEXT,
            shm_value REAL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shm_KPISupplier (
            shm_kpisubref TEXT PRIMARY KEY,
            shm_name TEXT,
            shm_value REAL
        );
        """,
    ]
    with engine.begin() as conn:
        for q in ddl:
            conn.execute(text(q))

def read_table(engine, table: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(text(f"SELECT * FROM {table}"), con=engine)
    except Exception:
        return pd.DataFrame()

def upsert_po_header(engine, record: dict):
    cols = list(record.keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    updates = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "shm_ponumber"])
    sql = f"""
        INSERT INTO shm_POHeader ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(shm_ponumber) DO UPDATE SET {updates};
    """
    with engine.begin() as conn:
        conn.execute(text(sql), record)

def read_po_details_by_po(engine, po: str) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql_query(
            text("SELECT * FROM shm_PODetails WHERE shm_ponumber = :po ORDER BY shm_podetailsindex"),
            con=conn,
            params={"po": po},
        )

def upsert_transport_booking(engine, po: str, patch: dict):
    patch = dict(patch)
    patch["shm_ponumber"] = po
    cols = list(patch.keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    updates = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "shm_ponumber"])
    sql = f"""
        INSERT INTO shm_POHeader ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(shm_ponumber) DO UPDATE SET {updates};
    """
    with engine.begin() as conn:
        conn.execute(text(sql), patch)

def upsert_master_record(engine, table: str, key_col: str, key: str, name: str):
    sql = f"""
        INSERT INTO {table} ({key_col}, shm_name)
        VALUES (:k, :n)
        ON CONFLICT({key_col}) DO UPDATE SET shm_name=excluded.shm_name;
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"k": key, "n": name})

def seed_demo_data(engine):
    df = read_table(engine, "shm_POHeader")
    if not df.empty:
        return

    divisions = ["Foods", "NF", "PCB", "Import-Foods", "Import-NF"]
    statuses = ["Pending", "Done", "Hold"]
    transports = ["Supplier", "SHM", "KEL", "TDM"]

    today = date.today()
    rows = []
    for i in range(1, 51):
        po = f"PO{today.strftime('%y%m')}-{i:04d}"
        podate = today - timedelta(days=random.randint(0, 20))
        req = podate + timedelta(days=random.randint(0, 7))
        delivery = req + timedelta(days=random.randint(0, 10))
        rows.append(
            dict(
                shm_ponumber=po,
                shm_suppliername=f"Supplier {random.randint(1, 8)}",
                shm_podivision=random.choice(divisions),
                shm_deliverystatus=random.choice(statuses),
                shm_podate=podate.isoformat(),
                shm_requestdate=req.isoformat(),
                shm_deliverydate=delivery.isoformat(),
                shm_totalqty=float(random.randint(50, 800)),
                shm_transportname=random.choice(transports),
                shm_trucktype=random.choice(["4W", "6W", "10W"]),
                shm_slotbooking=random.choice([0, 1]),
                shm_transportcost=float(random.randint(1000, 12000)),
                shm_recorddate=datetime.utcnow().isoformat(timespec="seconds"),
                shm_recordby="demo_seed",
            )
        )

    pd.DataFrame(rows).to_sql("shm_POHeader", con=engine, if_exists="append", index=False)

    det = []
    for r in rows:
        for j in range(random.randint(1, 5)):
            det.append(
                dict(
                    shm_podetailsindex=f"{r['shm_ponumber']}-{j+1}",
                    shm_ponumber=r["shm_ponumber"],
                    shm_item=f"ITEM-{random.randint(100,999)}",
                    shm_qty=float(random.randint(1, 50)),
                    shm_uom="PCS",
                    shm_remark="",
                )
            )
    pd.DataFrame(det).to_sql("shm_PODetails", con=engine, if_exists="append", index=False)

    pd.DataFrame([{"shm_suppliercode": f"S{n:03d}", "shm_name": f"Supplier {n}"} for n in range(1, 9)]).to_sql(
        "shm_Supplier", con=engine, if_exists="append", index=False
    )
    pd.DataFrame([{"shm_dccode": f"DC{n:02d}", "shm_name": f"DC {n}"} for n in range(1, 6)]).to_sql(
        "shm_DC", con=engine, if_exists="append", index=False
    )
    pd.DataFrame([{"shm_shmitem": f"ITEM-{n}", "shm_name": f"Product {n}"} for n in range(100, 130)]).to_sql(
        "shm_Product", con=engine, if_exists="append", index=False
    )
    pd.DataFrame([{"shm_username": "user@example.com", "shm_fullname": "Demo User", "shm_userclass": 2}]).to_sql(
        "shm_User", con=engine, if_exists="append", index=False
    )
