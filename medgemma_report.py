import base64
import datetime
import os
import re
import requests

LOG_PATH = os.path.join(os.path.expanduser("~"), "screenshots", "medgemma_log.txt")


def _write_log(clinical_text, image_paths, response_text):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{'='*60}\n")
        f.write(f"Timestamp: {timestamp}\n\n")
        f.write(f"Clinical text sent:\n{clinical_text}\n\n")
        f.write("Images sent:\n")
        for p in image_paths:
            f.write(f"  {p}\n")
        f.write(f"\nResponse:\n{response_text}\n\n")

from capture_workflow import run_capture_workflow

ENDPOINTS = {
    "medgemma-4b-it":  "https://mkd1z0lc69kz3hzn.us-east4.gcp.endpoints.huggingface.cloud/v1/chat/completions",
    "medgemma-27b-it": "https://s9ntdz93bp05d8a9.us-east-2.aws.endpoints.huggingface.cloud/v1/chat/completions",
    "maira-2":         "https://ezbevwqqugvzj3tv.us-east-1.aws.endpoints.huggingface.cloud/v1/chat/completions",
}
DEFAULT_MODEL = "medgemma-4b-it"
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def _load_hf_token():
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("HF_TOKEN not found in .env")


def format_age(age_raw):
    m = re.match(r'^(\d+)([DWMY])$', age_raw, re.IGNORECASE)
    if not m:
        return age_raw
    num = int(m.group(1))
    unit = m.group(2).upper()
    unit_names = {"Y": "years", "M": "months", "W": "weeks", "D": "days"}
    return f"{num} {unit_names.get(unit, unit)} old"


def _is_mostly_white(path, threshold=220, white_fraction=0.75):
    from PIL import Image as _Image
    img = _Image.open(path).convert("L")
    pixels = img.get_flattened_data()
    white = sum(1 for p in pixels if p > threshold)
    return white / len(pixels) > white_fraction


def _check_endpoint(hf_token, url, model):
    """Returns True if the endpoint is healthy, False otherwise."""
    import io as _io
    from PIL import Image as _PILImage
    img = _PILImage.new("RGB", (32, 32), color="gray")
    buf = _io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
    model_id = "microsoft/maira-2" if model == "maira-2" else f"google/{model}"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": "test"},
        ]}],
        "max_tokens": 5,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.ok:
            return True
        print(f"Endpoint check failed: {r.status_code} {r.text[:200]}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Endpoint check failed: {e}")
        return False


def run_medgemma_report(title=None, model=None):
    model = model or DEFAULT_MODEL
    if model not in ENDPOINTS:
        print(f"Unknown model '{model}'. Choose from: {', '.join(ENDPOINTS)}")
        return None
    url = ENDPOINTS[model]
    hf_token = _load_hf_token()
    print(f"Checking MedGemma endpoint ({model})...")
    if not _check_endpoint(hf_token, url, model):
        print("MedGemma endpoint is unavailable. Please check the HF dashboard.")
        return None
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    xray_paths, clinical_text, sex, age_raw = run_capture_workflow()

    if sex or age_raw:
        parts = []
        if sex:
            parts.append("Male" if sex == "M" else "Female")
        if age_raw:
            parts.append(format_age(age_raw))
        demo_str = ", ".join(parts)
        print(f"Demographics: {demo_str}")
        clinical_text = demo_str + ". " + (clinical_text or "")
    else:
        print("Demographics: not found")

    clinical_file = os.path.join(os.path.expanduser("~"), "screenshots", "clinicalInformation.txt")
    if os.path.exists(clinical_file):
        file_text = open(clinical_file, encoding="utf-8").read().strip()
        if file_text and file_text not in (clinical_text or ""):
            clinical_text = (clinical_text or "") + "\n" + file_text
            print(f"Clinical info from file: {file_text}")

    if not clinical_text or not clinical_text.strip():
        print("No clinical information found")
        return

    if not xray_paths:
        print("No xray images found")
        return

    filtered_paths = []
    for path in xray_paths:
        if "clario_clinical_info" in os.path.basename(path):
            print(f"Skipping {os.path.basename(path)} (clinical info image)")
        elif _is_mostly_white(path):
            request_path = os.path.join(screenshots_dir, "request.png")
            os.replace(path, request_path)
            print(f"{os.path.basename(path)} is mostly white — renamed to request.png")
        else:
            filtered_paths.append(path)
    xray_paths = filtered_paths

    if not xray_paths:
        print("No xray images remain after filtering")
        return

    print(f"\nSending {len(xray_paths)} image(s) to MedGemma...\n")

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }

    from PIL import Image as _PILImage
    import io as _io

    content = []
    for path in xray_paths:
        img = _PILImage.open(path)
        img.thumbnail((768, 768))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    title_line = f"Study: {title}\n" if title else ""
    prompt = (
        f"{title_line}{clinical_text}\n\n"
        "Reply only with a brief list of key findings "
        "without any interpretation of the findings.  "
        "If you are not confident in your answer, leave it out."
    )
    content.append({"type": "text", "text": prompt})

    model_id = "microsoft/maira-2" if model == "maira-2" else f"google/{model}"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": content}],
    }

    import time as _time
    for attempt in range(1, 4):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            break
        except requests.exceptions.ConnectionError as e:
            if attempt < 3:
                print(f"Connection error (attempt {attempt}/3), retrying in 15s... {e}")
                _time.sleep(15)
            else:
                response_text = f"Error: connection failed after 3 attempts — {e}"
                print(response_text)
                _write_log(prompt, xray_paths, response_text)
                return response_text

    if response.ok:
        response_text = response.json()["choices"][0]["message"]["content"]
        print(response_text)
    else:
        response_text = f"Error {response.status_code}: {response.text}"
        print(response_text)

    _write_log(prompt, xray_paths, response_text)
    print(f"\nLogged to {LOG_PATH}")
    return response_text


if __name__ == "__main__":
    run_medgemma_report()
