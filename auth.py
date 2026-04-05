# =========================
# auth.py
# =========================

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_LOGIN_PATH = "/siteman"
REQUEST_TIMEOUT = 5
USERNAME_FIELD_CANDIDATES = (
    "username",
    "user",
    "email",
    "login",
    "nama",
    "nik",
)
PASSWORD_FIELD_CANDIDATES = (
    "password",
    "pass",
    "passwd",
    "kata_sandi",
)
CSRF_FIELD_KEYWORDS = (
    "csrf",
    "token",
    "_token",
    "authenticity",
)
SUCCESS_MARKERS = (
    "logout",
    "log out",
    "keluar",
    "dashboard",
    "administrator",
    "pengaturan",
    "manajemen",
)
FAILURE_MARKERS = (
    "password salah",
    "login gagal",
    "gagal login",
    "invalid",
    "wrong password",
    "username atau password",
)


def create_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "OpenSID-Bug-Scanner/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def login_opensid(base_url, username, password, session=None, login_path=DEFAULT_LOGIN_PATH):
    active_session = session or create_session()
    login_url = _build_login_url(base_url, login_path)
    result = {
        "success": False,
        "session": active_session,
        "login_url": login_url,
        "final_url": None,
        "username_field": None,
        "password_field": None,
        "csrf_field": None,
        "message": None,
    }

    try:
        initial_response = active_session.get(
            login_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        result["message"] = f"Failed to load login page: {exc}"
        return result

    form = _select_login_form(initial_response.text)
    if not form:
        result["message"] = "Unable to identify OpenSID login form"
        result["final_url"] = initial_response.url
        return result

    username_field = _detect_username_field(form)
    password_field = _detect_password_field(form)
    if not username_field or not password_field:
        result["message"] = "Unable to detect username/password fields"
        result["final_url"] = initial_response.url
        return result

    action_url = _resolve_form_action(form, initial_response.url)
    method = (form.get("method") or "post").strip().lower()
    form_payload = _build_form_payload(form)
    form_payload[username_field] = username
    form_payload[password_field] = password

    result["username_field"] = username_field
    result["password_field"] = password_field
    result["csrf_field"] = _detect_csrf_field(form)

    try:
        submit_response = _submit_login_form(
            active_session,
            action_url,
            method,
            form_payload,
        )
    except requests.RequestException as exc:
        result["message"] = f"Login request failed: {exc}"
        return result

    result["final_url"] = submit_response.url

    validation = _validate_login(
        active_session,
        login_url,
        submit_response,
        username_field,
        password_field,
    )
    result["success"] = validation["success"]
    result["message"] = validation["message"]
    if validation["final_url"]:
        result["final_url"] = validation["final_url"]

    return result


def _build_login_url(base_url, login_path):
    normalized_base = base_url.strip()
    if "://" not in normalized_base:
        normalized_base = "http://" + normalized_base
    return urljoin(normalized_base.rstrip("/") + "/", login_path.lstrip("/"))


def _select_login_form(html):
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    if not forms:
        return None

    best_form = None
    best_score = -1
    for form in forms:
        score = 0
        if _detect_password_field(form):
            score += 3
        if _detect_username_field(form):
            score += 2
        form_text = form.get_text(" ", strip=True).lower()
        if "login" in form_text or "masuk" in form_text:
            score += 1
        if score > best_score:
            best_score = score
            best_form = form

    return best_form if best_score > 0 else None


def _detect_username_field(form):
    candidates = []
    for field in form.find_all("input"):
        input_type = (field.get("type") or "text").strip().lower()
        name = (field.get("name") or "").strip()
        if not name:
            continue

        if input_type in {"text", "email", "tel", "number"}:
            candidates.append(field)
        elif input_type not in {"hidden", "password", "submit", "button", "checkbox", "radio"}:
            candidates.append(field)

    for field in candidates:
        if _field_matches(field, USERNAME_FIELD_CANDIDATES):
            return field.get("name")

    return candidates[0].get("name") if candidates else None


def _detect_password_field(form):
    for field in form.find_all("input"):
        input_type = (field.get("type") or "").strip().lower()
        if input_type == "password" and field.get("name"):
            return field.get("name")

    for field in form.find_all("input"):
        if _field_matches(field, PASSWORD_FIELD_CANDIDATES):
            name = field.get("name")
            if name:
                return name

    return None


def _detect_csrf_field(form):
    for field in form.find_all("input", {"type": "hidden"}):
        if _field_matches(field, CSRF_FIELD_KEYWORDS):
            return field.get("name")
    return None


def _field_matches(field, keywords):
    name = (field.get("name") or "").lower()
    field_id = (field.get("id") or "").lower()
    placeholder = (field.get("placeholder") or "").lower()
    autocomplete = (field.get("autocomplete") or "").lower()
    values = (name, field_id, placeholder, autocomplete)
    return any(keyword in value for keyword in keywords for value in values)


def _resolve_form_action(form, page_url):
    action = form.get("action") or page_url
    return urljoin(page_url, action)


def _build_form_payload(form):
    payload = {}
    for field in form.find_all(["input", "textarea", "select"]):
        name = field.get("name")
        if not name:
            continue

        field_type = (field.get("type") or "").strip().lower()
        if field_type in {"submit", "button", "image", "file", "reset"}:
            continue

        value = field.get("value", "")
        if field.name == "textarea":
            value = field.text or value
        elif field.name == "select":
            selected = field.find("option", selected=True)
            if selected:
                value = selected.get("value", selected.text)
            else:
                first_option = field.find("option")
                if first_option:
                    value = first_option.get("value", first_option.text)

        payload[name] = value

    return payload


def _submit_login_form(session, action_url, method, payload):
    if method == "get":
        return session.get(
            action_url,
            params=payload,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

    return session.post(
        action_url,
        data=payload,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )


def _validate_login(session, login_url, submit_response, username_field, password_field):
    response_text = submit_response.text.lower()
    current_url = submit_response.url

    if any(marker in response_text for marker in FAILURE_MARKERS):
        return {
            "success": False,
            "message": "Login failed based on server response",
            "final_url": current_url,
        }

    if _looks_authenticated(response_text, current_url):
        return {
            "success": True,
            "message": "Authenticated session established",
            "final_url": current_url,
        }

    try:
        verification_response = session.get(
            login_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return {
            "success": False,
            "message": f"Login validation failed: {exc}",
            "final_url": current_url,
        }

    verification_text = verification_response.text.lower()
    verification_url = verification_response.url
    if _looks_authenticated(verification_text, verification_url):
        return {
            "success": True,
            "message": "Authenticated session verified",
            "final_url": verification_url,
        }

    if _contains_login_form(verification_response.text, username_field, password_field):
        return {
            "success": False,
            "message": "Login form still present after authentication attempt",
            "final_url": verification_url,
        }

    if session.cookies:
        return {
            "success": True,
            "message": "Session cookies established; login likely succeeded",
            "final_url": verification_url,
        }

    return {
        "success": False,
        "message": "Unable to confirm authenticated OpenSID session",
        "final_url": verification_url,
    }


def _looks_authenticated(response_text, current_url):
    if any(marker in response_text for marker in SUCCESS_MARKERS):
        return True

    lowered_url = (current_url or "").lower()
    return "/siteman" in lowered_url and "login" not in response_text


def _contains_login_form(html, username_field, password_field):
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.find_all("form"):
        names = {
            (field.get("name") or "").strip()
            for field in form.find_all("input")
            if field.get("name")
        }
        if username_field in names and password_field in names:
            return True
    return False
