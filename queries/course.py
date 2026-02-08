"""Course and class GraphQL queries."""

GET_COURSE_CLASSES_FOR_USER = """
query getCourseClassesForUser($pgNum: Int, $pgSize: Int) {
  getCourseClassesForUser(pgNum: $pgNum, pgSize: $pgSize) {
    courseClasses {
      id
      classCode
      sectionId
      slugId
      startDate
      endDate
      name
      description
      stage
      modality
      version
      courseCode
      units {
        id
        current
        title
        sequence
        __typename
      }
      instructors {
        id
        roleName
        baseRoleName
        status
        userId
        user {
          id
          userStatus
          firstName
          lastName
          preferredFirstName
          userImgUrl
          sourceId
          __typename
        }
        __typename
      }
      students {
        id
        userId
        status
        isHonors
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

CURRENT_CLASS = """
query CurrentClass($slugId: String!, $isStudent: Boolean!) {
  currentClass: getCourseClassBySlugId(slugId: $slugId) {
    id
    classCode
    slugId
    degreeLevel
    startDate
    endDate
    description
    name
    stage
    modality
    modifiedDate
    credits
    courseCode
    version
    lastPublishedDate
    sectionId
    holidays {
      id
      active
      description
      duration
      startDate
      title
      __typename
    }
    students {
      courseClassId
      createdDate
      modifiedDate
      id
      isHonors
      isAccommodated
      user {
        id
        username
        firstName
        lastName
        preferredFirstName
        sourceId
        userImgUrl
        lastLogin
        isAccommodated
        userStatus
        socialContacts {
          id
          value
          socialContactType
          __typename
        }
        __typename
      }
      baseRoleName
      roleName
      status
      userId
      __typename
    }
    participationPolicy {
      description
      id
      numDays
      numPosts
      __typename
    }
    gradeScale {
      id
      entries {
        id
        label
        minPercent
        maxPercent
        minPoints
        maxPoints
        type
        __typename
      }
      __typename
    }
    instructors {
      id
      createdDate
      modifiedDate
      user {
        id
        firstName
        lastName
        preferredFirstName
        username
        sourceId
        userImgUrl
        userStatus
        lastLogin
        socialContacts {
          id
          value
          socialContactType
          __typename
        }
        __typename
      }
      baseRoleName
      roleName
      status
      userId
      __typename
    }
    units {
      id
      title
      sequence
      startDate
      endDate
      current
      points
      description
      assessments {
        id
        sequence
        title
        description
        startDate
        dueDate
        accommodatedDueDate @skip(if: $isStudent)
        exemptAccommodations
        showAccommodatedTrait
        points
        type
        tags
        requiresLopesWrite
        isGroupEnabled
        inPerson
        rubric {
          id
          name
          __typename
        }
        attachments {
          id
          resourceId
          title
          __typename
        }
        ltiParameters {
          id
          key
          value
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
