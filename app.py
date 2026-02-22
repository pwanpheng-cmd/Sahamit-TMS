import streamlit as st
import pandas as pd
from datetime import date, datetime
from db import (
    get_engine,
    ensure_schema,
    seed_demo_data,
    read_table,
    upsert_po_header,
    read_po_details_by_po,
    upsert_transport_booking,
    upsert_master_record,
)

st.set_page_config(page_title="Sahamit TMS (Streamlit)", layout="wide")

engine = get_engine()
ensure_schema(engine)

st.sidebar.title("Sahamit TMS")
demo = st.sidebar.toggle("Use demo data", value=True, help="Seed demo data into local SQLite (safe to re-run).")
if demo:
    seed_demo_data(engine)

page = st.sidebar.radio(
    "Menu",
    ["Order Monitor", "PO Detail", "Transport Booking", "Reports & KPI", "Master Data", "Settings"],
)

# ---------------------- PAGE: ORDER MONITOR ----------------------
if page == "Order Monitor":
    st.title("Order Monitor")

    col1, col2, col3, col4 = st.columns([1.2, 1.2, 1.2, 2.4])
    with col1:
        search = st.text_input("Search (PO / Supplier)", value="")
    with col2:
        status = st.selectbox("Status", ["All", "Done", "Pending", "Cancel", "Hold", "MOQ"])
    with col3:
        division = st.selectbox("Division", ["All", "Foods", "NF", "PCB", "Import-Foods", "Import-NF"])
    with col4:
        st.caption("Tip: Select a PO here, then open **PO Detail**.")

    df = read_table(engine, "shm_POHeader")
    if df.empty:
        st.info("No data in shm_POHeader yet. Toggle demo data, or import CSV in Settings.")
    else:
        if search.strip():
            s = search.strip().lower()
            df = df[
                df["shm_ponumber"].str.lower().str.contains(s)
                | df["shm_suppliername"].str.lower().str.contains(s)
            ]
        if status != "All":
            df = df[df["shm_deliverystatus"] == status]
        if division != "All":
            df = df[df["shm_podivision"] == division]

        df = df.sort_values("shm_deliverydate", ascending=False)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total PO", len(df))
        c2.metric("Done", int((df["shm_deliverystatus"] == "Done").sum()))
        c3.metric("Pending", int((df["shm_deliverystatus"] == "Pending").sum()))
        c4.metric("Slot Booked", int((df["shm_slotbooking"] == 1).sum()))

        st.dataframe(
            df[
                [
                    "shm_ponumber",
                    "shm_suppliername",
                    "shm_podivision",
                    "shm_deliverystatus",
                    "shm_podate",
                    "shm_requestdate",
                    "shm_deliverydate",
                    "shm_totalqty",
                    "shm_transportname",
                    "shm_trucktype",
                    "shm_slotbooking",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    with st.expander("➕ Create / Edit PO Header", expanded=False):
        st.subheader("PO Header Form")
        left, right = st.columns([1.2, 1.0])
        with left:
            ponumber = st.text_input("PO Number *", value="")
            supplier = st.text_input("Supplier Name *", value="")
            podiv = st.selectbox("Division *", ["Foods", "NF", "PCB", "Import-Foods", "Import-NF"])
            st_status = st.selectbox("Status *", ["Done", "Pending", "Cancel", "Hold", "MOQ"], index=1)
        with right:
            po_date = st.date_input("PO Date *", value=date.today())
            req_date = st.date_input("Request Date *", value=date.today())
            deliv_date = st.date_input("Delivery Date *", value=date.today())
            totalqty = st.number_input("Total Qty", min_value=0.0, value=0.0, step=1.0)

        save = st.button("Save PO Header", type="primary")
        if save:
            if not ponumber.strip() or not supplier.strip():
                st.error("Please fill required fields: PO Number, Supplier Name.")
            else:
                upsert_po_header(
                    engine,
                    {
                        "shm_ponumber": ponumber.strip(),
                        "shm_suppliername": supplier.strip(),
                        "shm_podivision": podiv,
                        "shm_deliverystatus": st_status,
                        "shm_podate": po_date.isoformat(),
                        "shm_requestdate": req_date.isoformat(),
                        "shm_deliverydate": deliv_date.isoformat(),
                        "shm_totalqty": float(totalqty),
                        "shm_recorddate": datetime.utcnow().isoformat(timespec="seconds"),
                        "shm_recordby": "streamlit_user",
                    },
                )
                st.success("Saved.")
                st.rerun()

# ---------------------- PAGE: PO DETAIL ----------------------
elif page == "PO Detail":
    st.title("PO Detail")

    df = read_table(engine, "shm_POHeader")
    if df.empty:
        st.info("No PO Header data yet.")
        st.stop()

    po_list = df["shm_ponumber"].tolist()
    selected_po = st.selectbox("Select PO Number", po_list)

    header = df[df["shm_ponumber"] == selected_po].iloc[0].to_dict()
    st.subheader(f"Header: {selected_po}")
    st.json(header, expanded=False)

    st.subheader("Lines")
    lines = read_po_details_by_po(engine, selected_po)
    st.dataframe(lines, use_container_width=True, hide_index=True)

# ---------------------- PAGE: TRANSPORT BOOKING ----------------------
elif page == "Transport Booking":
    st.title("Transport Booking")

    headers = read_table(engine, "shm_POHeader")
    if headers.empty:
        st.info("No PO Header data yet.")
        st.stop()

    col1, col2 = st.columns([1.2, 2.0])
    with col1:
        po = st.selectbox("PO Number", headers["shm_ponumber"].tolist())
    with col2:
        st.caption("This updates booking fields in shm_POHeader (similar to Patch() in Power Apps).")

    transport = st.selectbox("Transport", ["Supplier", "Shipping", "SHM", "KEL", "บราโว่", "เอกอนันต์", "ว.ศรีประเสริฐ", "TDM", "โวลท์เวฟ"])
    trucktype = st.selectbox("Truck Type", ["4W", "4WJ", "6W", "10W", "18W", "106W"])
    delivery = st.date_input("Delivery Date", value=date.today())
    truckno = st.text_input("Truck No", value="")
    truckqty = st.number_input("Truck Qty", min_value=0.0, value=0.0, step=1.0)
    cost = st.number_input("Transport Cost", min_value=0.0, value=0.0, step=1.0)
    note = st.text_area("SCM Note", value="")

    if st.button("Save Booking", type="primary"):
        upsert_transport_booking(
            engine,
            po,
            {
                "shm_transportname": transport,
                "shm_trucktype": trucktype,
                "shm_slotbooking": 1,
                "shm_deliverydate": delivery.isoformat(),
                "shm_truckno": truckno.strip(),
                "shm_truckqty": float(truckqty),
                "shm_transportcost": float(cost),
                "shm_scmnote": note,
                "shm_recorddate": datetime.utcnow().isoformat(timespec="seconds"),
                "shm_recordby": "streamlit_user",
            },
        )
        st.success("✅ Booking saved.")
        st.rerun()

# ---------------------- PAGE: REPORTS & KPI ----------------------
elif page == "Reports & KPI":
    st.title("Reports & KPI")

    df = read_table(engine, "shm_POHeader")
    if df.empty:
        st.info("No PO data yet.")
        st.stop()

    total = len(df)
    done = int((df["shm_deliverystatus"] == "Done").sum())
    pending = int((df["shm_deliverystatus"] == "Pending").sum())
    slot = int((df["shm_slotbooking"] == 1).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Done", done)
    c3.metric("Pending", pending)
    c4.metric("Slot Booking", slot)

    st.subheader("By Division")
    div = df.groupby("shm_podivision")["shm_ponumber"].count().reset_index(name="count")
    st.bar_chart(div.set_index("shm_podivision")["count"])

    st.subheader("Recent Deliveries (Total Qty)")
    df2 = df.copy()
    df2["shm_deliverydate"] = pd.to_datetime(df2["shm_deliverydate"], errors="coerce")
    df2 = df2.sort_values("shm_deliverydate", ascending=False).head(50)
    st.line_chart(df2.set_index("shm_deliverydate")["shm_totalqty"])

# ---------------------- PAGE: MASTER DATA ----------------------
elif page == "Master Data":
    st.title("Master Data")

    tab1, tab2, tab3 = st.tabs(["Supplier", "DC", "Product"])

    def master_ui(table, key_col, label):
        st.subheader(label)
        df = read_table(engine, table)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()
        st.caption("Add / Update record")
        key = st.text_input(f"{key_col} *", key=f"{table}_key")
        name = st.text_input("Name", key=f"{table}_name")
        if st.button("Save", key=f"{table}_save"):
            if not key.strip():
                st.error("Key is required.")
            else:
                upsert_master_record(engine, table, key_col, key.strip(), name.strip())
                st.success("Saved.")
                st.rerun()

    with tab1:
        master_ui("shm_Supplier", "shm_suppliercode", "Supplier")
    with tab2:
        master_ui("shm_DC", "shm_dccode", "DC")
    with tab3:
        master_ui("shm_Product", "shm_shmitem", "Product")

# ---------------------- PAGE: SETTINGS ----------------------
else:
    st.title("Settings")

    st.subheader("Local Database")
    st.write("This starter uses local SQLite by default.")
    st.code("data/tms.db", language="text")

    st.subheader("Import from CSV")
    st.write("Export from Excel as CSV (UTF-8) then upload here to replace a table.")
    table = st.selectbox("Target table", ["shm_POHeader", "shm_PODetails", "shm_Supplier", "shm_DC", "shm_Product", "shm_User"])
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file is not None:
        df = pd.read_csv(file)
        st.write(df.head())
        if st.button("Import (Replace table)"):
            df.to_sql(table, con=engine, if_exists="replace", index=False)
            st.success("Imported.")
            st.rerun()
