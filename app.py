import json
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

# Load .env from the same folder as this file, wherever you run Python from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
MODEL = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()

print("-" * 50)
print("Gemini key loaded:", bool(API_KEY), "| length:", len(API_KEY))
print("Model:", MODEL)
if not API_KEY or API_KEY == "paste_your_gemini_key_here":
    print("WARNING: no real key found. Check that .env is next to app.py and has GEMINI_API_KEY=...")
print("-" * 50)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload limit

client = genai.Client(api_key=API_KEY)

ALLOWED = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
}

FILLERS = ["um", "uh", "er", "ah", "like", "you know", "basically", "actually", "so", "i mean"]

PROMPT = """You are an English speaking coach. Listen to the audio carefully.

Return ONLY valid JSON (no markdown, no backticks) in exactly this shape:
{
  "transcript": "word-for-word transcript of what was said, including filler words",
  "summary": "one sentence on what the speaker talked about",
  "strengths": ["3 to 5 specific strong points, each referring to something in the audio"],
  "weaknesses": ["3 to 5 specific weak points, each referring to something in the audio"],
  "tips": ["4 to 6 practical, actionable tips to improve; include a short example when useful"]
}

Judge clarity, pronunciation, grammar, vocabulary, structure (opening, main points, conclusion),
pace and confidence. Be honest but encouraging. If the audio has no speech, return an empty
transcript and say so in the summary."""


def count_fillers(transcript):
    """Count common filler words in the transcript."""
    text = transcript.lower()
    counts = {}
    for filler in FILLERS:
        found = len(re.findall(r"\b" + re.escape(filler) + r"\b", text))
        if found:
            counts[filler] = found
    return counts


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    file = request.files.get("audio")
    if file is None or file.filename == "":
        return jsonify({"error": "Please choose an audio file."}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        return jsonify({"error": "Unsupported format. Use mp3, wav, m4a, aac, ogg, flac or webm."}), 400

    audio_bytes = file.read()
    mime = file.mimetype if file.mimetype.startswith("audio/") else ALLOWED[ext]

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime), PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)
    except json.JSONDecodeError:
        return jsonify({"error": "The AI reply could not be read as JSON. Please try again."}), 502
    except Exception as e:
        # Show the real reason (with the key removed) in the terminal and on the page
        detail = str(e)
        if API_KEY:
            detail = detail.replace(API_KEY, "***")
        print("Analysis error:", detail)
        return jsonify({"error": "Analysis failed: " + detail[:400]}), 500

    transcript = result.get("transcript", "")
    words = re.findall(r"\b[\w']+\b", transcript)

    stats = {"word_count": len(words), "fillers": count_fillers(transcript)}

    # The browser sends the audio length in seconds, so we can work out speaking pace.
    try:
        duration = float(request.form.get("duration", 0))
    except ValueError:
        duration = 0
    if duration > 0:
        stats["duration_seconds"] = round(duration)
        stats["words_per_minute"] = round(len(words) / (duration / 60))

    result["stats"] = stats
    return jsonify(result)


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File is too large. Maximum size is 20 MB."}), 413


if __name__ == "__main__":
    app.run(debug=True)