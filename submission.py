"""
Assignment submission orchestration.

Executes the full 6-step submission flow:
1. Fetch assessment metadata (GraphQL)
2. Get presigned S3 upload URL (REST)
3. Upload file to S3 (raw PUT)
4. Link resource to submission (GraphQL mutation)
5. Confirm upload status (REST)
6. Final submit (REST)
"""

import mimetypes
from pathlib import Path
from typing import Any

from .request import HaloRequest, upload_to_s3
from . import queries


def _read_file(file_path: str) -> tuple[Path, bytes]:
    """Read file and return (Path object, raw bytes). Raises ValueError if not found."""
    p = Path(file_path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"File not found: {file_path}")
    return p, p.read_bytes()


def _file_type(path: Path) -> str:
    """Infer short file type string (e.g. 'pdf', 'docx') from extension."""
    return path.suffix.lstrip(".").lower() or "bin"


def _content_type(path: Path) -> str:
    """Infer MIME content type from file extension."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def submit_assignment_flow(
    class_id: str,
    class_name: str,
    slug: str,
    assessment_id: str,
    file_path: str,
) -> dict[str, Any]:
    """Execute the full assignment submission flow. Returns final status dict."""

    path, file_bytes = _read_file(file_path)

    # Step 1: Fetch assessment details
    assessment_data = (
        HaloRequest("CourseClassAssessment")
        .query(queries.COURSE_CLASS_ASSESSMENT)
        .variables({"assessmentId": assessment_id})
        .class_slug(slug)
        .course_class(class_id)
        .execute()
    )
    assessment = assessment_data["data"]["assessment"]

    # Step 2: Get presigned upload URL
    presigned_resp = (
        HaloRequest("generate-presigned-urls")
        .class_slug(slug)
        .course_class(class_id)
        .json_body([{
            "type": "assignment_submission",
            "kind": "FILE",
            "description": "",
            "fileName": path.name,
            "fileSize": len(file_bytes),
            "fileType": _file_type(path),
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

    # Step 3: Upload file to S3
    upload_to_s3(s3_url, file_bytes, _content_type(path))

    # Step 4: Link resource to submission (GraphQL mutation)
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
    submission_id = submission["id"]
    resources = submission["resources"]

    # Step 5: Confirm upload status
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

    # Step 6: Final submit
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
        "fileName": path.name,
    }
