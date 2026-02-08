"""User GraphQL queries."""

GET_USER_BY_ID = """
query getUserById($userId: String!) {
  getUserById(id: $userId) {
    id
    firstName
    lastName
    preferredFirstName
    userImgUrl
    userAccessGroups {
      accessGroup
      __typename
    }
    sourceId
    __typename
  }
}
"""

GET_USER_PREFERENCE_DETAILS = """
query GetUserPreferenceDetails {
  getUserPreferenceDetails {
    id
    userId
    preferenceType
    preferenceValue
    __typename
  }
}
"""

GET_USER_ALERT_COUNT = """
query GetUserAlertCount {
  getUserAlertCount {
    courseClassId
    count
    __typename
  }
}
"""
