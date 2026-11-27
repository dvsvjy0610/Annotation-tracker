import io
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "dev-key"
DB = DATABASE_URL = os.environ.get("postgresql://annotationtracker_user:OOc9tMYzFujjOq55RT9vbQkfhPGJFDwh@dpg-dc4ope5g1s2s73f91rhg-a.ohio-postgres.render.com/annotationtracker")


def query(sql, params=(), fetch=True):
    """Small helper: run SQL and return rows as dicts."""
    with psycopg2.connect(**DB) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if fetch else None


@app.route("/")
def index():
    status = request.args.get("status", "")
    label = request.args.get("label", "")
    # JOIN across 3 tables + optional filters (parameterized -> safe from SQL injection)
    sql = """SELECT a.id, c.filename, c.duration_sec, a.label, a.transcript,
                    a.status, n.name AS annotator
             FROM annotations a
             JOIN clips c      ON c.id = a.clip_id
             JOIN annotators n ON n.id = a.annotator_id
             WHERE (%s = '' OR a.status = %s) AND (%s = '' OR a.label = %s)
             ORDER BY a.created_at DESC"""
    rows = query(sql, (status, status, label, label))
    clips = query("SELECT id, filename FROM clips ORDER BY filename")
    people = query("SELECT id, name FROM annotators")
    return render_template("index.html", rows=rows, clips=clips, people=people,
                           status=status, label=label)


@app.route("/add", methods=["POST"])
def add():
    f = request.form
    query("INSERT INTO annotations(clip_id, annotator_id, label, transcript) VALUES (%s,%s,%s,%s)",
          (f["clip_id"], f["annotator_id"], f["label"], f["transcript"].strip()), fetch=False)
    return redirect(url_for("index"))


@app.route("/review/<int:ann_id>", methods=["POST"])
def review(ann_id):
    query("UPDATE annotations SET status='reviewed' WHERE id=%s", (ann_id,), fetch=False)
    return redirect(url_for("index"))


@app.route("/import", methods=["POST"])
def import_csv():
    """Upload a CSV of clips (filename,duration_sec,language) and clean it with Pandas."""
    df = pd.read_csv(io.StringIO(request.files["file"].read().decode("utf-8")))
    before = len(df)
    df["filename"] = df["filename"].astype(str).str.strip()
    df["language"] = df["language"].fillna("unknown").str.strip().str.lower()
    df["duration_sec"] = pd.to_numeric(df["duration_sec"], errors="coerce")
    df = df.dropna(subset=["filename", "duration_sec"])   # remove missing values
    df = df[df["duration_sec"] > 0]                       # remove invalid durations
    df = df.drop_duplicates(subset="filename")            # remove duplicates
    for r in df.itertuples():
        query("""INSERT INTO clips(filename, duration_sec, language) VALUES (%s,%s,%s)
                 ON CONFLICT (filename) DO NOTHING""",
              (r.filename, float(r.duration_sec), r.language), fetch=False)
    flash(f"Imported {len(df)} clean rows (dropped {before - len(df)} bad rows).")
    return redirect(url_for("index"))


@app.route("/stats")
def stats():
    """Simple EDA with Pandas + NumPy."""
    rows = query("""SELECT a.label, a.status, c.duration_sec, n.name AS annotator
                    FROM annotations a JOIN clips c ON c.id = a.clip_id
                    JOIN annotators n ON n.id = a.annotator_id""")
    if not rows:
        return render_template("stats.html", empty=True)
    df = pd.DataFrame(rows)
    df["duration_sec"] = df["duration_sec"].astype(float)
    d = df["duration_sec"].to_numpy()
    summary = {"total": len(df),
               "mean": round(float(np.mean(d)), 2),
               "median": round(float(np.median(d)), 2),
               "std": round(float(np.std(d)), 2),
               "pct_reviewed": round(float((df["status"] == "reviewed").mean() * 100), 1)}
    by_label = df.groupby("label").size().to_dict()
    by_person = df.groupby("annotator")["duration_sec"].sum().round(1).to_dict()
    return render_template("stats.html", empty=False, s=summary,
                           by_label=by_label, by_person=by_person)


if __name__ == "__main__":
    app.run()
