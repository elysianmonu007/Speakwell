
import json
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
MODEL = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

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

FILLERS = [
    "um", "uh", "er", "ah", "like",
    "you know", "basically", "actually", "so", "i mean"
]

PROMPT = """You are an English speaking coach. Listen to the audio carefully.

Return ONLY valid JSON in exactly this shape:
{
  "transcript": "word-for-word transcript including filler words",
  "summary": "one sentence summary",
  "strengths": ["3 to 5 specific strengths"],
  "weaknesses": ["3 to 5 specific weaknesses"],
  "tips": ["4 to 6 practical improvement tips"]
}

Judge clarity, pronunciation, grammar, vocabulary, structure,
pace and confidence. Be honest but encouraging."""


def count_fillers(transcript):
    text = transcript.lower()
    counts = {}

    for filler in FILLERS:
        found = len(
            re.findall(r"\b" + re.escape(filler) + r"\b", text)
        )
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

    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if "." in file.filename else ""
    )

    if ext not in ALLOWED:
        return jsonify({
            "error": "Unsupported audio format."
        }), 400

    audio_bytes = file.read()

    mime = (
        file.mimetype
        if file.mimetype and file.mimetype.startswith("audio/")
        else ALLOWED[ext]
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime
                ),
                PROMPT
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        result = json.loads(response.text)

    except json.JSONDecodeError:
        return jsonify({
            "error": "AI response could not be read. Please try again."
        }), 502

    except Exception as e:
        detail = str(e)

        if API_KEY:
            detail = detail.replace(API_KEY, "***")

        print("Analysis error:", detail)

        return jsonify({
            "error": "Analysis failed: " + detail[:400]
        }), 500

    transcript = result.get("transcript", "")
    words = re.findall(r"\b[\w']+\b", transcript)

    stats = {
        "word_count": len(words),
        "fillers": count_fillers(transcript)
    }

    try:
        duration = float(request.form.get("duration", 0))
    except (ValueError, TypeError):
        duration = 0

    if duration > 0:
        stats["duration_seconds"] = round(duration)
        stats["words_per_minute"] = round(
            len(words) / (duration / 60)
        )

    result["stats"] = stats
    return jsonify(result)


@app.errorhandler(413)
def too_large(_):
    return jsonify({
        "error": "File is too large. Maximum size is 20 MB."
    }), 413


if __name__ == "__main__":
    print("Gemini API key loaded:", bool(API_KEY))
    app.run(debug=True)
