"""Forums, discussions, and announcements GraphQL queries."""

ALL_DQ_FOR_COURSE_CLASS = """
query AllDQForCourseClass($courseClassId: String!, $sortBy: String, $pgNum: Int, $pgSize: Int) {
  allDQForCourseClass: getAllDQForCourseClass(
    courseClassId: $courseClassId
    sortBy: $sortBy
    pgNum: $pgNum
    pgSize: $pgSize
  ) {
    contextId
    forumId
    forumType
    courseClassId
    totalPosts
    title
    description
    startDate
    dueDate
    active
    description
    reassignedDueDate
    resources {
      active
      context
      description
      embedReady
      id
      kind
      name
      type
      __typename
    }
    __typename
  }
}
"""

GET_DISCUSSION_FORUM_POSTS = """
query getDiscussionForumPosts($forumId: String, $postId: String, $depthStart: Int, $depthEnd: Int, $dqPostFilters: [DQPostFilter]) {
  Posts: posts(
    forumId: $forumId
    postId: $postId
    depthStart: $depthStart
    depthEnd: $depthEnd
    dqPostFilters: $dqPostFilters
  ) {
    forumId
    content
    id
    originalPostId
    rootParentId
    postStatus
    parentPostId
    hasChildren
    postTags {
      tag
      __typename
    }
    publishDate
    modifiedDate
    createdBy {
      id
      userId
      baseRoleName
      user {
        id
        firstName
        preferredFirstName
        lastName
        userStatus
        userImgUrl
        __typename
      }
      __typename
    }
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
    isAcknowledge
    flagType
    countOfAcknowledgements
    replies {
      forumId
      content
      id
      originalPostId
      postStatus
      parentPostId
      publishDate
      modifiedDate
      createdBy {
        id
        userId
        baseRoleName
        user {
          id
          firstName
          lastName
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

GET_FORUM_NOTIFICATIONS = """
query GetForumNotifications($classId: String!, $filters: FilterInputGQL) {
  classes: getForumNotifications(classId: $classId, filter: $filters) {
    forumTypes {
      ANNOUNCEMENTS {
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
        __typename
      }
      CQ {
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
        __typename
      }
      DQ {
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
        __typename
      }
      IDQ {
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
        __typename
      }
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
      GROUP {
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

GET_ANNOUNCEMENTS_STUDENT = """
query GetAnnouncementsStudent($courseClassId: String!) {
  announcements(courseClassId: $courseClassId) {
    contextId
    courseClassId
    dueDate
    forumId
    forumType
    lastPost {
      isReplied
      __typename
    }
    startDate
    endDate
    title
    posts {
      content
      expiryDate
      forumId
      forumTitle
      id
      isAcknowledge
      modifiedDate
      originalPostId
      parentPostId
      postStatus
      publishDate
      startDate
      tenantId
      title
      postFlagAcknowledgements {
        acknowledge
        acknowledgedTimestamp
        userId
        __typename
      }
      postTags {
        tag
        __typename
      }
      createdBy {
        id
        user {
          id
          firstName
          lastName
          preferredFirstName
          userImgUrl
          __typename
        }
        __typename
      }
      resources {
        kind
        name
        id
        description
        type
        active
        context
        embedReady
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
