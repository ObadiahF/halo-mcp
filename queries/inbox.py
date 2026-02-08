"""Inbox GraphQL queries."""

GET_INBOX_LEFT_PANEL = """
query GetInboxLeftPanel {
  getInboxLeftPanel: getInboxLeftPanel {
    courseClassId
    unansweredCount
    forums {
      forumId
      forumType
      courseClassId
      startDate
      endDate
      contextId
      lastPost {
        isReplied
        recipient {
          id
          userStatus
          firstName
          lastName
          preferredFirstName
          userImgUrl
          __typename
        }
        post {
          content
          createdBy {
            baseRoleName
            courseClassId
            id
            roleName
            status
            userId
            user {
              id
              userStatus
              firstName
              lastName
              preferredFirstName
              userImgUrl
              __typename
            }
            __typename
          }
          expiryDate
          id
          parentPostId
          postStatus
          publishDate
          resources {
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
          wordCount
          __typename
        }
        __typename
      }
      posts {
        content
        createdBy {
          baseRoleName
          courseClassId
          id
          roleName
          status
          userId
          user {
            id
            userStatus
            firstName
            lastName
            preferredFirstName
            userImgUrl
            __typename
          }
          __typename
        }
        expiryDate
        id
        parentPostId
        postStatus
        publishDate
        resources {
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
        wordCount
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_INBOX_NOTIFICATIONS = """
query GetInboxNotifications($fetchCounts: Boolean) {
  classes: getInboxNotifications(fetchCounts: $fetchCounts) {
    forumTypes {
      INBOX {
        classes {
          classId
          count
          forums {
            count
            forumId
            posts
            __typename
          }
          __typename
        }
        count
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_POSTS_BY_INBOX_FORUM_ID = """
query getPostsByInboxForumId($forumId: String, $pgNum: Int, $pgSize: Int) {
  getPostsForInboxForum: getPostsForInboxForum(
    forumId: $forumId
    pgNum: $pgNum
    pgSize: $pgSize
  ) {
    content
    createdBy {
      baseRoleName
      courseClassId
      id
      roleName
      status
      userId
      user {
        id
        userStatus
        firstName
        lastName
        preferredFirstName
        userImgUrl
        __typename
      }
      __typename
    }
    expiryDate
    id
    isAcknowledge
    parentPostId
    postStatus
    publishDate
    resources {
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
    wordCount
    postFlagAcknowledgements {
      acknowledge
      userId
      __typename
    }
    postTags {
      tag
      __typename
    }
    __typename
  }
}
"""
