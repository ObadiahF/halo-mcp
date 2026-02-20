"""Assignment submission GraphQL queries and mutations."""

ASSIGNMENT_SUBMISSION = """
query AssignmentSubmission($courseClassAssessmentId: String!) {
  assignmentSubmission: getUserAssignmentSubmissionForAssessment(
    courseClassAssessmentId: $courseClassAssessmentId
  ) {
    id
    status
    dueDate
    submissionDate
    resources {
      id
      isFinal
      similarityReportStatusEnum
      similarityScore
      uploadDate
      resource {
        id
        name
        kind
        type
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

COURSE_CLASS_ASSESSMENT = """
query CourseClassAssessment($assessmentId: String!) {
  assessment: getCourseClassAssessmentById(id: $assessmentId) {
    id
    title
    description
    startDate
    dueDate
    points
    requiresLopesWrite
    isGroupEnabled
    type
    attachments {
      id
      resourceId
      title
      __typename
    }
    __typename
  }
}
"""

BULK_ASSIGNMENT_RESOURCE = """
mutation BulkAssignmentResource(
  $courseClassAssessmentId: String!,
  $resourceIds: [String]!
) {
  bulkAddAssignmentSubmissionResource(
    courseClassAssessmentId: $courseClassAssessmentId
    resourceIds: $resourceIds
  ) {
    id
    status
    dueDate
    submissionDate
    resources {
      id
      isFinal
      similarityReportStatusEnum
      similarityScore
      uploadDate
      resource {
        id
        name
        kind
        type
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
