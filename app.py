
"""
CodeCraftHub - Course Tracking REST API

A beginner-friendly Flask application that provides CRUD operations
for courses and stores the data in courses.json.
"""

from datetime import datetime
from pathlib import Path
import json
import re

from flask import Flask, jsonify, request

app = Flask(__name__)

# Store courses.json in the same folder as app.py.
DATA_FILE = Path(__file__).parent / "courses.json"

# Only these status values are allowed.
ALLOWED_STATUSES = {"Not Started", "In Progress", "Completed"}


class StorageError(Exception):
    """Raised when the course data file cannot be read or written."""


def create_data_file_if_needed():
    """Create an empty JSON list if courses.json does not exist."""
    if not DATA_FILE.exists():
        try:
            with DATA_FILE.open("w", encoding="utf-8") as file:
                json.dump([], file, indent=2)
        except OSError as error:
            raise StorageError(
                f"Could not create courses.json: {error}"
            ) from error


def load_courses():
    """Load and return all courses from the JSON file."""
    create_data_file_if_needed()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            courses = json.load(file)

        if not isinstance(courses, list):
            raise StorageError("courses.json must contain a JSON list.")

        return courses

    except json.JSONDecodeError as error:
        raise StorageError(
            f"courses.json contains invalid JSON: {error}"
        ) from error
    except OSError as error:
        raise StorageError(
            f"Could not read courses.json: {error}"
        ) from error


def save_courses(courses):
    """Save the complete course list to the JSON file."""
    try:
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(courses, file, indent=2)
            file.write("\n")
    except OSError as error:
        raise StorageError(
            f"Could not write to courses.json: {error}"
        ) from error


def get_next_course_id(courses):
    """Return the next integer ID, starting at 1."""
    integer_ids = [
        course["id"]
        for course in courses
        if isinstance(course.get("id"), int)
        and not isinstance(course.get("id"), bool)
    ]
    return max(integer_ids, default=0) + 1


def is_valid_date(date_value):
    """Check that a date is real and uses YYYY-MM-DD format."""
    if not isinstance(date_value, str):
        return False

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        return False

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        return parsed_date.strftime("%Y-%m-%d") == date_value
    except ValueError:
        return False


def validate_course_data(data):
    """Return an error message if required course fields are invalid."""
    if not isinstance(data, dict):
        return "Request body must contain a JSON object."

    required_fields = ["name", "description", "target_date", "status"]
    missing_fields = [
        field for field in required_fields if field not in data
    ]

    if missing_fields:
        return "Missing required field(s): " + ", ".join(missing_fields)

    if not isinstance(data["name"], str) or not data["name"].strip():
        return "name is required and must not be empty."

    if (
        not isinstance(data["description"], str)
        or not data["description"].strip()
    ):
        return "description is required and must not be empty."

    if not is_valid_date(data["target_date"]):
        return "target_date must use the format YYYY-MM-DD."

    if (
        not isinstance(data["status"], str)
        or data["status"] not in ALLOWED_STATUSES
    ):
        return (
            "Invalid status. Status must be one of: "
            "'Not Started', 'In Progress', or 'Completed'."
        )

    return None


def get_json_request_body():
    """Return the JSON request data and an error, if any."""
    if not request.is_json:
        return None, "Request must have Content-Type: application/json."

    data = request.get_json(silent=True)

    if data is None:
        return None, "Request body must contain valid JSON."

    return data, None


# POST: Create a new course.
@app.route("/api/courses", methods=["POST"])
def create_course():
    data, error = get_json_request_body()

    if error:
        return jsonify({"error": error}), 400

    validation_error = validate_course_data(data)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        courses = load_courses()

        new_course = {
            "id": get_next_course_id(courses),
            "name": data["name"].strip(),
            "description": data["description"].strip(),
            "target_date": data["target_date"],
            "status": data["status"],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        courses.append(new_course)
        save_courses(courses)

        return jsonify(new_course), 201

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# GET: Retrieve all courses.
@app.route("/api/courses", methods=["GET"])
def get_all_courses():
    try:
        return jsonify(load_courses()), 200
    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# GET: Retrieve one course by ID.
@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    try:
        courses = load_courses()

        for course in courses:
            if course.get("id") == course_id:
                return jsonify(course), 200

        return jsonify({
            "error": f"Course with id {course_id} was not found."
        }), 404

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# PUT: Replace an existing course.
@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    data, error = get_json_request_body()

    if error:
        return jsonify({"error": error}), 400

    validation_error = validate_course_data(data)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        courses = load_courses()

        for index, course in enumerate(courses):
            if course.get("id") == course_id:
                updated_course = {
                    "id": course_id,
                    "name": data["name"].strip(),
                    "description": data["description"].strip(),
                    "target_date": data["target_date"],
                    "status": data["status"],
                    "created_at": course.get("created_at"),
                }

                courses[index] = updated_course
                save_courses(courses)

                return jsonify(updated_course), 200

        return jsonify({
            "error": f"Course with id {course_id} was not found."
        }), 404

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# DELETE: Delete a course by ID.
@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    try:
        courses = load_courses()

        course_to_delete = next(
            (
                course for course in courses
                if course.get("id") == course_id
            ),
            None,
        )

        if course_to_delete is None:
            return jsonify({
                "error": f"Course with id {course_id} was not found."
            }), 404

        courses.remove(course_to_delete)
        save_courses(courses)

        # HTTP 204 means success with no response body.
        return "", 204

    except StorageError as error:
        return jsonify({"error": str(error)}), 500


# Return JSON for unknown URLs.
@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({
        "error": "The requested endpoint was not found."
    }), 404


# Return JSON when an HTTP method is not supported.
@app.errorhandler(405)
def handle_method_not_allowed(error):
    return jsonify({
        "error": "The HTTP method is not allowed for this endpoint."
    }), 405


if __name__ == "__main__":
    try:
        create_data_file_if_needed()
        print("CodeCraftHub API is starting...")
        print(f"Data will be stored in: {DATA_FILE}")
        print("API will be available at: http://localhost:5000")
    except StorageError as error:
        print(f"Warning: {error}")

    app.run(debug=True, host="127.0.0.1", port=5000)
