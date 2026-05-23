"""
Flask REST API for Credit Scoring Web App
Run: python app.py
Access: http://localhost:5000
"""

import os
import re
import sqlite3
import numpy as np
import joblib
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder="static")
app.secret_key = "creditscore_secret_session_key_19283746" # Secure signing key

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
DB_PATH = os.path.join(BASE_DIR, "users.db")


# ─── Database Initialization ──────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

init_db()

# ─── Load model ───────────────────────────────────────────────────────────────
print("Loading model...")
payload = joblib.load(MODEL_PATH)
model = payload["model"]
FEATURE_COLS = payload["feature_cols"]
feature_stats = payload["feature_stats"]
metrics = payload["metrics"]
print(f"Model loaded. AUC={metrics['auc']:.4f}, Gini={metrics['gini']:.4f}")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def prob_to_credit_score(pd_prob, base_score=600, pdo=50):
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(pd_prob / (1 - pd_prob + 1e-10))
    score = float(np.clip(offset, 300, 850))
    return round(score)


def get_risk_tier(score):
    if score >= 750:
        return {"tier": "Excellent", "color": "#22c55e", "bg": "#dcfce7", "rank": 1,
                "desc": "Very low risk. High-quality customer."}
    elif score >= 700:
        return {"tier": "Good", "color": "#16a34a", "bg": "#d1fae5", "rank": 2,
                "desc": "Low risk. Good customer profile."}
    elif score >= 630:
        return {"tier": "Fair", "color": "#d97706", "bg": "#fef3c7", "rank": 3,
                "desc": "Moderate risk. Monitor closely."}
    elif score >= 550:
        return {"tier": "Poor", "color": "#ea580c", "bg": "#ffedd5", "rank": 4,
                "desc": "High risk. Consider carefully."}
    else:
        return {"tier": "Very Poor", "color": "#dc2626", "bg": "#fee2e2", "rank": 5,
                "desc": "Very high risk. Not recommended for lending."}


def assess_factor(feature, value):
    """Return a qualitative assessment for each feature."""
    if feature == "RevolvingUtilizationOfUnsecuredLines":
        if value < 0.3:
            return "good", "Low utilization"
        elif value < 0.6:
            return "fair", "Moderate utilization"
        else:
            return "poor", "High utilization"
    elif feature == "age":
        if value >= 40:
            return "good", "Mature borrower"
        elif value >= 25:
            return "fair", "Young adult"
        else:
            return "poor", "Very young"
    elif feature in ("NumberOfTime30-59DaysPastDueNotWorse",
                     "NumberOfTime60-89DaysPastDueNotWorse",
                     "NumberOfTimes90DaysLate"):
        if value == 0:
            return "good", "No late payments"
        elif value <= 1:
            return "fair", "1 late payment"
        else:
            return "poor", f"{int(value)} late payments"
    elif feature == "DebtRatio":
        if value < 0.35:
            return "good", "Low debt ratio"
        elif value < 0.5:
            return "fair", "Moderate debt ratio"
        else:
            return "poor", "High debt ratio"
    elif feature == "MonthlyIncome":
        if value >= 5000:
            return "good", "Good income"
        elif value >= 2000:
            return "fair", "Moderate income"
        else:
            return "poor", "Low income"
    elif feature == "NumberOfOpenCreditLinesAndLoans":
        if 3 <= value <= 12:
            return "good", "Healthy credit mix"
        elif value <= 2:
            return "fair", "Thin credit file"
        else:
            return "fair", "Many credit lines"
    elif feature == "NumberRealEstateLoansOrLines":
        if value == 0:
            return "fair", "No real estate"
        elif value <= 2:
            return "good", "Stable real estate"
        else:
            return "poor", "Many property loans"
    elif feature == "NumberOfDependents":
        if value == 0:
            return "good", "No dependents"
        elif value <= 2:
            return "fair", f"{int(value)} dependents"
        else:
            return "poor", f"{int(value)} dependents"
    return "fair", "-"


# ─── Auth API Routes ──────────────────────────────────────────────────────────
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or not email or not password:
            return jsonify({"error": "Vui lòng nhập đầy đủ thông tin"}), 400

        # Validate username format
        if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", username):
            return jsonify({"error": "Tên đăng nhập không hợp lệ (3-20 ký tự, không chứa ký tự đặc biệt)"}), 400

        # Validate email format
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            return jsonify({"error": "Email không hợp lệ"}), 400

        if len(password) < 6:
            return jsonify({"error": "Mật khẩu phải chứa ít nhất 6 ký tự"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check existing username or email
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "Tên đăng nhập hoặc email đã tồn tại"}), 400

        # Hash password and insert
        pw_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, pw_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        # Auto login
        session["user_id"] = user_id
        session["username"] = username

        return jsonify({
            "success": True,
            "message": "Đăng ký tài khoản thành công!",
            "user": {"id": user_id, "username": username, "email": email}
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    try:
        data = request.get_json(force=True)
        username_or_email = data.get("username", "").strip()
        password = data.get("password", "")

        if not username_or_email or not password:
            return jsonify({"error": "Vui lòng nhập tên đăng nhập/email và mật khẩu"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username_or_email, username_or_email)
        )
        user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Tên đăng nhập hoặc mật khẩu không chính xác"}), 401

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return jsonify({
            "success": True,
            "message": "Đăng nhập thành công!",
            "user": {"id": user["id"], "username": user["username"], "email": user["email"]}
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return jsonify({"success": True, "message": "Đã đăng xuất thành công!"})


@app.route("/api/auth/user", methods=["GET"])
def auth_user():
    user_id = session.get("user_id")
    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return jsonify({
                "logged_in": True,
                "user": {"id": user["id"], "username": user["username"], "email": user["email"]}
            })
    return jsonify({"logged_in": False})


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(force=True)

        features = []
        for col in FEATURE_COLS:
            val = data.get(col)
            if val is None:
                val = feature_stats[col]["median"]
            features.append(float(val))

        X = np.array(features).reshape(1, -1)
        pd_prob = float(model.predict_proba(X)[0, 1])
        credit_score = prob_to_credit_score(pd_prob)
        risk = get_risk_tier(credit_score)

        labels = {
            "RevolvingUtilizationOfUnsecuredLines": "Credit Utilization",
            "age": "Age",
            "NumberOfTime30-59DaysPastDueNotWorse": "Late (30-59 days)",
            "DebtRatio": "Debt-to-Income Ratio",
            "MonthlyIncome": "Monthly Income",
            "NumberOfOpenCreditLinesAndLoans": "Open Credit Lines",
            "NumberOfTimes90DaysLate": "Late (90+ days)",
            "NumberRealEstateLoansOrLines": "Real Estate Loans",
            "NumberOfTime60-89DaysPastDueNotWorse": "Late (60-89 days)",
            "NumberOfDependents": "Dependents",
        }
        icons = {
            "RevolvingUtilizationOfUnsecuredLines": "credit_card",
            "age": "person",
            "NumberOfTime30-59DaysPastDueNotWorse": "warning",
            "DebtRatio": "account_balance",
            "MonthlyIncome": "payments",
            "NumberOfOpenCreditLinesAndLoans": "folder_open",
            "NumberOfTimes90DaysLate": "error",
            "NumberRealEstateLoansOrLines": "home",
            "NumberOfTime60-89DaysPastDueNotWorse": "report_problem",
            "NumberOfDependents": "family_restroom",
        }

        factors = []
        for col in FEATURE_COLS:
            val = float(data.get(col, feature_stats[col]["median"]))
            status, label_text = assess_factor(col, val)
            factors.append({
                "key": col,
                "label": labels.get(col, col),
                "icon": icons.get(col, "info"),
                "value": val,
                "status": status,
                "assessment": label_text,
            })

        recommendations = []
        if data.get("RevolvingUtilizationOfUnsecuredLines", 0) > 0.3:
            recommendations.append("Reduce your credit utilization below 30% to improve your score significantly.")
        if (data.get("NumberOfTime30-59DaysPastDueNotWorse", 0) > 0 or
                data.get("NumberOfTime60-89DaysPastDueNotWorse", 0) > 0 or
                data.get("NumberOfTimes90DaysLate", 0) > 0):
            recommendations.append("Pay all bills on time. Payment history is the most impactful factor.")
        if data.get("DebtRatio", 0) > 0.35:
            recommendations.append("Work on reducing your total debt relative to income.")
        if not recommendations:
            recommendations.append("Keep maintaining your excellent financial habits!")

        # --- Waterfall (SHAP) Calculation ---
        # 1. Calculate baseline score (all features at median)
        median_features = [feature_stats[col]["median"] for col in FEATURE_COLS]
        X_median = np.array(median_features).reshape(1, -1)
        pd_median = float(model.predict_proba(X_median)[0, 1])
        baseline_score = int(prob_to_credit_score(pd_median))

        # 2. Calculate contributions
        contributions = []
        sum_contribs = 0
        for col_idx, col in enumerate(FEATURE_COLS):
            test_features = list(median_features)
            val = data.get(col)
            if val is None:
                val = feature_stats[col]["median"]
            test_features[col_idx] = float(val)
            
            X_test = np.array(test_features).reshape(1, -1)
            pd_test = float(model.predict_proba(X_test)[0, 1])
            S_test = int(prob_to_credit_score(pd_test))
            contrib = S_test - baseline_score
            contributions.append({
                "key": col,
                "label": labels.get(col, col),
                "value": contrib
            })
            sum_contribs += contrib

        # 3. Calculate Interaction/Joint effect
        interaction = credit_score - baseline_score - sum_contribs

        waterfall_data = {
            "baseline": baseline_score,
            "final": credit_score,
            "contributions": contributions,
            "interaction": interaction
        }

        return jsonify({
            "credit_score": credit_score,
            "probability_of_default": round(pd_prob * 100, 2),
            "risk_tier": risk["tier"],
            "risk_color": risk["color"],
            "risk_bg": risk["bg"],
            "risk_desc": risk["desc"],
            "factors": factors,
            "recommendations": recommendations,
            "model_metrics": {"auc": round(metrics["auc"], 4), "gini": round(metrics["gini"], 4)},
            "waterfall": waterfall_data,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": "HistGradientBoostingClassifier"})


# ─── NLP Parser for Chat ──────────────────────────────────────────────────────
def parse_nl_to_features(text, context=None):
    """Extract credit scoring features from natural language text."""
    t = text.lower()
    extracted = {}

    def mask_match(m):
        nonlocal t
        if m:
            start, end = m.span()
            t = t[:start] + " " * (end - start) + t[end:]

    # Age
    for p in [
        r"\b(?:i(?:'m| am)?|age[d]?|am)\s+(\d{1,3})\s*(?:years?(?:\s*old)?)?",
        r"\b(\d{1,3})\s*(?:years?\s*old|yr\.?\s*old)",
        r"\bage[:\s]+(\d{1,3})\b",
    ]:
        m = re.search(p, t)
        if m:
            v = int(m.group(1))
            if 18 <= v <= 110:
                extracted["age"] = v
                mask_match(m)
                break

    # Monthly Income
    for p in [
        r"(?:earn|income|salary|make|get paid|receive)\s+\$?([\d,]+(?:\.\d+)?)\s*k?\s*(?:/\s*month|per\s+month|monthly|a\s+month)?",
        r"\$\s*([\d,]+(?:\.\d+)?)\s*k?\s*(?:a\s+month|per\s+month|monthly|/\s*month)",
        r"(?:monthly\s+income|income)[:\s]+\$?([\d,]+(?:\.\d+)?)\s*k?",
    ]:
        m = re.search(p, t)
        if m:
            raw = m.group(1).replace(",", "")
            v = float(raw)
            seg = t[m.start():m.end() + 2]
            if re.search(r"\bk\b", seg):
                v *= 1000
            if 0 < v < 1_000_000:
                extracted["MonthlyIncome"] = v
                mask_match(m)
                break

    # Credit Utilization
    for p in [
        r"(?:utiliz(?:ation|e[sd]?)|credit\s+usage|using|usage|util)\s+(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:utiliz|credit\s+usage|credit\s+used|credit\s+(?:card\s+)?utiliz|of\s+(?:my\s+)?(?:credit|limit)|util|usage)",
        r"utiliz(?:ation)?[:\s]+(\d+(?:\.\d+)?)\s*%?",
    ]:
        m = re.search(p, t)
        if m:
            v = float(m.group(1))
            if v > 1:
                v /= 100
            if 0 <= v <= 2:
                extracted["RevolvingUtilizationOfUnsecuredLines"] = round(v, 4)
                mask_match(m)
                break
    if "RevolvingUtilizationOfUnsecuredLines" not in extracted:
        m = re.search(r"(?:credit\s+(?:card\s+)?utiliz(?:ation)?|utiliz(?:ation)?)[\s:]+([0-1]?\.\d+)", t)
        if m:
            extracted["RevolvingUtilizationOfUnsecuredLines"] = float(m.group(1))
            mask_match(m)

    # Debt Ratio
    for p in [
        r"(?:debt(?:[\s\-/]*(?:to[\s\-/]?)?income)?\s*ratio|dti)(?:\s+(?:is|of|to\s+be|stands?\s+at))?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:debt|dti|of\s+income\s+(?:goes?\s+to\s+)?debt)",
        r"\bdti[:\s]+(\d+(?:\.\d+)?)\s*%?",
    ]:
        m = re.search(p, t)
        if m:
            v = float(m.group(1))
            if v > 1:
                v /= 100
            extracted["DebtRatio"] = round(v, 4)
            mask_match(m)
            break

    # Open Credit Lines
    for p in [
        r"(\d+)\s*(?:open\s+)?(?:credit\s+(?:lines?|accounts?|cards?)|loans?)\s*(?:open|active)?",
        r"(?:open|active|total)\s+(?:credit\s+)?(?:lines?|accounts?|loans?)[:\s]+(\d+)",
    ]:
        m = re.search(p, t)
        if m:
            v = int(m.group(1))
            if 0 <= v <= 60:
                extracted["NumberOfOpenCreditLinesAndLoans"] = v
                mask_match(m)
                break

    # Real Estate
    for p in [
        r"(\d+)\s*(?:real\s+estate|mortgage|property|home)\s*(?:loans?|lines?)?",
        r"(?:mortgage|real\s+estate)[s]?[:\s]+(\d+)",
        r"(\d+)\s*mortgages?",
    ]:
        m = re.search(p, t)
        if m:
            v = int(m.group(1))
            if 0 <= v <= 20:
                extracted["NumberRealEstateLoansOrLines"] = v
                mask_match(m)
                break

    # Dependents
    m_no_kids = re.search(r"(?:no|zero|0)\s*(?:kids?|children|dependents?)", t)
    if m_no_kids:
        extracted["NumberOfDependents"] = 0
        mask_match(m_no_kids)
    else:
        for p in [
            r"(\d+)\s*(?:dependents?|kids?|children|child)\b",
            r"(?:have|has|with)\s+(\d+)\s*(?:kids?|children|dependents?)\b",
        ]:
            m = re.search(p, t)
            if m:
                v = int(m.group(1))
                if 0 <= v <= 20:
                    extracted["NumberOfDependents"] = v
                    mask_match(m)
                    break

    # Never late shortcut
    m_never_late = re.search(r"\b(?:never\s+late|no\s+late\s+pay|always\s+on[\s\-]?time|never\s+miss(?:ed)?|0\s*(?:times?\s+)?late)\b", t)
    if m_never_late:
        extracted["NumberOfTime30-59DaysPastDueNotWorse"] = 0
        extracted["NumberOfTime60-89DaysPastDueNotWorse"] = 0
        extracted["NumberOfTimes90DaysLate"] = 0
        mask_match(m_never_late)

    # Specific late 30-59
    m = re.search(r"(\d+)\s*(?:times?\s+)?(?:late|past\s*due)\s*(?:30.59|30\s*to\s*59)\s*(?:days?)?", t)
    if m:
        extracted["NumberOfTime30-59DaysPastDueNotWorse"] = int(m.group(1))
        mask_match(m)

    # Specific late 60-89
    m = re.search(r"(\d+)\s*(?:times?\s+)?(?:late|past\s*due)\s*(?:60.89|60\s*to\s*89)\s*(?:days?)?", t)
    if m:
        extracted["NumberOfTime60-89DaysPastDueNotWorse"] = int(m.group(1))
        mask_match(m)

    # Specific late 90+
    m = re.search(r"(\d+)\s*(?:times?\s+)?(?:late|past\s*due)\s*(?:90\+?|90\s+(?:days?\s+)?or\s+more)", t)
    if m:
        extracted["NumberOfTimes90DaysLate"] = int(m.group(1))
        mask_match(m)

    # Generic late payments
    if "NumberOfTime30-59DaysPastDueNotWorse" not in extracted:
        m = re.search(r"(\d+)\s*(?:times?\s+)?(?:late\s*(?:pay(?:ments?)?)?|past\s*due)", t)
        if m:
            extracted["NumberOfTime30-59DaysPastDueNotWorse"] = int(m.group(1))
            extracted.setdefault("NumberOfTime60-89DaysPastDueNotWorse", 0)
            extracted.setdefault("NumberOfTimes90DaysLate", 0)
            mask_match(m)

    # Generic percentage fallback using current context
    if context is None:
        context = {}
    
    merged_so_far = {**context, **extracted}
    
    # If we still haven't found RevolvingUtilizationOfUnsecuredLines or DebtRatio
    # let's look for any standalone percentage or decimal in the text
    has_ru = "RevolvingUtilizationOfUnsecuredLines" in merged_so_far
    has_dr = "DebtRatio" in merged_so_far
    
    if not (has_ru and has_dr):
        # Find any percentage (e.g. "35%")
        m = re.search(r"\b(\d+(?:\.\d+)?)\s*%", t)
        if m:
            val = float(m.group(1)) / 100.0
            if not has_ru and has_dr:
                extracted["RevolvingUtilizationOfUnsecuredLines"] = val
            elif has_ru and not has_dr:
                extracted["DebtRatio"] = val
            else:
                extracted["RevolvingUtilizationOfUnsecuredLines"] = val
        else:
            # Look for a plain decimal like "0.35"
            m = re.search(r"\b(0\.\d+)\b", t)
            if m:
                val = float(m.group(1))
                if not has_ru and has_dr:
                    extracted["RevolvingUtilizationOfUnsecuredLines"] = val
                elif has_ru and not has_dr:
                    extracted["DebtRatio"] = val
                else:
                    extracted["RevolvingUtilizationOfUnsecuredLines"] = val
            else:
                # Or look for a standalone number like "35" if one of them is missing
                m = re.search(r"\b([1-9]\d)\b", t)
                if m:
                    val = float(m.group(1)) / 100.0
                    if not has_ru and has_dr:
                        extracted["RevolvingUtilizationOfUnsecuredLines"] = val
                    elif has_ru and not has_dr:
                        extracted["DebtRatio"] = val

    return extracted


def build_chat_reply(extracted, missing, prediction=None):
    LABELS = {
        "age": "your age",
        "MonthlyIncome": "your monthly income (e.g. $3,000)",
        "RevolvingUtilizationOfUnsecuredLines": "credit utilization rate (e.g. 30%)",
        "DebtRatio": "debt-to-income ratio (e.g. 40%)",
        "NumberOfOpenCreditLinesAndLoans": "number of open credit lines/loans",
        "NumberRealEstateLoansOrLines": "number of mortgage/real estate loans",
        "NumberOfDependents": "number of dependents (kids, family)",
        "NumberOfTime30-59DaysPastDueNotWorse": "times 30-59 days late on payments",
        "NumberOfTime60-89DaysPastDueNotWorse": "times 60-89 days late on payments",
        "NumberOfTimes90DaysLate": "times 90+ days late on payments",
    }

    if prediction:
        score = prediction["credit_score"]
        pd_pct = prediction["probability_of_default"]
        tier = prediction["risk_tier"]
        icons = {"Excellent": "🟢", "Good": "🟩", "Fair": "🟡", "Poor": "🟠", "Very Poor": "🔴"}
        icon = icons.get(tier, "⚪")

        parts = []
        if "age" in extracted:
            parts.append(f"age {int(extracted['age'])}")
        if "MonthlyIncome" in extracted:
            parts.append(f"income ${extracted['MonthlyIncome']:,.0f}/mo")
        if "RevolvingUtilizationOfUnsecuredLines" in extracted:
            parts.append(f"utilization {extracted['RevolvingUtilizationOfUnsecuredLines']*100:.0f}%")
        summary = ", ".join(parts) if parts else "your profile"

        reply = (
            f"📊 **Based on {summary}:**\n\n"
            f"**Credit Score: {score} / 850**\n"
            f"**Default Probability: {pd_pct}%**\n"
            f"**Risk Tier: {icon} {tier}**\n\n"
        )
        if score >= 750:
            reply += "✅ Excellent! You'd qualify for the best loan rates and terms."
        elif score >= 700:
            reply += "✅ Good profile. You should qualify for most loan products at competitive rates."
        elif score >= 630:
            reply += "⚠️ Fair profile. You may qualify but at higher interest rates."
        elif score >= 550:
            reply += "⚠️ Poor profile. High risk — focus on reducing late payments and debt."
        else:
            reply += "❌ Very poor profile. Prioritize paying off overdue balances."

        if missing:
            reply += f"\n\n💡 *I used defaults for: {', '.join(LABELS.get(f, f) for f in missing[:2])}.*"
        return reply

    ack_parts = []
    if "age" in extracted:
        ack_parts.append(f"age **{int(extracted['age'])}**")
    if "MonthlyIncome" in extracted:
        ack_parts.append(f"income **${extracted['MonthlyIncome']:,.0f}/month**")
    if "RevolvingUtilizationOfUnsecuredLines" in extracted:
        ack_parts.append(f"utilization **{extracted['RevolvingUtilizationOfUnsecuredLines']*100:.0f}%**")
    if "DebtRatio" in extracted:
        ack_parts.append(f"debt ratio **{extracted['DebtRatio']*100:.0f}%**")

    ack = ("Got it! I noted " + ", ".join(ack_parts) + ".\n\n") if ack_parts else ""
    if missing:
        need = "\n• ".join(LABELS.get(f, f) for f in missing[:3])
        return ack + f"To predict your credit score, I still need:\n• {need}"
    return ack + "Calculating your credit score..."


# ─── Chat Endpoint ────────────────────────────────────────────────────────────
REQUIRED_FIELDS = ["age", "RevolvingUtilizationOfUnsecuredLines", "DebtRatio"]
OPTIONAL_FIELDS = [
    "MonthlyIncome", "NumberOfTime30-59DaysPastDueNotWorse",
    "NumberOfTime60-89DaysPastDueNotWorse", "NumberOfTimes90DaysLate",
    "NumberOfOpenCreditLinesAndLoans", "NumberRealEstateLoansOrLines",
    "NumberOfDependents",
]


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
        message = body.get("message", "").strip()
        context = body.get("context", {})

        newly = parse_nl_to_features(message, context=context)
        merged = {**context, **newly}

        missing_required = [f for f in REQUIRED_FIELDS if f not in merged]

        if not missing_required:
            full_data = {col: float(merged.get(col, feature_stats[col]["median"]))
                         for col in FEATURE_COLS}
            X = np.array([full_data[col] for col in FEATURE_COLS]).reshape(1, -1)
            pd_prob = float(model.predict_proba(X)[0, 1])
            credit_score = prob_to_credit_score(pd_prob)
            risk = get_risk_tier(credit_score)
            missing_opt = [f for f in OPTIONAL_FIELDS if f not in merged]
            prediction = {
                "credit_score": credit_score,
                "probability_of_default": round(pd_prob * 100, 2),
                "risk_tier": risk["tier"],
                "risk_color": risk["color"],
                "risk_bg": risk["bg"],
            }
            reply = build_chat_reply(merged, missing_opt, prediction)
            return jsonify({"reply": reply, "context": merged, "prediction": prediction, "done": True})

        reply = build_chat_reply(merged, missing_required, prediction=None)
        return jsonify({"reply": reply, "context": merged, "prediction": None, "done": False})

    except Exception as e:
        return jsonify({"reply": f"Sorry, I hit an error: {str(e)}", "context": {}, "done": False}), 200



# ─── Batch Prediction Endpoints ───────────────────────────────────────────────

@app.route("/api/sample-template", methods=["GET"])
def sample_template():
    try:
        headers = [
            "RevolvingUtilizationOfUnsecuredLines",
            "age",
            "NumberOfTime30-59DaysPastDueNotWorse",
            "DebtRatio",
            "MonthlyIncome",
            "NumberOfOpenCreditLinesAndLoans",
            "NumberOfTimes90DaysLate",
            "NumberRealEstateLoansOrLines",
            "NumberOfTime60-89DaysPastDueNotWorse",
            "NumberOfDependents"
        ]
        rows = [
            [0.35, 45, 0, 0.25, 5500, 8, 0, 1, 0, 2],
            [0.02, 60, 0, 0.15, 9000, 12, 0, 2, 0, 0],
            [0.95, 28, 2, 0.65, 3000, 4, 1, 0, 1, 1]
        ]
        content = ",".join(headers) + "\n" + "\n".join(",".join(map(str, r)) for r in rows)
        return content, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=credit_scoring_template.csv'
        }
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/batch-predict", methods=["POST"])
def batch_predict():
    try:
        import pandas as pd
        import uuid
        import unicodedata

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext == '.csv':
            df_original = pd.read_csv(file)
        elif ext in ['.xls', '.xlsx']:
            df_original = pd.read_excel(file)
        else:
            return jsonify({"error": "Unsupported file format. Please upload a CSV or Excel file."}), 400

        if df_original.empty:
            return jsonify({"error": "Uploaded file is empty."}), 400

        norm_mapping = {
            "revolvingutilizationofunsecuredlines": "RevolvingUtilizationOfUnsecuredLines",
            "utilization": "RevolvingUtilizationOfUnsecuredLines",
            "creditutilization": "RevolvingUtilizationOfUnsecuredLines",
            "creditusage": "RevolvingUtilizationOfUnsecuredLines",
            "tilesudunghanmuc": "RevolvingUtilizationOfUnsecuredLines",
            "tilesudung": "RevolvingUtilizationOfUnsecuredLines",
            "util": "RevolvingUtilizationOfUnsecuredLines",
            "tileutilization": "RevolvingUtilizationOfUnsecuredLines",
            
            "age": "age",
            "tuoi": "age",
            
            "numberoftime3059dayspastduenotworse": "NumberOfTime30-59DaysPastDueNotWorse",
            "late3059": "NumberOfTime30-59DaysPastDueNotWorse",
            "pastdue3059": "NumberOfTime30-59DaysPastDueNotWorse",
            "trehan3059": "NumberOfTime30-59DaysPastDueNotWorse",
            "songaytrehan3059": "NumberOfTime30-59DaysPastDueNotWorse",
            
            "debtratio": "DebtRatio",
            "tieno": "DebtRatio",
            
            "monthlyincome": "MonthlyIncome",
            "income": "MonthlyIncome",
            "thunhap": "MonthlyIncome",
            
            "numberofopencreditlinesandloans": "NumberOfOpenCreditLinesAndLoans",
            "openlines": "NumberOfOpenCreditLinesAndLoans",
            "sokhoanvay": "NumberOfOpenCreditLinesAndLoans",
            "sohanmuctindung": "NumberOfOpenCreditLinesAndLoans",
            
            "numberoftimes90dayslate": "NumberOfTimes90DaysLate",
            "late90": "NumberOfTimes90DaysLate",
            "trehan90": "NumberOfTimes90DaysLate",
            
            "numberrealestateloansorlines": "NumberRealEstateLoansOrLines",
            "realestate": "NumberRealEstateLoansOrLines",
            "realestateloans": "NumberRealEstateLoansOrLines",
            "sobatdongsan": "NumberRealEstateLoansOrLines",
            
            "numberoftime6089dayspastduenotworse": "NumberOfTime60-89DaysPastDueNotWorse",
            "late6089": "NumberOfTime60-89DaysPastDueNotWorse",
            "trehan6089": "NumberOfTime60-89DaysPastDueNotWorse",
            
            "numberofdependents": "NumberOfDependents",
            "dependents": "NumberOfDependents",
            "songuoiphuthuoc": "NumberOfDependents"
        }

        def normalize_header(name):
            s = str(name).strip().lower()
            s = re.sub(r'[\s_\-]+', '', s)
            s_no_accent = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            return s, s_no_accent

        df_features = pd.DataFrame(index=df_original.index)
        for col in FEATURE_COLS:
            found = False
            for user_col in df_original.columns:
                s, s_no_accent = normalize_header(user_col)
                if s in norm_mapping and norm_mapping[s] == col:
                    df_features[col] = df_original[user_col]
                    found = True
                    break
                elif s_no_accent in norm_mapping and norm_mapping[s_no_accent] == col:
                    df_features[col] = df_original[user_col]
                    found = True
                    break
            if not found:
                df_features[col] = feature_stats[col]["median"]
            
            df_features[col] = pd.to_numeric(df_features[col], errors='coerce').fillna(feature_stats[col]["median"])

        # Predict
        probs = model.predict_proba(df_features[FEATURE_COLS])[:, 1]
        scores = [prob_to_credit_score(p) for p in probs]
        
        # Add predictions to original data
        df_scored = df_original.copy()
        df_scored["Predicted_Credit_Score"] = scores
        df_scored["Predicted_Default_Probability_%"] = np.round(probs * 100, 2)
        
        risk_tiers = [get_risk_tier(s) for s in scores]
        df_scored["Risk_Tier"] = [t["tier"] for t in risk_tiers]

        # Save to static exports directory
        export_filename = f"scored_{uuid.uuid4().hex[:8]}.csv"
        export_dir = os.path.join(FRONTEND_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_path = os.path.join(export_dir, export_filename)
        df_scored.to_csv(export_path, index=False)

        total_count = len(df_scored)
        avg_score = int(round(np.mean(scores))) if total_count > 0 else 0
        
        tier_counts = {"Excellent": 0, "Good": 0, "Fair": 0, "Poor": 0, "Very Poor": 0}
        for t in risk_tiers:
            tier_counts[t["tier"]] = tier_counts.get(t["tier"], 0) + 1
        
        tier_distribution = {
            k: round((v / total_count) * 100, 1) if total_count > 0 else 0 
            for k, v in tier_counts.items()
        }

        # First 50 rows preview
        preview_data = []
        for i in range(min(50, total_count)):
            preview_data.append({
                "index": i + 1,
                "age": int(df_features.loc[i, "age"]),
                "income": float(df_features.loc[i, "MonthlyIncome"]),
                "utilization": float(df_features.loc[i, "RevolvingUtilizationOfUnsecuredLines"]),
                "debt_ratio": float(df_features.loc[i, "DebtRatio"]),
                "score": int(df_scored.loc[i, "Predicted_Credit_Score"]),
                "pd": float(df_scored.loc[i, "Predicted_Default_Probability_%"]),
                "tier": df_scored.loc[i, "Risk_Tier"],
                "color": risk_tiers[i]["color"]
            })

        return jsonify({
            "success": True,
            "total_records": total_count,
            "average_score": avg_score,
            "tier_distribution": tier_distribution,
            "preview": preview_data,
            "download_url": f"/exports/{export_filename}"
        })

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



# ─── What-if / Roadmap Endpoint ───────────────────────────────────────────────
@app.route("/api/whatif", methods=["POST"])
def whatif():
    try:
        data = request.get_json(force=True)
        features = []
        for col in FEATURE_COLS:
            val = data.get(col)
            if val is None:
                val = feature_stats[col]["median"]
            features.append(float(val))

        X = np.array(features).reshape(1, -1)
        pd_prob = float(model.predict_proba(X)[0, 1])
        credit_score = prob_to_credit_score(pd_prob)
        risk = get_risk_tier(credit_score)

        return jsonify({
            "credit_score": credit_score,
            "probability_of_default": round(pd_prob * 100, 2),
            "risk_tier": risk["tier"],
            "risk_color": risk["color"],
            "risk_bg": risk["bg"],
            "risk_desc": risk["desc"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Compare Profiles Endpoint ────────────────────────────────────────────────
@app.route("/api/compare", methods=["POST"])
def compare():
    try:
        body = request.get_json(force=True)
        profiles = body.get("profiles", [])
        if not profiles:
            return jsonify({"error": "No profiles provided"}), 400

        results = []
        for prof in profiles:
            name = prof.get("_name", "Profile")
            features = []
            for col in FEATURE_COLS:
                val = prof.get(col)
                if val is None:
                    val = feature_stats[col]["median"]
                features.append(float(val))

            X = np.array(features).reshape(1, -1)
            pd_prob = float(model.predict_proba(X)[0, 1])
            credit_score = prob_to_credit_score(pd_prob)
            risk = get_risk_tier(credit_score)

            labels = {
                "RevolvingUtilizationOfUnsecuredLines": "Credit Utilization",
                "age": "Age",
                "NumberOfTime30-59DaysPastDueNotWorse": "Late (30-59 days)",
                "DebtRatio": "Debt-to-Income Ratio",
                "MonthlyIncome": "Monthly Income",
                "NumberOfOpenCreditLinesAndLoans": "Open Credit Lines",
                "NumberOfTimes90DaysLate": "Late (90+ days)",
                "NumberRealEstateLoansOrLines": "Real Estate Loans",
                "NumberOfTime60-89DaysPastDueNotWorse": "Late (60-89 days)",
                "NumberOfDependents": "Dependents",
            }
            factors = []
            for col in FEATURE_COLS:
                val = float(prof.get(col, feature_stats[col]["median"]))
                status, assessment = assess_factor(col, val)
                factors.append({
                    "key": col,
                    "label": labels.get(col, col),
                    "value": val,
                    "status": status,
                    "assessment": assessment,
                })

            results.append({
                "name": name,
                "credit_score": credit_score,
                "probability_of_default": round(pd_prob * 100, 2),
                "risk_tier": risk["tier"],
                "risk_color": risk["color"],
                "risk_bg": risk["bg"],
                "factors": factors,
            })

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting Credit Scoring API...")
    print("Open http://localhost:5000 in your browser")
    app.run(host="0.0.0.0", port=5000, debug=False)
