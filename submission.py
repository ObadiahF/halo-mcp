"""
Assignment submission orchestration.

Two-phase flow:
  1. upload_assignment_file_flow — upload a file and attach it to a submission
     (repeatable for multiple files)
  2. submit_assignment_flow — finalize and submit for grading
"""

import mimetypes
from pathlib import Path
from typing import Any

from .request import HaloRequest, upload_to_s3
from . import queries


# ---- helpers ----

def _read_file(file_path: str) -> tuple[str, bytes]:
    """Read a file and return (filename, raw bytes)."""
    p = Path(file_path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"File not found: {file_path}")
    return p.name, p.read_bytes()


def _file_type(filename: str) -> str:
    """Infer short file type string (e.g. 'pdf', 'docx') from extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return ext


def _content_type(filename: str) -> str:
    """Infer MIME content type from filename."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _format_resources(resources: list[dict]) -> list[dict]:
    """Format resource list into a concise summary."""
    return [
        {
            "fileName": r["resource"]["name"],
            "resourceId": r["resource"]["id"],
            "uploadDate": r.get("uploadDate"),
        }
        for r in resources
    ]


# ---- phase 1: upload ----

def upload_assignment_file_flow(
    class_id: str,
    slug: str,
    assessment_id: str,
    file_path: str,
) -> dict[str, Any]:
    """Upload a file and attach it to an assignment submission.

    Steps: presigned URL → S3 upload → link resource → confirm upload.
    Can be called multiple times to attach multiple files before submitting.
    """
    file_name, file_bytes = _read_file(file_path)

    # Get presigned upload URL
    presigned_resp = (
        HaloRequest("generate-presigned-urls")
        .class_slug(slug)
        .course_class(class_id)
        .json_body([{
            "type": "assignment_submission",
            "kind": "FILE",
            "description": "",
            "fileName": file_name,
            "fileSize": len(file_bytes),
            "fileType": _file_type(file_name),
            "storageProviderEnum": ["S3"],
            "resourceSignature": {
                "courseClassId": class_id,
                "courseClassAssessmentId": assessment_id,
                "courseClassAssessmentGroupId": None,
            },
        }])
        .execute_rest_post("/api/v1/orchestrate/generate-presigned-urls")
    )

    resource_id = presigned_resp[0]["resourceId"]
    s3_url = presigned_resp[0]["s3UploadUrl"]

    # Upload file to S3
    upload_to_s3(s3_url, file_bytes, _content_type(file_name))

    # Link resource to submission (GraphQL mutation)
    bulk_resp = (
        HaloRequest("BulkAssignmentResource")
        .query(queries.BULK_ASSIGNMENT_RESOURCE)
        .variables({
            "courseClassAssessmentId": assessment_id,
            "resourceIds": [resource_id],
        })
        .class_slug(slug)
        .course_class(class_id)
        .execute()
    )

    submission = bulk_resp["data"]["bulkAddAssignmentSubmissionResource"]

    # Confirm upload status
    (
        HaloRequest("fileUploadStatus")
        .class_slug(slug)
        .course_class(class_id)
        .json_body([{
            "resourceId": resource_id,
            "status": "COMPLETED",
            "storageProviderEnum": ["S3"],
        }])
        .execute_rest_post("/api/v1/orchestrate/fileUploadStatus")
    )

    return {
        "uploadedFile": file_name,
        "submissionId": submission["id"],
        "totalAttachedFiles": len(submission["resources"]),
        "attachedFiles": _format_resources(submission["resources"]),
    }


# ---- phase 2: submit ----

def submit_assignment_flow(
    class_id: str,
    class_name: str,
    slug: str,
    assessment_id: str,
) -> dict[str, Any]:
    """Finalize and submit an assignment for grading.

    Fetches assessment metadata and current submission state,
    then submits all attached resources.
    """
    # Fetch assessment details (title, requiresLopesWrite)
    assessment_data = (
        HaloRequest("CourseClassAssessment")
        .query(queries.COURSE_CLASS_ASSESSMENT)
        .variables({"assessmentId": assessment_id})
        .class_slug(slug)
        .course_class(class_id)
        .execute()
    )
    assessment = assessment_data["data"]["assessment"]

    # Fetch current submission state (submission ID + all attached resources)
    submission_data = (
        HaloRequest("AssignmentSubmission")
        .query(queries.ASSIGNMENT_SUBMISSION)
        .variables({"courseClassAssessmentId": assessment_id})
        .class_slug(slug)
        .course_class(class_id)
        .execute()
    )
    submission = submission_data["data"]["assignmentSubmission"]
    submission_id = submission["id"]
    resources = submission["resources"]

    if not resources:
        raise ValueError(
            "No files attached to this assignment. "
            "Use upload_assignment_file first."
        )

    # Build resource info for submit payload
    resource_info = [
        {
            "assignmentSubmissionResourceId": r["id"],
            "resourceId": r["resource"]["id"],
            "fileName": r["resource"]["name"],
            "similarityReportStatus": r.get(
                "similarityReportStatusEnum", "NOT_SUBMITTED"
            ),
        }
        for r in resources
    ]

    submit_resp = (
        HaloRequest("submit")
        .class_slug(slug)
        .course_class(class_id)
        .json_body({
            "classId": class_id,
            "className": class_name,
            "assessmentId": assessment_id,
            "assessmentTitle": assessment["title"],
            "requiresLopeswrite": assessment.get("requiresLopesWrite", False),
            "resourceInfo": resource_info,
        })
        .execute_rest_post(
            f"/api/v1/orchestrate/resource/assignment_resource/{submission_id}/submit"
        )
    )

    return {
        "status": submit_resp.get("status", "Unknown"),
        "submissionId": submission_id,
        "assessmentTitle": assessment["title"],
        "filesSubmitted": [r["fileName"] for r in resource_info],
    }
