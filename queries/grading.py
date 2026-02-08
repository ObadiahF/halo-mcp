"""Grading GraphQL queries."""

ALL_ASSESSMENT_GRADES = """
query AllAssessmentGrades($courseClassSlugId: String!, $courseUnitId: String) {
  assessmentGrades: getAllClassGrades(
    courseClassSlugId: $courseClassSlugId
    courseUnitId: $courseUnitId
  ) {
    grades {
      user {
        id
        __typename
      }
      userLastSeenDate
      assessment {
        id
        inPerson
        __typename
      }
      accommodatedDueDate
      dueDate
      id
      status
      assignmentSubmission {
        submissionDate
        __typename
      }
      userQuizAssessment {
        userQuizId
        accommodatedDuration
        __typename
      }
      isEverReassigned
      history {
        assignmentSubmissionId
        comment
        gradeId
        status
        points
        userCourseClassAssessmentId
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GRADE_OVERVIEW = """
query GradeOverview($courseClassSlugId: String!, $courseClassUserIds: [String]) {
  gradeOverview: getAllClassGrades(
    courseClassSlugId: $courseClassSlugId
    courseClassUserIds: $courseClassUserIds
  ) {
    finalGrade {
      id
      finalPoints
      gradeValue
      isPublished
      maxPoints
      __typename
    }
    grades {
      isEverReassigned
      userLastSeenDate
      assignmentSubmission {
        id
        submissionDate
        __typename
      }
      assessment {
        id
        title
        points
        type
        dueDate
        __typename
      }
      post {
        id
        forumId
        publishDate
        __typename
      }
      assessmentGroup {
        groupUsers {
          user {
            id
            __typename
          }
          __typename
        }
        status
        __typename
      }
      dueDate
      accommodatedDueDate
      finalComment {
        comment
        commentResources {
          resource {
            id
            kind
            name
            type
            active
            context
            description
            embedReady
            __typename
          }
          __typename
        }
        __typename
      }
      finalPoints
      id
      status
      userQuizAssessment {
        accommodatedDuration
        dueTime
        duration
        startTime
        submissionDate
        userQuizId
        __typename
      }
      history {
        comment
        dueDate
        status
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
